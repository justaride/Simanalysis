"""Manifest-backed safe fix actions."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, cast

from simanalysis.treatment import assert_sims_not_running, timestamp_for, utc_now
from simanalysis.world import CACHE_DIR_NAMES, CACHE_FILE_NAMES

FIX_ROOT_NAME = "_Simanalysis_Fixes"
CACHE_BACKUP_PREFIX = "_CacheCleanup_"
VALID_FIX_KINDS = {"cache_cleanup"}
VALID_FIX_STATUSES = {"applied", "restored", "blocked"}


def apply_cache_cleanup(sims4_dir: str | Path) -> dict[str, Any]:
    """Move known cache artifacts to a Simanalysis-owned backup folder."""
    assert_sims_not_running()
    base = _require_sims_dir(sims4_dir)
    cache_paths = _cache_paths(base)
    if not cache_paths:
        raise ValueError("No cache cleanup candidates found")

    now = utc_now()
    ts = timestamp_for(now)
    backup_dir = base / FIX_ROOT_NAME / f"{CACHE_BACKUP_PREFIX}{ts}"
    session_id = f"cache-cleanup-{ts}"
    manifest_path = base / FIX_ROOT_NAME / f"{session_id}.json"
    records = [
        {
            "source": str(path),
            "destination": str(backup_dir / path.name),
            "kind": "folder" if path.is_dir() else "file",
            "status": "pending",
        }
        for path in cache_paths
    ]
    session = {
        "version": 1,
        "session_id": session_id,
        "kind": "cache_cleanup",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "sims4_dir": str(base),
        "backup_dir": str(backup_dir),
        "manifest_path": str(manifest_path),
        "status": "applied",
        "records": records,
        "warnings": [],
        "blockers": [],
    }
    _write_session(session)

    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        for record in records:
            source = Path(str(record["source"]))
            destination = Path(str(record["destination"]))
            _assert_safe_cache_move(base, backup_dir, source, destination)
            record["status"] = "moving"
            _write_session(session)
            shutil.move(str(source), str(destination))
            record["status"] = "moved"
            _write_session(session)
    except Exception:
        session["status"] = "blocked"
        _write_session(session)
        raise

    return _save_loaded(session)


def restore_fix_session(manifest_path: str | Path) -> dict[str, Any]:
    """Restore files moved by a Simanalysis fix manifest."""
    assert_sims_not_running()
    session = load_fix_session(manifest_path)
    if session["kind"] != "cache_cleanup":
        raise ValueError(f"Unsupported fix kind: {session['kind']}")
    base = Path(str(session["sims4_dir"]))
    backup_dir = Path(str(session["backup_dir"]))

    try:
        for record in session["records"]:
            if record.get("status") == "restored":
                continue
            source = Path(str(record["destination"]))
            destination = Path(str(record["source"]))
            _assert_safe_cache_restore(base, backup_dir, source, destination)
            shutil.move(str(source), str(destination))
            record["status"] = "restored"
            _write_session(session)
    except Exception:
        session["status"] = "blocked"
        _write_session(session)
        raise

    session["status"] = "restored"
    return _save_loaded(session)


def load_fix_session(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Fix manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Fix manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Fix manifest must be a JSON object")
    data = cast(dict[str, Any], parsed)
    _validate_session(data)
    data["manifest_path"] = str(path)
    return data


def _validate_session(data: dict[str, Any]) -> None:
    if data.get("version") != 1:
        raise ValueError("Unsupported fix manifest version")
    for key in ("session_id", "kind", "sims4_dir", "backup_dir", "status"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"Fix manifest field {key} must be a string")
    if data["kind"] not in VALID_FIX_KINDS:
        raise ValueError(f"Unsupported fix kind: {data['kind']}")
    if data["status"] not in VALID_FIX_STATUSES:
        raise ValueError(f"Unknown fix status: {data['status']}")
    for key in ("records", "warnings", "blockers"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"Fix manifest field {key} must be a list")
    base = _logical_absolute(data["sims4_dir"])
    backup = _logical_absolute(data["backup_dir"])
    try:
        rel = backup.relative_to(base / FIX_ROOT_NAME)
    except ValueError as exc:
        raise ValueError("Fix backup folder must be under _Simanalysis_Fixes") from exc
    if len(rel.parts) != 1 or not backup.name.startswith(CACHE_BACKUP_PREFIX):
        raise ValueError("Fix backup folder must be a direct cache cleanup backup folder")


def _cache_paths(base: Path) -> list[Path]:
    paths: list[Path] = []
    for child in sorted(base.iterdir(), key=lambda item: item.name.casefold()):
        normalized = child.name.casefold()
        is_supported_cache = (child.is_file() and normalized in CACHE_FILE_NAMES) or (
            child.is_dir() and normalized in CACHE_DIR_NAMES
        )
        if is_supported_cache:
            paths.append(child.resolve())
    return paths


def _assert_safe_cache_move(base: Path, backup_dir: Path, source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.expanduser()
    if source.is_symlink() or source.parent.is_symlink():
        raise ValueError(f"Cache source must not be a symlink: {source}")
    if destination.exists():
        raise ValueError(f"Fix destination already exists: {destination}")
    if source.parent != base:
        raise ValueError(f"Cache source must be a direct child of Sims 4 folder: {source}")
    normalized = source.name.casefold()
    if not (
        (source.is_file() and normalized in CACHE_FILE_NAMES)
        or (source.is_dir() and normalized in CACHE_DIR_NAMES)
    ):
        raise ValueError(f"Unsupported cache cleanup source: {source}")
    if destination.parent != backup_dir:
        raise ValueError(f"Fix destination must be a direct child of backup folder: {destination}")


def _assert_safe_cache_restore(
    base: Path,
    backup_dir: Path,
    source: Path,
    destination: Path,
) -> None:
    source = source.resolve()
    destination = destination.expanduser()
    if not source.exists():
        raise ValueError(f"Restore source is missing: {source}")
    if source.is_symlink() or source.parent.is_symlink():
        raise ValueError(f"Restore source must not be a symlink: {source}")
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}")
    if source.parent != backup_dir:
        raise ValueError(f"Restore source must be a direct child of backup folder: {source}")
    if destination.parent != base:
        raise ValueError(f"Restore destination must be a direct child of Sims 4 folder: {destination}")


def _require_sims_dir(path: str | Path) -> Path:
    base = Path(path).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Invalid Sims 4 directory path: {path}")
    return base


def _save_loaded(session: dict[str, Any]) -> dict[str, Any]:
    session["updated_at"] = utc_now().isoformat().replace("+00:00", "Z")
    return _write_session(session)


def _write_session(session: dict[str, Any]) -> dict[str, Any]:
    path = Path(session["manifest_path"])
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
            tmp.write(json.dumps(session, indent=2))
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return session


def _logical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(Path(path).expanduser()))
