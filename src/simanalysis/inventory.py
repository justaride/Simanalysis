"""Persistent read-only Sims 4 folder inventory."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simanalysis.parsers.dbpf import DBPFReader

APP_DATA_DIR = Path.home() / ".simanalysis"
DEFAULT_DB_PATH = APP_DATA_DIR / "inventory.sqlite3"
SCHEMA_VERSION = "1"

GENERATED_DIR_NAMES = {
    ".modguardian",
    ".simanalysis",
    "_Simanalysis_Treatment",
}
MOD_PACKAGE_ROOTS = (
    "Mods",
    "_Disabled",
    "_Disabled_Mods",
    "_Quarantine",
    "_Simanalysis_Quarantine",
)
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
KNOWN_EXTENSIONS = {
    ".package",
    ".ts4script",
    ".zip",
    ".rar",
    ".7z",
    ".save",
    ".ver",
    ".trayitem",
    ".blueprint",
    ".bpi",
    ".hhi",
    ".sgi",
    ".householdbinary",
    ".room",
    ".ini",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".mp4",
    ".avi",
}


@dataclass(frozen=True)
class FileFact:
    """A file observed during one inventory scan."""

    abs_path: Path
    rel_path: str
    filename: str
    extension: str
    size_bytes: int
    mtime_ns: int
    sha256: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_root(root_path: str | Path) -> Path:
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Invalid directory path: {root_path}")
    return root


def _resolve_db_path(db_path: str | Path | None) -> Path:
    path = Path(db_path).expanduser().resolve() if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rel_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _should_skip_dir(name: str) -> bool:
    return name in GENERATED_DIR_NAMES


def _collect_files(root: Path, warnings: list[str]) -> list[FileFact]:
    facts: list[FileFact] = []
    for current_root, dir_names, file_names in os.walk(root, followlinks=False):
        dir_names[:] = sorted(name for name in dir_names if not _should_skip_dir(name))
        current = Path(current_root)
        for filename in sorted(file_names):
            path = current / filename
            rel_path = _rel_path(root, path)
            if path.is_symlink():
                warnings.append(f"{rel_path}: symlink skipped")
                continue
            try:
                stat = path.stat()
                if not path.is_file():
                    continue
                facts.append(
                    FileFact(
                        abs_path=path.resolve(),
                        rel_path=rel_path,
                        filename=path.name,
                        extension=path.suffix.lower(),
                        size_bytes=stat.st_size,
                        mtime_ns=stat.st_mtime_ns,
                        sha256=_sha256(path),
                    )
                )
            except OSError as exc:
                warnings.append(f"{rel_path}: {exc}")
    return sorted(facts, key=lambda fact: fact.rel_path)


def _should_parse_package(fact: FileFact) -> bool:
    if fact.extension != ".package":
        return False
    first_part = fact.rel_path.split("/", 1)[0]
    return first_part in MOD_PACKAGE_ROOTS


def _resource_key(type_id: int, group_id: int, instance_id: int) -> str:
    return f"{type_id:08X}:{group_id:08X}:{instance_id:016X}"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roots (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL,
            file_count INTEGER NOT NULL DEFAULT 0,
            warnings_json TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY(root_id) REFERENCES roots(id)
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL,
            scan_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            file_count INTEGER NOT NULL,
            total_size_bytes INTEGER NOT NULL,
            summary_json TEXT NOT NULL,
            FOREIGN KEY(root_id) REFERENCES roots(id),
            FOREIGN KEY(scan_id) REFERENCES scans(id)
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL,
            abs_path TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            extension TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            first_seen_scan_id INTEGER NOT NULL,
            last_seen_scan_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(root_id, rel_path),
            FOREIGN KEY(root_id) REFERENCES roots(id)
        );

        CREATE TABLE IF NOT EXISTS packages (
            file_id INTEGER PRIMARY KEY,
            parse_status TEXT NOT NULL,
            parse_error TEXT,
            resource_count INTEGER NOT NULL,
            has_compression INTEGER NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL,
            type_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            instance_id TEXT NOT NULL,
            resource_key TEXT NOT NULL,
            offset INTEGER NOT NULL,
            compressed_size INTEGER NOT NULL,
            uncompressed_size INTEGER NOT NULL,
            compression_type TEXT NOT NULL,
            FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS file_events (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL,
            scan_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            file_id INTEGER,
            rel_path TEXT NOT NULL,
            old_rel_path TEXT,
            sha256 TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY(root_id) REFERENCES roots(id),
            FOREIGN KEY(scan_id) REFERENCES scans(id),
            FOREIGN KEY(file_id) REFERENCES files(id)
        );
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (SCHEMA_VERSION,),
    )


def _lastrowid(cursor: sqlite3.Cursor) -> int:
    row_id = cursor.lastrowid
    if row_id is None:
        raise RuntimeError("SQLite insert did not return a row id")
    return row_id


def _root_id(conn: sqlite3.Connection, root: Path) -> int:
    root_string = str(root)
    row = conn.execute("SELECT id FROM roots WHERE path = ?", (root_string,)).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute(
        "INSERT INTO roots(path, created_at) VALUES(?, ?)",
        (root_string, _now()),
    )
    return _lastrowid(cursor)


def _start_scan(conn: sqlite3.Connection, root_id: int) -> int:
    cursor = conn.execute(
        "INSERT INTO scans(root_id, started_at, status) VALUES(?, ?, ?)",
        (root_id, _now(), "running"),
    )
    return _lastrowid(cursor)


def _active_file_rows(conn: sqlite3.Connection, root_id: int) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT *
        FROM files
        WHERE root_id = ? AND status = 'active'
        """,
        (root_id,),
    ).fetchall()
    return {str(row["rel_path"]): row for row in rows}


