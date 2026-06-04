"""Read-only Sims 4 world inventory for local recovery workflows."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

WorldStatus = Literal["active", "disabled", "quarantined", "archived"]

MOD_SUFFIXES = {".package", ".ts4script"}
TRAY_SUFFIXES = {
    ".bpi",
    ".blueprint",
    ".hhi",
    ".householdbinary",
    ".room",
    ".sgi",
    ".trayitem",
}
CACHE_FILE_NAMES = {
    "avatarcache.package",
    "localthumbcache.package",
    "notify.glob",
}
CACHE_DIR_NAMES = {
    "cache",
    "cachestr",
    "onlinethumbnailcache",
}
ARCHIVE_ROOT_NAMES = {
    "archive",
    "archives",
    "_archive",
    "_archives",
    "import_staging",
    "_import_staging",
    "simsanalysis_backups",
}
STATUS_ORDER: dict[WorldStatus, int] = {
    "active": 0,
    "disabled": 1,
    "quarantined": 2,
    "archived": 3,
}


def scan_world(sims4_dir: str | Path) -> dict[str, Any]:
    """Build a read-only inventory of the user's Sims 4 folder."""
    base = Path(sims4_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Invalid Sims 4 directory path: {sims4_dir}")

    warnings: list[str] = []
    mods_dir = base / "Mods"
    if not mods_dir.exists():
        warnings.append("Mods folder not found")

    units = _discover_units(base)
    game_state = _discover_game_state(base)

    package_files = sum(int(unit["package_count"]) for unit in units)
    script_files = sum(int(unit["script_count"]) for unit in units)
    summary = {
        "active_units": _count_units(units, "active"),
        "disabled_units": _count_units(units, "disabled"),
        "quarantined_units": _count_units(units, "quarantined"),
        "archived_units": _count_units(units, "archived"),
        "package_files": package_files,
        "script_files": script_files,
        "tray_files": len(game_state["tray"]),
        "save_files": len(game_state["saves"]),
        "log_files": len(game_state["logs"]),
        "cache_files": len(game_state["caches"]),
        "warnings": len(warnings),
    }

    return {
        "schema_version": 1,
        "sims4_dir": str(base),
        "summary": summary,
        "units": units,
        "game_state": game_state,
        "warnings": warnings,
    }


def world_status(sims4_dir: str | Path) -> dict[str, Any]:
    """Return the compact status view of a world scan."""
    world = scan_world(sims4_dir)
    return {
        "schema_version": world["schema_version"],
        "sims4_dir": world["sims4_dir"],
        "summary": world["summary"],
        "warnings": world["warnings"],
    }


def _count_units(units: list[dict[str, Any]], status: WorldStatus) -> int:
    return sum(1 for unit in units if unit["status"] == status)


def _discover_units(base: Path) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    mods_dir = base / "Mods"
    if mods_dir.exists() and mods_dir.is_dir():
        for child in _sorted_children(mods_dir):
            if child.is_file() and child.suffix.lower() in MOD_SUFFIXES:
                units.append(_build_unit(base, child, "active"))
            elif child.is_dir():
                status = _status_for_named_root(child.name, default="active")
                assert status is not None
                if _contains_mod_files(child):
                    units.append(_build_unit(base, child, status))

    for child in _sorted_children(base):
        if child == mods_dir or not child.is_dir():
            continue
        status = _status_for_named_root(child.name)
        if status is not None and _contains_mod_files(child):
            units.append(_build_unit(base, child, status))

    return sorted(
        units,
        key=lambda unit: (
            STATUS_ORDER[unit["status"]],
            str(unit["relative_path"]).casefold(),
        ),
    )


def _status_for_named_root(name: str, default: WorldStatus | None = None) -> WorldStatus | None:
    normalized = name.casefold()
    if normalized.startswith("_disabled"):
        return "disabled"
    if normalized.startswith("_quarantine"):
        return "quarantined"
    if normalized in ARCHIVE_ROOT_NAMES or normalized.startswith("_archive"):
        return "archived"
    return default


def _contains_mod_files(root: Path) -> bool:
    return any(True for _ in _iter_mod_files(root))


def _build_unit(base: Path, root: Path, status: WorldStatus) -> dict[str, Any]:
    files = list(_iter_mod_files(root))
    package_count = sum(1 for path in files if path.suffix.lower() == ".package")
    script_count = sum(1 for path in files if path.suffix.lower() == ".ts4script")
    file_records = [_file_record(base, path) for path in files]
    return {
        "unit_id": _unit_hash(base, root, status, files),
        "name": root.name,
        "kind": "file" if root.is_file() else "folder",
        "status": status,
        "path": str(root.resolve()),
        "relative_path": _relative_posix(base, root),
        "file_count": len(files),
        "package_count": package_count,
        "script_count": script_count,
        "total_size_bytes": sum(int(record["size_bytes"]) for record in file_records),
        "identity": {
            "sha256": _unit_hash(base, root, status, files),
            "basis": "relative-path-size-mtime-v1",
        },
        "files": file_records,
    }


def _iter_mod_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        if root.suffix.lower() in MOD_SUFFIXES:
            yield root.resolve()
        return

    for path in sorted(root.rglob("*"), key=lambda item: _relative_sort_key(root, item)):
        if path.is_file() and path.suffix.lower() in MOD_SUFFIXES:
            yield path.resolve()


def _file_record(base: Path, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path.resolve()),
        "relative_path": _relative_posix(base, path),
        "suffix": path.suffix.lower(),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _unit_hash(base: Path, root: Path, status: WorldStatus, files: list[Path]) -> str:
    digest = hashlib.sha256()
    digest.update(status.encode("utf-8"))
    digest.update(b"\0")
    digest.update(_relative_posix(base, root).encode("utf-8"))
    for path in files:
        stat = path.stat()
        digest.update(b"\0")
        digest.update(_relative_posix(base, path).encode("utf-8"))
        digest.update(b":")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b":")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()


