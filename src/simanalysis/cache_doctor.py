"""Read-only Cache Doctor status for Sims 4 user folders."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_TARGETS: tuple[dict[str, str], ...] = (
    {
        "id": "localthumbcache",
        "relative_path": "localthumbcache.package",
        "kind": "file",
        "label": "Local thumbnail cache",
        "risk": "medium",
        "reason": "Can retain stale thumbnails and CAS/build-buy previews after mod or patch changes.",
    },
    {
        "id": "avatarcache",
        "relative_path": "avatarcache.package",
        "kind": "file",
        "label": "Avatar cache",
        "risk": "low",
        "reason": "Can retain stale Sim portrait data; usually safe to review after UI or CAS issues.",
    },
    {
        "id": "cache_dir",
        "relative_path": "cache",
        "kind": "directory",
        "label": "Cache directory",
        "risk": "medium",
        "reason": "General game cache directory that can contain stale generated data.",
    },
    {
        "id": "cachestr_dir",
        "relative_path": "cachestr",
        "kind": "directory",
        "label": "String cache directory",
        "risk": "medium",
        "reason": "Can retain cached strings after tuning, STBL, or language-content changes.",
    },
    {
        "id": "onlinethumbnailcache_dir",
        "relative_path": "onlinethumbnailcache",
        "kind": "directory",
        "label": "Online thumbnail cache",
        "risk": "low",
        "reason": "Thumbnail cache directory; usually cosmetic but useful during visual cache review.",
    },
    {
        "id": "cachewebkit_dir",
        "relative_path": "cachewebkit",
        "kind": "directory",
        "label": "WebKit cache directory",
        "risk": "low",
        "reason": "Embedded web/UI cache directory; review only when UI/cache symptoms support it.",
    },
)


def _modified_at(path: Path) -> str | None:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _directory_stats(path: Path, warnings: list[str]) -> tuple[int, int]:
    size_bytes = 0
    item_count = 0
    for child in path.rglob("*"):
        if child.is_symlink():
            warnings.append(f"Skipped symlinked cache entry: {child}")
            continue
        item_count += 1
        if child.is_file():
            try:
                size_bytes += child.stat().st_size
            except OSError as exc:
                warnings.append(f"Could not stat cache entry {child}: {exc}")
    return size_bytes, item_count


def _absent_target(root: Path, target: dict[str, str]) -> dict[str, Any]:
    absolute_path = root / target["relative_path"]
    return {
        **target,
        "path": str(absolute_path),
        "present": False,
        "status": "absent",
        "size_bytes": 0,
        "item_count": 0,
        "modified_at": None,
    }


def build_cache_status(sims4_dir: Path | str) -> dict[str, Any]:
    """Inspect known Sims 4 cache targets without mutating the selected folder."""
    root = Path(sims4_dir).expanduser().resolve()
    warnings: list[str] = []
    targets: list[dict[str, Any]] = []

    for target in CACHE_TARGETS:
        absolute_path = root / target["relative_path"]
        if not absolute_path.exists():
            targets.append(_absent_target(root, target))
            continue

        if absolute_path.is_symlink():
            warnings.append(f"Skipped symlinked cache target: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "skipped_symlink"
            targets.append(skipped)
            continue

        expected_kind = target["kind"]
        if expected_kind == "file" and not absolute_path.is_file():
            warnings.append(f"Cache target had unexpected type: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "unexpected_type"
            targets.append(skipped)
            continue
        if expected_kind == "directory" and not absolute_path.is_dir():
            warnings.append(f"Cache target had unexpected type: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "unexpected_type"
            targets.append(skipped)
            continue

        if expected_kind == "directory":
            size_bytes, item_count = _directory_stats(absolute_path, warnings)
        else:
            size_bytes = absolute_path.stat().st_size
            item_count = 1

        targets.append(
            {
                **target,
                "path": str(absolute_path),
                "present": True,
                "status": "present",
                "size_bytes": size_bytes,
                "item_count": item_count,
                "modified_at": _modified_at(absolute_path),
            }
        )

    present = [target for target in targets if target["present"]]
    if present:
        recommendations = [
            "Review listed cache targets before deleting anything.",
            "Future cache cleanup should be staged through an Operating Table manifest after snapshot approval.",
            "Close The Sims 4 before any future cache-clearing operation.",
        ]
        status = "review_recommended"
    else:
        recommendations = ["No known Sims 4 cache targets were found in the selected folder."]
        status = "no_cache_targets_found"

    return {
        "status": status,
        "root_path": str(root),
        "targets": targets,
        "present_count": len(present),
        "total_size_bytes": sum(target["size_bytes"] for target in present),
        "warnings": warnings,
        "recommendations": recommendations,
        "mutates_files": False,
    }


def format_cache_status_text(status: dict[str, Any]) -> str:
    """Format Cache Doctor status for terminal review."""
    lines = [
        "Cache Doctor",
        f"Status: {status.get('status', 'unknown')}",
        f"Root: {status.get('root_path', 'unknown')}",
        "Read-only: yes",
        f"Present targets: {status.get('present_count', 0)}",
        f"Total size: {status.get('total_size_bytes', 0)} bytes",
    ]

    targets = status.get("targets") or []
    present_targets = [target for target in targets if target.get("present")]
    if present_targets:
        lines.append("")
        lines.append("Cache targets:")
        for target in present_targets:
            lines.append(
                f"- {target.get('relative_path')}: {target.get('size_bytes', 0)} bytes, "
                f"{target.get('item_count', 0)} item(s), risk {target.get('risk', 'unknown')}"
            )

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
