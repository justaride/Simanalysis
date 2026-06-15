"""Read-only Update Desk staging status."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile, is_zipfile

ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
PACKAGE_EXTENSIONS = {".package"}
SCRIPT_EXTENSIONS = {".ts4script"}
SOURCE_SIDECAR_SUFFIX = ".source.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _modified_at(path: Path) -> str | None:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_hex(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signal(
    signal_id: str,
    severity: str,
    message: str,
    *,
    path: str | None = None,
    paths: list[str] | None = None,
) -> dict[str, Any]:
    signal: dict[str, Any] = {
        "id": signal_id,
        "severity": severity,
        "message": message,
    }
    if path is not None:
        signal["path"] = path
    if paths is not None:
        signal["paths"] = paths
    return signal


def _missing_staging_status(staging_dir: Path) -> dict[str, Any]:
    message = "The selected Update Desk staging folder does not exist."
    return {
        "status": "missing_staging_folder",
        "staging_path": str(staging_dir),
        "item_count": 0,
        "archive_count": 0,
        "package_count": 0,
        "script_count": 0,
        "other_count": 0,
        "source_bound_count": 0,
        "missing_source_count": 0,
        "total_size_bytes": 0,
        "latest_modified_at": None,
        "extension_counts": {},
        "items": [],
        "signals": [_signal("missing_staging_folder", "medium", message, path=str(staging_dir))],
        "warnings": [message],
        "recommendations": [
            "Choose or create a staging folder before reviewing external downloads."
        ],
        "mutates_files": False,
    }


def detect_case_collisions(relative_paths: list[str]) -> list[dict[str, Any]]:
    """Return casefold collisions for staged paths."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for relative_path in relative_paths:
        grouped[relative_path.casefold()].append(relative_path)

    signals: list[dict[str, Any]] = []
    for paths in grouped.values():
        unique_paths = list(dict.fromkeys(paths))
        if len(unique_paths) < 2:
            continue
        signals.append(
            _signal(
                "case_collision",
                "high",
                "Multiple staged paths differ only by case or Unicode casefolding.",
                paths=unique_paths,
            )
        )
    return signals


def _kind(extension: str) -> str:
    if extension in ARCHIVE_EXTENSIONS:
        return "archive"
    if extension in PACKAGE_EXTENSIONS:
        return "package"
    if extension in SCRIPT_EXTENSIONS:
        return "script"
    return "other"


def _unsafe_archive_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts


def _archive_scan(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    extension = path.suffix.lower()
    if extension not in ARCHIVE_EXTENSIONS:
        return {"status": "not_archive"}, []

    if extension != ".zip":
        return {
            "status": "listing_unsupported",
            "member_count": None,
            "unsafe_members": [],
        }, []

    if not is_zipfile(path):
        message = "ZIP archive could not be read as a valid archive."
        return {
            "status": "unreadable_zip",
            "member_count": None,
            "unsafe_members": [],
        }, [_signal("archive_unreadable", "medium", message, path=path.name)]

    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
    except (BadZipFile, OSError):
        message = "ZIP archive could not be opened for safe listing."
        return {
            "status": "unreadable_zip",
            "member_count": None,
            "unsafe_members": [],
        }, [_signal("archive_unreadable", "medium", message, path=path.name)]

    unsafe_members = [name for name in names if _unsafe_archive_member(name)]
    if unsafe_members:
        return {
            "status": "unsafe_members",
            "member_count": len(names),
            "unsafe_members": unsafe_members,
        }, [
            _signal(
                "archive_path_escape",
                "high",
                "Archive contains absolute or parent-directory member paths.",
                path=path.name,
                paths=unsafe_members,
            )
        ]

    return {
        "status": "readable_zip",
        "member_count": len(names),
        "unsafe_members": [],
    }, []


def _source_binding(
    sidecar: Path | None, root: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sidecar is None:
        return {"status": "missing"}, []

    relative_path = sidecar.relative_to(root).as_posix()
    try:
        data = json.loads(sidecar.read_text())
    except (OSError, json.JSONDecodeError):
        return {
            "status": "invalid",
            "relative_path": relative_path,
        }, [
            _signal(
                "invalid_source_binding",
                "medium",
                "Source binding sidecar is not readable JSON.",
                path=relative_path,
            )
        ]

    return {
        "status": "bound",
        "relative_path": relative_path,
        "source_url": data.get("source_url") or data.get("url"),
        "creator": data.get("creator"),
        "downloaded_at": data.get("downloaded_at"),
    }, []


def _file_payload(
    path: Path, root: Path, source_sidecar: Path | None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    extension = path.suffix.lower()
    archive_scan, archive_signals = _archive_scan(path)
    source_binding, source_signals = _source_binding(source_sidecar, root)
    relative_path = path.relative_to(root).as_posix()
    signals = [*archive_signals, *source_signals]
    if source_binding["status"] == "missing" and _kind(extension) in {
        "archive",
        "package",
        "script",
    }:
        signals.append(
            _signal(
                "missing_source_binding",
                "low",
                "Staged mod candidate has no source binding sidecar.",
                path=relative_path,
            )
        )

    return {
        "name": path.name,
        "relative_path": relative_path,
        "path": str(path),
        "extension": extension,
        "kind": _kind(extension),
        "size_bytes": path.stat().st_size,
        "modified_at": _modified_at(path),
        "source_binding": source_binding,
        "archive_scan": archive_scan,
    }, signals


def build_update_staging_status(staging_dir: Path | str) -> dict[str, Any]:
    """Inspect an Update Desk staging folder without editing or moving files."""
    root = Path(staging_dir).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return _missing_staging_status(root)

    children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    source_sidecars = {
        child.name.removesuffix(SOURCE_SIDECAR_SUFFIX): child
        for child in children
        if child.is_file() and child.name.endswith(SOURCE_SIDECAR_SUFFIX)
    }
    item_names = {
        child.name for child in children if not child.name.endswith(SOURCE_SIDECAR_SUFFIX)
    }

    warnings: list[str] = []
    signals: list[dict[str, Any]] = []
    relative_paths: list[str] = []
    items: list[dict[str, Any]] = []
    extension_counts: dict[str, int] = {}
    total_size_bytes = 0
    latest_modified_at: str | None = None

    for child in children:
        relative_path = child.relative_to(root).as_posix()
        relative_paths.append(relative_path)

        if child.is_symlink():
            message = f"Skipped symlinked staging entry: {child}"
            warnings.append(message)
            signals.append(_signal("symlink_skipped", "high", message, path=relative_path))
            continue

        if child.name.startswith("._"):
            signals.append(
                _signal(
                    "appledouble_noise",
                    "low",
                    "AppleDouble sidecar file found in staging.",
                    path=relative_path,
                )
            )
            continue

        if child.name.casefold().endswith(".icloud"):
            signals.append(
                _signal(
                    "icloud_placeholder",
                    "medium",
                    "iCloud placeholder or evicted file marker found in staging.",
                    path=relative_path,
                )
            )
            continue

        if not child.is_file():
            signals.append(
                _signal(
                    "non_file_entry",
                    "low",
                    "Non-file entry found in staging and ignored.",
                    path=relative_path,
                )
            )
            continue

        if child.name.endswith(SOURCE_SIDECAR_SUFFIX):
            if child.name.removesuffix(SOURCE_SIDECAR_SUFFIX) not in item_names:
                signals.append(
                    _signal(
                        "orphan_source_binding",
                        "low",
                        "Source binding sidecar has no matching staged file.",
                        path=relative_path,
                    )
                )
            continue

        payload, item_signals = _file_payload(child, root, source_sidecars.get(child.name))
        items.append(payload)
        signals.extend(item_signals)
        total_size_bytes += payload["size_bytes"]
        extension_counts[payload["extension"]] = extension_counts.get(payload["extension"], 0) + 1
        modified_at = payload["modified_at"]
        if modified_at and (latest_modified_at is None or modified_at > latest_modified_at):
            latest_modified_at = modified_at

    signals.extend(detect_case_collisions(relative_paths))

    archive_count = sum(1 for item in items if item["kind"] == "archive")
    package_count = sum(1 for item in items if item["kind"] == "package")
    script_count = sum(1 for item in items if item["kind"] == "script")
    other_count = sum(1 for item in items if item["kind"] == "other")
    source_bound_count = sum(1 for item in items if item["source_binding"]["status"] == "bound")
    missing_source_count = sum(1 for item in items if item["source_binding"]["status"] == "missing")

    if items or signals:
        status = "review_recommended"
        recommendations = [
            "Keep external downloads in staging until an install plan has been reviewed.",
            "Treat archive scan signals as evidence; this status does not extract archives.",
            "Do not copy staged files into Mods until a snapshot-backed plan is approved.",
        ]
    else:
        status = "no_staged_files_found"
        recommendations = ["No staged update files were found in the selected folder."]

    return {
        "status": status,
        "staging_path": str(root),
        "item_count": len(items),
        "archive_count": archive_count,
        "package_count": package_count,
        "script_count": script_count,
        "other_count": other_count,
        "source_bound_count": source_bound_count,
        "missing_source_count": missing_source_count,
        "total_size_bytes": total_size_bytes,
        "latest_modified_at": latest_modified_at,
        "extension_counts": dict(sorted(extension_counts.items())),
        "items": items,
        "signals": signals,
        "warnings": warnings,
        "recommendations": recommendations,
        "mutates_files": False,
    }


def _mods_case_index(mods_root: Path) -> dict[str, str]:
    if not mods_root.exists() or not mods_root.is_dir():
        return {}
    return {child.name.casefold(): child.name for child in mods_root.iterdir()}


def _destination_blockers(mods_root: Path, destination: Path) -> list[str]:
    blockers: list[str] = []
    if not mods_root.exists() or not mods_root.is_dir():
        return ["mods_folder_missing"]

    if destination.is_symlink():
        blockers.append("destination_symlink")
    elif destination.exists():
        blockers.append("destination_exists")

    case_match = _mods_case_index(mods_root).get(destination.name.casefold())
    if case_match is not None and case_match != destination.name:
        blockers.append("case_collision")

    return blockers


def _copy_action(index: int, item: dict[str, Any], mods_root: Path) -> dict[str, Any]:
    source = Path(str(item["path"]))
    destination_name = Path(str(item["name"])).name
    destination = mods_root / destination_name
    blockers = _destination_blockers(mods_root, destination)
    expected = {
        "size": item.get("size_bytes", 0),
        "sha256": _sha256_hex(source),
    }
    review_notes: list[str] = []
    if item.get("source_binding", {}).get("status") != "bound":
        review_notes.append("source_binding_not_bound")

    return {
        "action_id": f"update-copy-{index:03d}",
        "action_type": "copy_staged_file",
        "status": "blocked" if blockers else "planned",
        "source_name": item.get("name"),
        "source_path": item.get("path"),
        "source_relative_path": item.get("relative_path"),
        "destination_relative_path": destination_name,
        "destination_path": str(destination),
        "expected": expected,
        "source_binding": item.get("source_binding", {"status": "unknown"}),
        "archive_scan": item.get("archive_scan", {"status": "not_archive"}),
        "blockers": blockers,
        "review_notes": review_notes,
    }


def _archive_blockers(archive_scan: dict[str, Any]) -> list[str]:
    status = archive_scan.get("status")
    if status == "unsafe_members":
        return ["archive_path_escape"]
    if status == "unreadable_zip":
        return ["archive_unreadable"]
    if status == "listing_unsupported":
        return ["archive_listing_unsupported"]
    return []


def _archive_action(index: int, item: dict[str, Any]) -> dict[str, Any]:
    archive_scan = item.get("archive_scan", {"status": "not_archive"})
    blockers = _archive_blockers(archive_scan)
    return {
        "action_id": f"update-archive-{index:03d}",
        "action_type": "review_archive",
        "status": "blocked" if blockers else "review_required",
        "source_name": item.get("name"),
        "source_path": item.get("path"),
        "source_relative_path": item.get("relative_path"),
        "destination_relative_path": None,
        "destination_path": None,
        "expected": {
            "size": item.get("size_bytes", 0),
            "sha256": _sha256_hex(Path(str(item["path"]))),
        },
        "source_binding": item.get("source_binding", {"status": "unknown"}),
        "archive_scan": archive_scan,
        "blockers": blockers,
        "review_notes": ["archive_requires_explicit_review"],
    }


def _plan_status(actions: list[dict[str, Any]], staging_status: str) -> str:
    if staging_status == "missing_staging_folder":
        return "blocked"
    if any(action["status"] == "blocked" for action in actions):
        return "blocked"
    if not actions:
        return "empty"
    return "ready_for_review"


def build_update_install_plan(
    staging_dir: Path | str,
    mods_dir: Path | str,
) -> dict[str, Any]:
    """Build a read-only staged update install plan without changing Mods."""
    staging_status = build_update_staging_status(staging_dir)
    mods_root = Path(mods_dir).expanduser().resolve()
    actions: list[dict[str, Any]] = []

    for item in staging_status.get("items", []):
        kind = item.get("kind")
        if kind in {"package", "script"}:
            actions.append(_copy_action(len(actions) + 1, item, mods_root))
        elif kind == "archive":
            actions.append(_archive_action(len(actions) + 1, item))

    blocked_count = sum(1 for action in actions if action["status"] == "blocked")
    copy_count = sum(1 for action in actions if action["action_type"] == "copy_staged_file")
    archive_review_count = sum(1 for action in actions if action["action_type"] == "review_archive")
    status = _plan_status(actions, str(staging_status.get("status", "unknown")))

    recommendations = [
        "Review this plan before any snapshot-backed commit step.",
        "Archives are not extracted by this plan; review archive actions separately.",
        "Do not change Mods until a snapshot and approval gate exists for this plan.",
    ]
    if blocked_count:
        recommendations.insert(0, "Resolve blocked actions before approving an update commit.")

    generated_at = _utc_now()
    return {
        "version": 1,
        "plan_id": "update-plan-" + generated_at.replace("-", "").replace(":", "")[:15],
        "generated_at": generated_at,
        "status": status,
        "staging_status": staging_status.get("status", "unknown"),
        "staging_path": staging_status.get("staging_path"),
        "mods_path": str(mods_root),
        "manifest_path": None,
        "action_count": len(actions),
        "copy_count": copy_count,
        "archive_review_count": archive_review_count,
        "blocked_count": blocked_count,
        "requires_snapshot": True,
        "mutates_files": False,
        "mutates_mods": False,
        "actions": actions,
        "signals": staging_status.get("signals", []),
        "warnings": staging_status.get("warnings", []),
        "recommendations": recommendations,
    }


def write_update_install_plan(
    plan: dict[str, Any],
    output_path: Path | str,
) -> dict[str, Any]:
    """Write a plan manifest explicitly requested by the caller."""
    path = Path(output_path).expanduser().resolve()
    if path.exists() and path.is_symlink():
        raise ValueError(f"Refusing to replace symlinked update plan: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = dict(plan)
    saved["manifest_path"] = str(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(saved, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return saved


def format_update_install_plan_text(plan: dict[str, Any]) -> str:
    """Format an Update Desk install plan for terminal review."""
    lines = [
        "Update Desk Install Plan",
        f"Status: {plan.get('status', 'unknown')}",
        f"Staging: {plan.get('staging_path', 'unknown')}",
        f"Mods: {plan.get('mods_path', 'unknown')}",
        "Read-only: yes",
        "Mods mutation: no",
        f"Snapshot required: {'yes' if plan.get('requires_snapshot') else 'no'}",
        f"Actions: {plan.get('action_count', 0)}",
        f"Blocked: {plan.get('blocked_count', 0)}",
    ]
    if plan.get("manifest_path"):
        lines.append(f"Manifest: {plan['manifest_path']}")

    actions = plan.get("actions") or []
    if actions:
        lines.append("")
        lines.append("Actions:")
        for action in actions:
            destination = action.get("destination_relative_path") or "(review only)"
            blockers = action.get("blockers") or []
            blocker_suffix = f" blocked={','.join(blockers)}" if blockers else ""
            lines.append(
                f"- {action.get('action_id')}: {action.get('status')} "
                f"{action.get('source_name')} -> {destination}{blocker_suffix}"
            )

    recommendations = plan.get("recommendations") or []
    if recommendations:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in recommendations)

    return "\n".join(lines)


def format_update_staging_text(status: dict[str, Any]) -> str:
    """Format Update Desk staging status for terminal review."""
    lines = [
        "Update Desk",
        f"Status: {status.get('status', 'unknown')}",
        f"Staging: {status.get('staging_path', 'unknown')}",
        "Read-only: yes",
        f"Items: {status.get('item_count', 0)}",
        f"Archives: {status.get('archive_count', 0)}",
        f"Packages: {status.get('package_count', 0)}",
        f"Scripts: {status.get('script_count', 0)}",
        f"Source-bound: {status.get('source_bound_count', 0)}",
        f"Missing source: {status.get('missing_source_count', 0)}",
        f"Total size: {status.get('total_size_bytes', 0)} bytes",
    ]

    items = status.get("items") or []
    if items:
        lines.append("")
        lines.append("Staged items:")
        for item in items:
            archive_status = item.get("archive_scan", {}).get("status", "not_archive")
            lines.append(
                f"- {item.get('name', 'unknown')}: {item.get('kind', 'unknown')}, "
                f"{item.get('size_bytes', 0)} bytes, source "
                f"{item.get('source_binding', {}).get('status', 'unknown')}, "
                f"archive {archive_status}"
            )

    signals = status.get("signals") or []
    if signals:
        lines.append("")
        lines.append("Signals:")
        for signal in signals:
            location = signal.get("path") or ", ".join(signal.get("paths", []))
            suffix = f" ({location})" if location else ""
            lines.append(f"- {signal.get('id', 'signal')}: {signal.get('message', '')}{suffix}")

    warnings = status.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)

    recommendations = status.get("recommendations") or []
    if recommendations:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in recommendations)

    return "\n".join(lines)