def _insert_file(conn: sqlite3.Connection, root_id: int, scan_id: int, fact: FileFact) -> int:
    cursor = conn.execute(
        """
        INSERT INTO files(
            root_id, abs_path, rel_path, filename, extension, size_bytes, mtime_ns,
            sha256, first_seen_scan_id, last_seen_scan_id, status
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            root_id,
            str(fact.abs_path),
            fact.rel_path,
            fact.filename,
            fact.extension,
            fact.size_bytes,
            fact.mtime_ns,
            fact.sha256,
            scan_id,
            scan_id,
        ),
    )
    return _lastrowid(cursor)


def _update_file(conn: sqlite3.Connection, file_id: int, scan_id: int, fact: FileFact) -> None:
    conn.execute(
        """
        UPDATE files
        SET abs_path = ?,
            rel_path = ?,
            filename = ?,
            extension = ?,
            size_bytes = ?,
            mtime_ns = ?,
            sha256 = ?,
            last_seen_scan_id = ?,
            status = 'active'
        WHERE id = ?
        """,
        (
            str(fact.abs_path),
            fact.rel_path,
            fact.filename,
            fact.extension,
            fact.size_bytes,
            fact.mtime_ns,
            fact.sha256,
            scan_id,
            file_id,
        ),
    )


def _mark_removed(conn: sqlite3.Connection, file_id: int) -> None:
    conn.execute("UPDATE files SET status = 'removed' WHERE id = ?", (file_id,))


def _record_event(
    conn: sqlite3.Connection,
    root_id: int,
    scan_id: int,
    event_type: str,
    rel_path: str,
    sha256: str,
    file_id: int | None = None,
    old_rel_path: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_payload = payload or {}
    cursor = conn.execute(
        """
        INSERT INTO file_events(
            root_id, scan_id, event_type, file_id, rel_path, old_rel_path, sha256, payload_json
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            root_id,
            scan_id,
            event_type,
            file_id,
            rel_path,
            old_rel_path,
            sha256,
            json.dumps(event_payload, sort_keys=True),
        ),
    )
    return {
        "id": _lastrowid(cursor),
        "event_type": event_type,
        "file_id": file_id,
        "rel_path": rel_path,
        "old_rel_path": old_rel_path,
        "sha256": sha256,
        "payload": event_payload,
    }


def _delete_package_details(conn: sqlite3.Connection, file_id: int) -> None:
    conn.execute("DELETE FROM resources WHERE file_id = ?", (file_id,))
    conn.execute("DELETE FROM packages WHERE file_id = ?", (file_id,))


def _parse_package(fact: FileFact) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        reader = DBPFReader(fact.abs_path)
        resources = reader.read_index()
    except Exception as exc:
        return (
            {
                "rel_path": fact.rel_path,
                "parse_status": "error",
                "parse_error": f"DBPF parse error: {exc}",
                "resource_count": 0,
                "has_compression": False,
            },
            [],
        )

    resource_payloads = []
    for resource in resources:
        compressed = resource.is_compressed
        type_id = f"{resource.type:08X}"
        group_id = f"{resource.group:08X}"
        instance_id = f"{resource.instance:016X}"
        resource_payloads.append(
            {
                "type_id": type_id,
                "group_id": group_id,
                "instance_id": instance_id,
                "resource_key": _resource_key(resource.type, resource.group, resource.instance),
                "offset": resource.offset,
                "compressed_size": resource.compressed_size,
                "uncompressed_size": resource.size,
                "compression_type": "zlib" if compressed else "none",
            }
        )

    return (
        {
            "rel_path": fact.rel_path,
            "parse_status": "ok",
            "parse_error": None,
            "resource_count": len(resource_payloads),
            "has_compression": any(resource.is_compressed for resource in resources),
        },
        resource_payloads,
    )


