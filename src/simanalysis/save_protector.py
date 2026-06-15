"""Read-only Save Protector status for Sims 4 user folders."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAVE_PATTERN = re.compile(r"^(?P<slot>.+)\.save(?P<backup>\.ver\d+)?$", re.IGNORECASE)


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


def _save_file_payload(path: Path, saves_dir: Path) -> dict[str, Any]:
    relative_path = path.relative_to(saves_dir.parent).as_posix()
    return {
        "name": path.name,
        "relative_path": relative_path,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "modified_at": _modified_at(path),
    }


def _save_identity(path: Path) -> tuple[str, bool] | None:
    match = SAVE_PATTERN.match(path.name)
    if not match:
        return None
    return match.group("slot"), bool(match.group("backup"))


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
                "Multiple save paths differ only by case or Unicode casefolding.",
                paths=unique_paths,
            )
        )
    return signals


def _missing_saves_status(root: Path, saves_dir: Path) -> dict[str, Any]:
    message = "The selected Sims 4 folder does not contain a saves directory."
    return {
        "status": "missing_saves_folder",
        "root_path": str(root),
        "saves_path": str(saves_dir),
        "primary_save_count": 0,
        "backup_count": 0,
        "orphan_backup_count": 0,
        "total_size_bytes": 0,
        "latest_modified_at": None,
        "save_groups": [],
        "signals": [_signal("missing_saves_folder", "medium", message, path=saves_dir.as_posix())],
        "warnings": [message],
        "recommendations": [
            "Choose the Sims 4 user folder that contains saves if you want save protection status."
        ],
        "mutates_files": False,
    }


def build_save_protector_status(sims4_dir: Path | str) -> dict[str, Any]:
    """Inspect Sims 4 save files without editing saves or writing manifests."""
    root = Path(sims4_dir).expanduser().resolve()
    saves_dir = root / "saves"
    if not saves_dir.exists() or not saves_dir.is_dir():
        return _missing_saves_status(root, saves_dir)

    warnings: list[str] = []
    signals: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    relative_paths: list[str] = []
    latest_modified_at: str | None = None
    total_size_bytes = 0
    primary_save_count = 0
    backup_count = 0

    for child in sorted(saves_dir.iterdir(), key=lambda item: item.name.casefold()):
        relative_path = child.relative_to(root).as_posix()
        relative_paths.append(relative_path)

        if child.is_symlink():
            message = f"Skipped symlinked save entry: {child}"
            warnings.append(message)
            signals.append(_signal("symlink_skipped", "high", message, path=relative_path))
            continue

        if child.name.startswith("._"):
            signals.append(
                _signal(
                    "appledouble_noise",
                    "low",
                    "AppleDouble sidecar file found in saves.",
                    path=relative_path,
                )
            )
            continue

        if child.name.casefold().endswith(".icloud"):
            signals.append(
                _signal(
                    "icloud_placeholder",
                    "medium",
                    "iCloud placeholder or evicted file marker found in saves.",
                    path=relative_path,
                )
            )
            continue

        if not child.is_file():
            signals.append(
                _signal(
                    "non_file_entry",
                    "low",
                    "Non-file entry found in saves and ignored.",
                    path=relative_path,
                )
            )
            continue

        identity = _save_identity(child)
        if identity is None:
            continue

        slot, is_backup = identity
        payload = _save_file_payload(child, saves_dir)
        total_size_bytes += payload["size_bytes"]
        modified_at = payload["modified_at"]
        if modified_at and (latest_modified_at is None or modified_at > latest_modified_at):
            latest_modified_at = modified_at

        group = groups.setdefault(
            slot,
            {
                "slot": slot,
                "primary": None,
                "backups": [],
                "backup_count": 0,
                "total_size_bytes": 0,
                "latest_modified_at": None,
            },
        )
        group["total_size_bytes"] += payload["size_bytes"]
        if modified_at and (
            group["latest_modified_at"] is None or modified_at > group["latest_modified_at"]
        ):
            group["latest_modified_at"] = modified_at

        if is_backup:
            backup_count += 1
            group["backups"].append(payload)
            group["backup_count"] += 1
        else:
            primary_save_count += 1
            group["primary"] = payload

    signals.extend(detect_case_collisions(relative_paths))

    save_groups = sorted(groups.values(), key=lambda group: group["slot"].casefold())
    orphan_backup_count = sum(1 for group in save_groups if group["primary"] is None)

    if primary_save_count or backup_count or signals:
        status = "review_recommended"
        recommendations = [
            "Make a manual save copy before patch-day testing or mod changes.",
            "Do not edit save files in Simanalysis v3; this surface is read-only.",
            "Future save-adjacent file operations must be staged separately and never rewrite saves.",
        ]
    else:
        status = "no_save_files_found"
        recommendations = ["No Sims 4 save files were found in the selected saves directory."]

    return {
        "status": status,
        "root_path": str(root),
        "saves_path": str(saves_dir),
        "primary_save_count": primary_save_count,
        "backup_count": backup_count,
        "orphan_backup_count": orphan_backup_count,
        "total_size_bytes": total_size_bytes,
        "latest_modified_at": latest_modified_at,
        "save_groups": save_groups,
        "signals": signals,
        "warnings": warnings,
        "recommendations": recommendations,
        "mutates_files": False,
    }


def format_save_protector_text(status: dict[str, Any]) -> str:
    """Format Save Protector status for terminal review."""
    lines = [
        "Save Protector",
        f"Status: {status.get('status', 'unknown')}",
        f"Root: {status.get('root_path', 'unknown')}",
        f"Saves: {status.get('saves_path', 'unknown')}",
        "Read-only: yes",
        f"Primary saves: {status.get('primary_save_count', 0)}",
        f"Backups: {status.get('backup_count', 0)}",
        f"Orphan backup groups: {status.get('orphan_backup_count', 0)}",
        f"Total size: {status.get('total_size_bytes', 0)} bytes",
    ]

    groups = status.get("save_groups") or []
    if groups:
        lines.append("")
        lines.append("Save groups:")
        for group in groups:
            primary = "primary present" if group.get("primary") else "no primary"
            lines.append(
                f"- {group.get('slot', 'unknown')}: {primary}, "
                f"{group.get('backup_count', 0)} backup(s)"
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