def _discover_game_state(base: Path) -> dict[str, list[dict[str, str]]]:
    return {
        "tray": _named_paths(_iter_tray_files(base / "Tray")),
        "saves": _named_paths(_iter_save_files(base / "saves")),
        "logs": _discover_logs(base),
        "caches": _discover_caches(base),
    }


def _iter_tray_files(tray_dir: Path) -> Iterable[Path]:
    if not tray_dir.exists() or not tray_dir.is_dir():
        return []
    return (
        path.resolve()
        for path in sorted(tray_dir.rglob("*"), key=lambda item: _relative_sort_key(tray_dir, item))
        if path.is_file() and path.suffix.lower() in TRAY_SUFFIXES
    )


def _iter_save_files(saves_dir: Path) -> Iterable[Path]:
    if not saves_dir.exists() or not saves_dir.is_dir():
        return []
    return (
        path.resolve()
        for path in sorted(saves_dir.rglob("*"), key=lambda item: _relative_sort_key(saves_dir, item))
        if path.is_file() and ".save" in path.name.casefold()
    )


def _discover_logs(base: Path) -> list[dict[str, str]]:
    logs: list[dict[str, str]] = []
    for kind, pattern in (("script", "lastException*.txt"), ("ui", "lastUIException*.txt")):
        for path in sorted(base.glob(pattern), key=lambda item: item.name.casefold()):
            if path.is_file():
                logs.append({"kind": kind, "name": path.name, "path": str(path.resolve())})
    return logs


def _discover_caches(base: Path) -> list[dict[str, str]]:
    caches: list[dict[str, str]] = []
    for path in _sorted_children(base):
        normalized = path.name.casefold()
        if path.is_file() and normalized in CACHE_FILE_NAMES:
            caches.append({"kind": "file", "name": path.name, "path": str(path.resolve())})
        elif path.is_dir() and normalized in CACHE_DIR_NAMES:
            caches.append({"kind": "folder", "name": path.name, "path": str(path.resolve())})
    return caches


def _named_paths(paths: Iterable[Path]) -> list[dict[str, str]]:
    return [{"name": path.name, "path": str(path.resolve())} for path in paths]


def _sorted_children(path: Path) -> list[Path]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(path.iterdir(), key=lambda item: item.name.casefold())


def _relative_posix(base: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _relative_sort_key(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix().casefold()
    except ValueError:
        return path.as_posix().casefold()
