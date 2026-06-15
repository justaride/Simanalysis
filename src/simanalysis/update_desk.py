"""Read-only Update Desk staging status."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Callable, cast
from zipfile import BadZipFile, ZipFile, is_zipfile

from simanalysis.treatment import assert_sims_not_running as assert_sims_not_running

ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
PACKAGE_EXTENSIONS = {".package"}
SCRIPT_EXTENSIONS = {".ts4script"}
SOURCE_SIDECAR_SUFFIX = ".source.json"
UPDATE_MANIFEST_VERSION = 1
UPDATE_SESSION_ROOT_NAME = "_Simanalysis_UpdateDesk"
UPDATE_MANIFEST_DIR_NAME = "manifests"
UPDATE_MANIFEST_STATUSES = {
    "planned",
    "applying",
    "applied",
    "partial",
    "blocked",
    "undoing",
    "undone",
}
UPDATE_APPLICABLE_MANIFEST_STATUSES = {"planned", "partial"}
UPDATE_UNDOABLE_MANIFEST_STATUSES = {"applying", "applied", "partial", "undoing"}
UPDATE_ACTION_STATUSES = {
    "pending",
    "copying",
    "copied",
    "undo_pending",
    "undoing",
    "undone",
    "blocked",
}
UPDATE_REQUIRED_ACTION_KEYS = {
    "action_id",
    "action_type",
    "source_relative_path",
    "destination_relative_path",
    "source_path",
    "destination_path",
    "expected",
    "installed",
    "status",
    "error",
}


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


def _logical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _reject_symlinked_path(path: Path, message: str) -> None:
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError(f"Refusing {message}: {path}")


def _reject_symlinked_existing_ancestors(path: Path, message: str) -> None:
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    _reject_symlinked_path(current, message)


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


class UpdateInstaller:
    """Commit and undo approved Update Desk copy actions from a plan manifest."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now

    def stage_plan(
        self,
        plan: dict[str, Any],
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        _validate_update_plan(plan)
        selected_ids = _selected_update_action_ids(plan, selected_action_ids, all_actions)
        created_at = self._clock()
        staging_root = _logical_absolute(Path(str(plan["staging_path"])))
        mods_root = _logical_absolute(Path(str(plan["mods_path"])))
        actions = [
            _update_manifest_action(plan, action_id, staging_root, mods_root)
            for action_id in selected_ids
        ]
        operation_id, manifest_path = _unique_update_manifest_path(
            mods_root / UPDATE_SESSION_ROOT_NAME / UPDATE_MANIFEST_DIR_NAME,
            _update_operation_id(created_at),
        )
        manifest: dict[str, Any] = {
            "version": UPDATE_MANIFEST_VERSION,
            "operation_id": operation_id,
            "created_at": created_at,
            "updated_at": created_at,
            "staging_path": str(staging_root),
            "mods_path": str(mods_root),
            "manifest_path": str(manifest_path),
            "source_plan": {
                "version": int(plan["version"]),
                "plan_id": str(plan["plan_id"]),
                "generated_at": str(plan["generated_at"]),
            },
            "status": "planned",
            "mutates_files": True,
            "mutates_mods": True,
            "actions": actions,
            "warnings": [],
            "blockers": [],
        }
        return _write_update_manifest(manifest)

    def commit_plan(
        self,
        plan: dict[str, Any],
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        manifest = self.stage_plan(
            plan,
            selected_action_ids=selected_action_ids,
            all_actions=all_actions,
        )
        return self.apply(manifest["manifest_path"])

    def commit_plan_file(
        self,
        plan_path: Path | str,
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        return self.commit_plan(
            load_update_install_plan(plan_path),
            selected_action_ids=selected_action_ids,
            all_actions=all_actions,
        )

    def apply(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_update_manifest(manifest_path)
        if manifest["status"] not in UPDATE_APPLICABLE_MANIFEST_STATUSES:
            raise ValueError(
                f"Update operation cannot be applied from status: {manifest['status']}"
            )
        actions = _validated_update_actions(manifest)
        pending = [action for action in actions if action.get("status") in {"pending", "blocked"}]
        _preflight_update_actions(manifest, pending)
        manifest["status"] = "applying"
        _save_update_manifest(manifest)

        for action in pending:
            copy_completed = False
            try:
                _preflight_update_action(manifest, action)
                action["status"] = "copying"
                action["error"] = None
                _save_update_manifest(manifest)
                destination = Path(str(action["destination_path"]))
                _ensure_safe_update_destination_parent(manifest, destination)
                if destination.exists():
                    raise ValueError(f"Update destination already exists: {destination}")
                shutil.copy2(str(action["source_path"]), str(destination))
                copy_completed = True
                installed = {
                    "size": destination.stat().st_size,
                    "sha256": _sha256_hex(destination),
                }
                action["installed"] = installed
                action["status"] = "copied"
                action["error"] = None
                _save_update_manifest(manifest)
            except Exception as exc:
                if copy_completed:
                    action["status"] = "undo_pending"
                    action["error"] = str(exc)
                    manifest["status"] = "partial"
                    _save_update_manifest_best_effort(manifest)
                    raise
                action["status"] = "blocked"
                action["error"] = str(exc)
                manifest["status"] = (
                    "partial" if _has_copied_update_actions(manifest) else "blocked"
                )
                _save_update_manifest(manifest)
                raise

        manifest["status"] = "applied"
        return _save_update_manifest(manifest)

    def undo(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_update_manifest(manifest_path)
        actions = _validated_update_actions(manifest)
        undoable = [
            action
            for action in reversed(actions)
            if action.get("status") in {"copying", "copied", "undo_pending", "undoing"}
        ]
        if manifest["status"] not in UPDATE_UNDOABLE_MANIFEST_STATUSES:
            raise ValueError(f"Update operation cannot be undone from status: {manifest['status']}")
        if not undoable:
            raise ValueError("Update operation has no copied actions to undo")
        _preflight_update_undo_actions(manifest, undoable)

        manifest["status"] = "undoing"
        _save_update_manifest(manifest)
        for action in undoable:
            try:
                _preflight_update_undo_action(manifest, action)
                action["status"] = "undoing"
                action["error"] = None
                _save_update_manifest(manifest)
                Path(str(action["destination_path"])).unlink()
                action["status"] = "undone"
                action["error"] = None
                _save_update_manifest(manifest)
            except Exception as exc:
                action["status"] = "undo_pending"
                action["error"] = str(exc)
                manifest["status"] = "partial"
                _save_update_manifest(manifest)
                raise

        if _has_copied_update_actions(manifest):
            manifest["status"] = "partial"
            _save_update_manifest(manifest)
            raise ValueError("Could not undo every copied update action")
        manifest["status"] = "undone"
        return _save_update_manifest(manifest)


def load_update_install_plan(plan_path: Path | str) -> dict[str, Any]:
    path = Path(plan_path).expanduser()
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked update install plan: {plan_path}")
    path = _logical_absolute(path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Update install plan not found: {plan_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Update install plan is not valid JSON: {plan_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Update install plan must be a JSON object")
    plan = cast(dict[str, Any], parsed)
    _validate_update_plan(plan)
    return plan


def load_update_manifest(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path).expanduser()
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked update manifest: {manifest_path}")
    path = _logical_absolute(path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Update manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Update manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Update manifest must be a JSON object")
    manifest = cast(dict[str, Any], parsed)
    _validate_update_manifest(manifest, path)
    return manifest


def _validate_update_plan(plan: dict[str, Any]) -> None:
    if plan.get("version") != 1:
        raise ValueError("Unsupported update install plan version")
    for key in ("plan_id", "generated_at", "staging_path", "mods_path", "actions"):
        if key not in plan:
            raise ValueError(f"Update install plan is missing required key: {key}")
    if not isinstance(plan["actions"], list):
        raise ValueError("Update install plan actions must be a list")
    if plan.get("status") == "blocked":
        raise ValueError("Blocked update install plans cannot be committed")


def _selected_update_action_ids(
    plan: dict[str, Any],
    selected_action_ids: list[str] | None,
    all_actions: bool,
) -> list[str]:
    selected = list(selected_action_ids or [])
    if selected and all_actions:
        raise ValueError("Choose explicit update actions or --all-actions, not both")
    available = [_update_plan_action_id(action) for action in _copy_plan_actions(plan)]
    if all_actions:
        selected = available
    if not selected:
        raise ValueError("Choose at least one update action")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate update action selected")
    missing = sorted(set(selected) - set(available))
    if missing:
        raise ValueError(f"Unknown or non-copy update action: {', '.join(missing)}")
    return selected


def _copy_plan_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        action
        for action in plan["actions"]
        if isinstance(action, dict) and action.get("action_type") == "copy_staged_file"
    ]


def _update_plan_action_id(action: dict[str, Any]) -> str:
    action_id = action.get("action_id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError("Update action is missing action_id")
    return action_id


def _find_update_plan_action(plan: dict[str, Any], action_id: str) -> dict[str, Any]:
    matches = [
        action for action in _copy_plan_actions(plan) if action.get("action_id") == action_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Update action must map to exactly one copy action: {action_id}")
    return matches[0]


def _update_manifest_action(
    plan: dict[str, Any],
    action_id: str,
    staging_root: Path,
    mods_root: Path,
) -> dict[str, Any]:
    action = _find_update_plan_action(plan, action_id)
    if action.get("status") != "planned":
        raise ValueError(f"Update action is not planned: {action_id}")
    source_relative = str(action.get("source_relative_path", ""))
    destination_relative = str(action.get("destination_relative_path", ""))
    source_path = _resolve_update_source(staging_root, source_relative)
    destination_path = _resolve_update_destination(mods_root, destination_relative)
    if _logical_absolute(Path(str(action.get("source_path", "")))) != source_path:
        raise ValueError("Update source path does not match relative path")
    if _logical_absolute(Path(str(action.get("destination_path", "")))) != destination_path:
        raise ValueError("Update destination path does not match relative path")
    _reject_symlinked_path(source_path, "symlinked update source")
    _reject_symlinked_existing_ancestors(destination_path, "symlinked update destination")
    expected = action.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("Update action expected evidence must be an object")
    _validate_update_expected(expected)
    return {
        "action_id": action_id,
        "action_type": "copy_staged_file",
        "source_name": action.get("source_name"),
        "source_relative_path": source_relative,
        "destination_relative_path": destination_relative,
        "source_path": str(source_path),
        "destination_path": str(destination_path),
        "expected": {
            "size": int(expected["size"]),
            "sha256": str(expected["sha256"]),
        },
        "installed": None,
        "source_binding": action.get("source_binding", {"status": "unknown"}),
        "status": "pending",
        "error": None,
    }


def _resolve_update_source(staging_root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Update source must be a relative staging path")
    source = _logical_absolute(staging_root / relative_path)
    try:
        source.relative_to(staging_root)
    except ValueError as exc:
        raise ValueError("Update source must be under staging") from exc
    return source


def _resolve_update_destination(mods_root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Update destination must be relative")
    destination = _logical_absolute(mods_root / relative_path)
    try:
        destination.relative_to(mods_root)
    except ValueError as exc:
        raise ValueError("Update destination must be under Mods") from exc
    if destination == mods_root:
        raise ValueError("Update destination must be a file path")
    return destination


def _write_update_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(manifest["manifest_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(json.dumps(manifest, indent=2, sort_keys=True))
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
        try:
            parent_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return manifest
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return manifest


def _save_update_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_update_manifest_write_target(manifest)
    manifest["updated_at"] = _utc_now()
    return _write_update_manifest(manifest)


def _save_update_manifest_best_effort(manifest: dict[str, Any]) -> None:
    with suppress(Exception):
        _save_update_manifest(manifest)


def _validate_update_manifest(manifest: dict[str, Any], path: Path) -> None:
    if manifest.get("version") != UPDATE_MANIFEST_VERSION:
        raise ValueError("Unsupported update manifest version")
    required = {
        "operation_id",
        "created_at",
        "updated_at",
        "staging_path",
        "mods_path",
        "manifest_path",
        "source_plan",
        "status",
        "mutates_files",
        "mutates_mods",
        "actions",
        "warnings",
        "blockers",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"Update manifest is missing required keys: {', '.join(sorted(missing))}")
    if manifest["status"] not in UPDATE_MANIFEST_STATUSES:
        raise ValueError(f"Unknown update manifest status: {manifest['status']}")
    if _logical_absolute(Path(str(manifest["manifest_path"]))) != path:
        raise ValueError("Update manifest path does not match loaded path")
    if manifest.get("mutates_files") is not True or manifest.get("mutates_mods") is not True:
        raise ValueError("Update manifest must declare Mods mutation")
    if not isinstance(manifest["actions"], list):
        raise ValueError("Update manifest actions must be a list")


def _validate_update_manifest_write_target(manifest: dict[str, Any]) -> None:
    mods_root = _manifest_update_mods(manifest)
    manifest_path = _absolute_update_manifest_path(manifest)
    manifest_root = _logical_absolute(
        mods_root / UPDATE_SESSION_ROOT_NAME / UPDATE_MANIFEST_DIR_NAME
    )
    try:
        manifest_path.relative_to(manifest_root)
    except ValueError as exc:
        raise ValueError("Update manifest path must be under update manifest root") from exc
    _reject_symlinked_path(manifest_path, "symlinked update manifest")


def _validated_update_actions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_update_manifest_write_target(manifest)
    validated: list[dict[str, Any]] = []
    for index, action in enumerate(manifest.get("actions", [])):
        if not isinstance(action, dict):
            raise ValueError(f"Update manifest action at index {index} must be an object")
        _validate_update_action_contract(manifest, action)
        validated.append(action)
    return validated


def _validate_update_action_contract(manifest: dict[str, Any], action: dict[str, Any]) -> None:
    missing = UPDATE_REQUIRED_ACTION_KEYS - set(action)
    if missing:
        raise ValueError(
            f"Update manifest action is missing required keys: {', '.join(sorted(missing))}"
        )
    for key in (
        "action_id",
        "action_type",
        "source_relative_path",
        "destination_relative_path",
        "source_path",
        "destination_path",
    ):
        if not isinstance(action[key], str) or not action[key]:
            raise ValueError(f"Update manifest action {key} must be a non-empty string")
    if action["action_type"] != "copy_staged_file":
        raise ValueError(f"Unsupported update action type: {action['action_type']}")
    if action["status"] not in UPDATE_ACTION_STATUSES:
        raise ValueError(f"Unsupported update action status: {action['status']}")
    if action["error"] is not None and not isinstance(action["error"], str):
        raise ValueError("Update action error must be a string or null")
    _validate_update_expected(action["expected"])
    if action["installed"] is not None:
        _validate_update_expected(action["installed"])
    staging_root = _manifest_update_staging(manifest)
    mods_root = _manifest_update_mods(manifest)
    source = _absolute_update_action_path(action, "source_path", "Update source path")
    destination = _absolute_update_action_path(
        action,
        "destination_path",
        "Update destination path",
    )
    if source != _resolve_update_source(staging_root, str(action["source_relative_path"])):
        raise ValueError("Update source path does not match relative path")
    if destination != _resolve_update_destination(
        mods_root,
        str(action["destination_relative_path"]),
    ):
        raise ValueError("Update destination path does not match relative path")


def _preflight_update_actions(manifest: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    _reject_duplicate_update_paths(actions, "source_path", "source")
    _reject_duplicate_update_paths(actions, "destination_path", "destination")
    for action in actions:
        _preflight_update_action(manifest, action)


def _preflight_update_action(manifest: dict[str, Any], action: dict[str, Any]) -> None:
    _validate_update_action_contract(manifest, action)
    source = Path(str(action["source_path"]))
    destination = Path(str(action["destination_path"]))
    if not source.exists():
        raise ValueError(f"Update source path is missing: {source}")
    if not source.is_file():
        raise ValueError(f"Update source path is not a file: {source}")
    _reject_symlinked_path(source, "symlinked update source")
    _reject_symlinked_existing_ancestors(destination, "symlinked update destination")
    if destination.exists():
        raise ValueError(f"Update destination already exists: {destination}")
    _validate_update_path_identity(action, source, "Update source path", "plan")


def _preflight_update_undo_actions(
    manifest: dict[str, Any],
    actions: list[dict[str, Any]],
) -> None:
    _reject_duplicate_update_paths(actions, "destination_path", "undo source")
    for action in actions:
        _preflight_update_undo_action(manifest, action)


def _preflight_update_undo_action(manifest: dict[str, Any], action: dict[str, Any]) -> None:
    _validate_update_action_contract(manifest, action)
    destination = Path(str(action["destination_path"]))
    if not destination.exists():
        raise ValueError(f"Update destination is missing: {destination}")
    _reject_symlinked_path(destination, "symlinked update destination")
    installed = action.get("installed")
    if not isinstance(installed, dict) and action.get("status") != "copying":
        raise ValueError("Update action has no installed evidence")
    evidence_label = "manifest" if isinstance(installed, dict) else "plan"
    _validate_update_path_identity(action, destination, "Update destination", evidence_label)


def _reject_duplicate_update_paths(
    actions: list[dict[str, Any]],
    key: str,
    label: str,
) -> None:
    seen: dict[Path, str] = {}
    for action in actions:
        path = _logical_absolute(Path(str(action[key])))
        action_id = str(action["action_id"])
        previous_action_id = seen.get(path)
        if previous_action_id is not None:
            raise ValueError(
                f"Duplicate update action {label} path: {path} ({previous_action_id}, {action_id})"
            )
        seen[path] = action_id


def _ensure_safe_update_destination_parent(manifest: dict[str, Any], destination: Path) -> None:
    mods_root = _manifest_update_mods(manifest)
    destination = _logical_absolute(destination)
    try:
        relative_parent = destination.parent.relative_to(mods_root)
    except ValueError as exc:
        raise ValueError("Update destination path must be under Mods") from exc
    _ensure_safe_update_directory_component(mods_root, destination)
    current = mods_root
    for part in relative_parent.parts:
        current = current / part
        _ensure_safe_update_directory_component(current, destination)


def _ensure_safe_update_directory_component(path: Path, destination: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked update destination: {destination}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"Update destination parent is not a directory: {path}")
    if not path.exists():
        path.mkdir(exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked update destination: {destination}")
    if not path.is_dir():
        raise ValueError(f"Update destination parent is not a directory: {path}")


def _validate_update_expected(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Update expected evidence must be an object")
    try:
        size = int(value["size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Update expected size must be an integer") from exc
    if size < 0:
        raise ValueError("Update expected size must be non-negative")
    sha = value.get("sha256")
    if not isinstance(sha, str) or not sha:
        raise ValueError("Update expected sha256 must be a non-empty string")
    return {"size": size, "sha256": sha}


def _validate_update_path_identity(
    action: dict[str, Any],
    path: Path,
    label: str,
    evidence_label: str,
) -> None:
    evidence_key = "installed" if evidence_label == "manifest" else "expected"
    expected = _validate_update_expected(action[evidence_key])
    if path.stat().st_size != int(expected["size"]):
        raise ValueError(f"{label} no longer matches update {evidence_label} evidence: {path}")
    if _sha256_hex(path) != str(expected["sha256"]):
        raise ValueError(f"{label} no longer matches update {evidence_label} evidence: {path}")


def _absolute_update_action_path(action: dict[str, Any], key: str, label: str) -> Path:
    path = Path(str(action[key])).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    return _logical_absolute(path)


def _absolute_update_manifest_path(manifest: dict[str, Any]) -> Path:
    path = Path(str(manifest["manifest_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Update manifest path must be absolute")
    return _logical_absolute(path)


def _manifest_update_staging(manifest: dict[str, Any]) -> Path:
    path = Path(str(manifest["staging_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Update manifest staging path must be absolute")
    staging_root = _logical_absolute(path)
    if not staging_root.exists() or not staging_root.is_dir():
        raise ValueError(f"Update manifest staging path is not a directory: {staging_root}")
    return staging_root


def _manifest_update_mods(manifest: dict[str, Any]) -> Path:
    path = Path(str(manifest["mods_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Update manifest Mods path must be absolute")
    mods_root = _logical_absolute(path)
    if not mods_root.exists() or not mods_root.is_dir():
        raise ValueError(f"Update manifest Mods path is not a directory: {mods_root}")
    return mods_root


def _has_copied_update_actions(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(action, dict)
        and action.get("status") in {"copying", "copied", "undo_pending", "undoing"}
        for action in manifest.get("actions", [])
    )


def _unique_update_manifest_path(manifest_dir: Path, base_operation_id: str) -> tuple[str, Path]:
    _reject_symlinked_path(manifest_dir, "symlinked update manifest root")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    operation_id = base_operation_id
    suffix = 1
    while True:
        path = manifest_dir / f"{operation_id}.json"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            suffix += 1
            operation_id = f"{base_operation_id}-{suffix}"
        else:
            os.close(fd)
            return operation_id, path


def _update_operation_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"update-op-{digits[:8]}-{digits[8:14]}"


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
