"""Read-only Tray dependency status for Sims 4 user folders."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRAY_EXTENSIONS = {
    ".trayitem",
    ".blueprint",
    ".bpi",
    ".hhi",
    ".householdbinary",
    ".sgi",
    ".rmi",
}

TYPE_SIDECAR_EXTENSIONS = {
    ".blueprint",
    ".bpi",
    ".hhi",
    ".householdbinary",
    ".rmi",
}


def _modified_at(path: Path) -> str | None:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


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


def _tray_file_payload(path: Path, root: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "relative_path": path.relative_to(root).as_posix(),
        "path": str(path),
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "modified_at": _modified_at(path),
    }


def detect_case_collisions(relative_paths: list[str]) -> list[dict[str, Any]]:
    """Return casefold collisions for paths that would be ambiguous on case-insensitive volumes."""
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
                "Multiple Tray paths differ only by case or Unicode casefolding.",
                paths=unique_paths,
            )
        )
    return signals


def _missing_tray_status(root: Path, tray_dir: Path) -> dict[str, Any]:
    message = "The selected Sims 4 folder does not contain a Tray directory."
    return {
        "status": "missing_tray_folder",
        "root_path": str(root),
        "tray_path": str(tray_dir),
        "tray_file_count": 0,
        "group_count": 0,
        "anchored_group_count": 0,
        "sidecar_only_group_count": 0,
        "total_size_bytes": 0,
        "latest_modified_at": None,
        "extension_counts": {},
        "groups": [],
        "signals": [_signal("missing_tray_folder", "medium", message, path=tray_dir.as_posix())],
        "warnings": [message],
        "recommendations": [
            "Choose the Sims 4 user folder that contains Tray if you want Tray status."
        ],
        "mutates_files": False,
    }


def _type_hint(extensions: set[str], has_trayitem: bool) -> str:
    if ".hhi" in extensions or ".householdbinary" in extensions:
        return "Household"
    if ".rmi" in extensions:
        return "Room"
    if ".blueprint" in extensions or ".bpi" in extensions:
        return "Lot or room"
    if has_trayitem:
        return "Tray item"
    return "Sidecar group"


def _finalize_group(group: dict[str, Any]) -> dict[str, Any]:
    extensions = set(group["extensions"])
    has_trayitem = ".trayitem" in extensions
    group["files"].sort(key=lambda item: item["relative_path"].casefold())
    group["extensions"] = sorted(extensions)
    group["file_count"] = len(group["files"])
    group["has_trayitem"] = has_trayitem
    group["type_hint"] = _type_hint(extensions, has_trayitem)
    group["dependency_signals"] = []

    if not has_trayitem:
        group["dependency_signals"].append(
            {
                "id": "sidecar_without_trayitem",
                "severity": "medium",
                "message": "Tray sidecar files exist without a .trayitem anchor.",
            }
        )
    elif not (extensions & TYPE_SIDECAR_EXTENSIONS):
        group["dependency_signals"].append(
            {
                "id": "type_confidence_limited",
                "severity": "low",
                "message": "No household, lot, or room sidecar was found for this .trayitem.",
            }
        )
    return group


def build_tray_status(sims4_dir: Path | str) -> dict[str, Any]:
    """Inspect Sims 4 Tray files without editing or moving anything."""
    root = Path(sims4_dir).expanduser().resolve()
    tray_dir = root / "Tray"
    if not tray_dir.exists() or not tray_dir.is_dir():
        return _missing_tray_status(root, tray_dir)

    warnings: list[str] = []
    signals: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    relative_paths: list[str] = []
    extension_counts: dict[str, int] = {}
    latest_modified_at: str | None = None
    total_size_bytes = 0
    tray_file_count = 0

    for child in sorted(tray_dir.iterdir(), key=lambda item: item.name.casefold()):
        relative_path = child.relative_to(root).as_posix()
        relative_paths.append(relative_path)

        if child.is_symlink():
            message = f"Skipped symlinked Tray entry: {child}"
            warnings.append(message)
            signals.append(_signal("symlink_skipped", "high", message, path=relative_path))
            continue

        if child.name.startswith("._"):
            signals.append(
                _signal(
                    "appledouble_noise",
                    "low",
                    "AppleDouble sidecar file found in Tray.",
                    path=relative_path,
                )
            )
            continue

        if child.name.casefold().endswith(".icloud"):
            signals.append(
                _signal(
                    "icloud_placeholder",
                    "medium",
                    "iCloud placeholder or evicted file marker found in Tray.",
                    path=relative_path,
                )
            )
            continue

        if not child.is_file():
            signals.append(
                _signal(
                    "non_file_entry",
                    "low",
                    "Non-file entry found in Tray and ignored.",
                    path=relative_path,
                )
            )
            continue

        extension = child.suffix.lower()
        if extension not in TRAY_EXTENSIONS:
            continue

        payload = _tray_file_payload(child, root)
        tray_file_count += 1
        total_size_bytes += payload["size_bytes"]
        extension_counts[extension] = extension_counts.get(extension, 0) + 1
        modified_at = payload["modified_at"]
        if modified_at and (latest_modified_at is None or modified_at > latest_modified_at):
            latest_modified_at = modified_at

        group = groups.setdefault(
            child.stem,
            {
                "stem": child.stem,
                "files": [],
                "extensions": [],
                "total_size_bytes": 0,
                "latest_modified_at": None,
            },
        )
        group["files"].append(payload)
        group["extensions"].append(extension)
        group["total_size_bytes"] += payload["size_bytes"]
        if modified_at and (
            group["latest_modified_at"] is None or modified_at > group["latest_modified_at"]
        ):
            group["latest_modified_at"] = modified_at

    tray_groups = sorted(
        (_finalize_group(group) for group in groups.values()),
        key=lambda group: (not group["has_trayitem"], group["stem"].casefold()),
    )

    for group in tray_groups:
        file_paths = [item["relative_path"] for item in group["files"]]
        for dependency_signal in group["dependency_signals"]:
            signals.append(
                _signal(
                    dependency_signal["id"],
                    dependency_signal["severity"],
                    dependency_signal["message"],
                    paths=file_paths,
                )
            )

    signals.extend(detect_case_collisions(relative_paths))
    anchored_group_count = sum(1 for group in tray_groups if group["has_trayitem"])
    sidecar_only_group_count = len(tray_groups) - anchored_group_count

    if tray_file_count or signals:
        status = "review_recommended"
        recommendations = [
            "Treat Tray dependency signals as read-only evidence, not deletion instructions.",
            "Back up the Tray folder before moving lots, rooms, or households between profiles.",
            "Sidecar-only groups need manual review because their .trayitem anchor is absent.",
        ]
    else:
        status = "no_tray_files_found"
        recommendations = ["No Sims 4 Tray files were found in the selected Tray directory."]

    return {
        "status": status,
        "root_path": str(root),
        "tray_path": str(tray_dir),
        "tray_file_count": tray_file_count,
        "group_count": len(tray_groups),
        "anchored_group_count": anchored_group_count,
        "sidecar_only_group_count": sidecar_only_group_count,
        "total_size_bytes": total_size_bytes,
        "latest_modified_at": latest_modified_at,
        "extension_counts": dict(sorted(extension_counts.items())),
        "groups": tray_groups,
        "signals": signals,
        "warnings": warnings,
        "recommendations": recommendations,
        "mutates_files": False,
    }


def format_tray_status_text(status: dict[str, Any]) -> str:
    """Format Tray dependency status for terminal review."""
    lines = [
        "Tray Protector",
        f"Status: {status.get('status', 'unknown')}",
        f"Root: {status.get('root_path', 'unknown')}",
        f"Tray: {status.get('tray_path', 'unknown')}",
        "Read-only: yes",
        f"Tray files: {status.get('tray_file_count', 0)}",
        f"Groups: {status.get('group_count', 0)}",
        f"Anchored groups: {status.get('anchored_group_count', 0)}",
        f"Sidecar-only groups: {status.get('sidecar_only_group_count', 0)}",
        f"Total size: {status.get('total_size_bytes', 0)} bytes",
    ]

    groups = status.get("groups") or []
    if groups:
        lines.append("")
        lines.append("Tray groups:")
        for group in groups:
            anchor = "anchored" if group.get("has_trayitem") else "sidecar only"
            lines.append(
                f"- {group.get('stem', 'unknown')}: {anchor}, "
                f"{group.get('file_count', 0)} file(s), {group.get('type_hint', 'unknown')}"
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