def _store_package_details(
    conn: sqlite3.Connection,
    file_id: int,
    package_payload: dict[str, Any],
    resources: list[dict[str, Any]],
) -> None:
    _delete_package_details(conn, file_id)
    conn.execute(
        """
        INSERT INTO packages(file_id, parse_status, parse_error, resource_count, has_compression)
        VALUES(?, ?, ?, ?, ?)
        """,
        (
            file_id,
            package_payload["parse_status"],
            package_payload["parse_error"],
            package_payload["resource_count"],
            int(bool(package_payload["has_compression"])),
        ),
    )
    conn.executemany(
        """
        INSERT INTO resources(
            file_id, type_id, group_id, instance_id, resource_key, offset,
            compressed_size, uncompressed_size, compression_type
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                file_id,
                resource["type_id"],
                resource["group_id"],
                resource["instance_id"],
                resource["resource_key"],
                resource["offset"],
                resource["compressed_size"],
                resource["uncompressed_size"],
                resource["compression_type"],
            )
            for resource in resources
        ],
    )


def _file_payload(file_id: int, fact: FileFact, status: str) -> dict[str, Any]:
    return {
        "id": file_id,
        "abs_path": str(fact.abs_path),
        "rel_path": fact.rel_path,
        "filename": fact.filename,
        "extension": fact.extension,
        "size_bytes": fact.size_bytes,
        "mtime_ns": fact.mtime_ns,
        "sha256": fact.sha256,
        "status": status,
    }


def _summary(
    root: Path,
    facts: list[FileFact],
    events: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    statuses: dict[str, str],
) -> dict[str, Any]:
    extensions = [fact.extension for fact in facts]
    event_counts = {
        "added_count": 0,
        "removed_count": 0,
        "modified_count": 0,
        "moved_count": 0,
        "unchanged_count": 0,
    }
    for event in events:
        key = f"{event['event_type']}_count"
        if key in event_counts:
            event_counts[key] += 1
    event_counts["unchanged_count"] = sum(
        1 for fact in facts if statuses.get(fact.rel_path) == "unchanged"
    )

    return {
        "root_path": str(root),
        "file_count": len(facts),
        "package_count": extensions.count(".package"),
        "script_count": extensions.count(".ts4script"),
        "archive_count": sum(1 for extension in extensions if extension in ARCHIVE_EXTENSIONS),
        "unknown_extension_count": sum(
            1 for extension in extensions if extension and extension not in KNOWN_EXTENSIONS
        ),
        "total_size_bytes": sum(fact.size_bytes for fact in facts),
        **event_counts,
        "package_parse_ok_count": sum(1 for package in packages if package["parse_status"] == "ok"),
        "package_parse_error_count": sum(
            1 for package in packages if package["parse_status"] == "error"
        ),
        "resource_count": len(resources),
    }


def _snapshot(
    conn: sqlite3.Connection,
    root_id: int,
    scan_id: int,
    summary: dict[str, Any],
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO snapshots(
            root_id, scan_id, created_at, file_count, total_size_bytes, summary_json
        )
        VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            root_id,
            scan_id,
            _now(),
            summary["file_count"],
            summary["total_size_bytes"],
            json.dumps(summary, sort_keys=True),
        ),
    )
    return _lastrowid(cursor)


def _finish_scan(
    conn: sqlite3.Connection,
    scan_id: int,
    file_count: int,
    warnings: list[str],
    status: str = "completed",
) -> None:
    conn.execute(
        """
        UPDATE scans
        SET completed_at = ?, status = ?, file_count = ?, warnings_json = ?
        WHERE id = ?
        """,
        (_now(), status, file_count, json.dumps(warnings, sort_keys=True), scan_id),
    )


def _write_export(export_path: Path, payload: dict[str, Any]) -> None:
    export_path = export_path.expanduser().resolve()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    export_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def run_inventory_scan(
    root_path: str | Path,
    db_path: str | Path | None = None,
    export_path: str | Path | None = None,
) -> dict[str, Any]:
    """Scan a Sims 4 user folder and persist a read-only local inventory."""

    root = _resolve_root(root_path)
    resolved_db = _resolve_db_path(db_path)
    resolved_export = Path(export_path).expanduser().resolve() if export_path else None
    warnings: list[str] = []
    facts = _collect_files(root, warnings)
    current_by_rel = {fact.rel_path: fact for fact in facts}
    files_payload: list[dict[str, Any]] = []
    package_payloads: list[dict[str, Any]] = []
    resource_payloads: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    with _connect(resolved_db) as conn:
        _ensure_schema(conn)
        root_id = _root_id(conn, root)
        scan_id = _start_scan(conn, root_id)
        previous_by_rel = _active_file_rows(conn, root_id)
        missing_rels = set(previous_by_rel) - set(current_by_rel)
        new_rels = set(current_by_rel) - set(previous_by_rel)
        missing_by_sha: dict[str, list[sqlite3.Row]] = {}
        for rel_path in sorted(missing_rels):
            row = previous_by_rel[rel_path]
            missing_by_sha.setdefault(str(row["sha256"]), []).append(row)
        moved_new_rels: set[str] = set()
        moved_old_rels: set[str] = set()

        for rel_path in sorted(new_rels):
            fact = current_by_rel[rel_path]
            candidates = missing_by_sha.get(fact.sha256, [])
            if not candidates:
                continue
            previous = candidates.pop(0)
            old_rel_path = str(previous["rel_path"])
            file_id = int(previous["id"])
            _update_file(conn, file_id, scan_id, fact)
            moved_new_rels.add(rel_path)
            moved_old_rels.add(old_rel_path)
            events.append(
                _record_event(
                    conn,
                    root_id,
                    scan_id,
                    "moved",
                    fact.rel_path,
                    fact.sha256,
                    file_id=file_id,
                    old_rel_path=old_rel_path,
                )
            )

        for rel_path in sorted(missing_rels - moved_old_rels):
            previous = previous_by_rel[rel_path]
            file_id = int(previous["id"])
            _mark_removed(conn, file_id)
            events.append(
                _record_event(
                    conn,
                    root_id,
                    scan_id,
                    "removed",
                    rel_path,
                    str(previous["sha256"]),
                    file_id=file_id,
                )
            )

        current_file_ids: dict[str, int] = {}
        current_statuses: dict[str, str] = {}
        for fact in facts:
            previous_row = previous_by_rel.get(fact.rel_path)
            if fact.rel_path in moved_new_rels:
                file_id = int(
                    conn.execute(
                        "SELECT id FROM files WHERE root_id = ? AND rel_path = ?",
                        (root_id, fact.rel_path),
                    ).fetchone()["id"]
                )
                current_statuses[fact.rel_path] = "moved"
            elif previous_row is None:
                file_id = _insert_file(conn, root_id, scan_id, fact)
                events.append(
                    _record_event(
                        conn,
                        root_id,
                        scan_id,
                        "added",
                        fact.rel_path,
                        fact.sha256,
                        file_id=file_id,
                    )
                )
                current_statuses[fact.rel_path] = "added"
            else:
                file_id = int(previous_row["id"])
                if str(previous_row["sha256"]) == fact.sha256:
                    event_type = "unchanged"
                else:
                    event_type = "modified"
                    events.append(
                        _record_event(
                            conn,
                            root_id,
                            scan_id,
                            event_type,
                            fact.rel_path,
                            fact.sha256,
                            file_id=file_id,
                            payload={"previous_sha256": str(previous_row["sha256"])},
                        )
                    )
                _update_file(conn, file_id, scan_id, fact)
                current_statuses[fact.rel_path] = event_type
            current_file_ids[fact.rel_path] = file_id

        for fact in facts:
            file_id = current_file_ids[fact.rel_path]
            status = current_statuses.get(fact.rel_path, "unchanged")
            files_payload.append(_file_payload(file_id, fact, status))
            if _should_parse_package(fact):
                package_payload, resources = _parse_package(fact)
                package_payload["file_id"] = file_id
                package_payloads.append(package_payload)
                for resource in resources:
                    resource["file_id"] = file_id
                    resource["package_rel_path"] = fact.rel_path
                resource_payloads.extend(resources)
                _store_package_details(conn, file_id, package_payload, resources)
            elif fact.extension != ".package":
                _delete_package_details(conn, file_id)

        summary = _summary(
            root, facts, events, package_payloads, resource_payloads, current_statuses
        )
        snapshot_id = _snapshot(conn, root_id, scan_id, summary)
        _finish_scan(conn, scan_id, len(facts), warnings)

        result: dict[str, Any] = {
            "database_path": str(resolved_db),
            "export_path": str(resolved_export) if resolved_export else None,
            "scan_id": scan_id,
            "snapshot_id": snapshot_id,
            "summary": summary,
            "warnings": warnings,
            "files": sorted(files_payload, key=lambda file: str(file["rel_path"])),
            "packages": sorted(package_payloads, key=lambda package: str(package["rel_path"])),
            "resources": sorted(
                resource_payloads,
                key=lambda resource: (
                    str(resource["package_rel_path"]),
                    str(resource["resource_key"]),
                ),
            ),
            "events": events,
        }
        if resolved_export:
            _write_export(resolved_export, result)
        return result
