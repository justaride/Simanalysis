"""Read-only inventory ledger for Sims 4 folders."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from simanalysis.parsers.dbpf import DBPFReader

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class InventoryScanSummary:
    """Summary of one read-only inventory scan."""

    scan_id: int
    root_path: str
    files_total: int = 0
    packages_total: int = 0
    resources_total: int = 0
    package_parse_errors: int = 0
    added: int = 0
    removed: int = 0
    moved: int = 0
    modified: int = 0
    unchanged: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Convert the summary to a JSON-serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class _FileFingerprint:
    path: Path
    relative_path: str
    extension: str
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class _DiscoveryResult:
    fingerprints: list[_FileFingerprint]
    warnings: list[str]


@dataclass(frozen=True)
class _SnapshotFingerprint:
    relative_path: str
    size: int
    sha256: str


class InventoryStore:
    """SQLite store for scan history, files, package metadata, and events."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path).expanduser()

    def connect(self) -> sqlite3.Connection:
        """Open a SQLite connection after ensuring the schema exists."""
        self.initialize()
        return sqlite3.connect(self.db_path)

    def initialize(self) -> None:
        """Create the inventory schema if needed."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(_SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


class InventoryScanner:
    """Record a read-only snapshot of a Sims 4 folder into SQLite."""

    def __init__(self, db_path: Path | str) -> None:
        self.store = InventoryStore(db_path)

    def scan(self, root_path: Path | str) -> InventoryScanSummary:
        """Scan a Sims 4 folder without mutating its files."""
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Inventory root is not a directory: {root_path}")

        started_at = _utc_now()
        discovery = _discover_file_fingerprints(root, excluded_paths={self.store.db_path})
        fingerprints = discovery.fingerprints

        with self.store.connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            previous = _load_latest_snapshot(conn, root)
            changes = _classify_changes(previous, fingerprints)
            scan_id = _create_scan(conn, root, started_at)
            snapshot_id = _create_snapshot(conn, scan_id, root, started_at, len(fingerprints))

            packages_total = 0
            resources_total = 0
            package_parse_errors = 0
            warnings = list(discovery.warnings)

            for fingerprint in fingerprints:
                file_id = _upsert_file(conn, scan_id, root, fingerprint)
                conn.execute(
                    """
                    INSERT INTO snapshot_files (
                        snapshot_id, file_id, relative_path, size, mtime_ns, sha256,
                        change_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        file_id,
                        fingerprint.relative_path,
                        fingerprint.size,
                        fingerprint.mtime_ns,
                        fingerprint.sha256,
                        changes.status_by_relative_path[fingerprint.relative_path],
                    ),
                )

                if fingerprint.extension == ".package":
                    packages_total += 1
                    parse_status, parse_error, resource_count = _record_package(
                        conn,
                        scan_id,
                        file_id,
                        fingerprint.path,
                    )
                    resources_total += resource_count
                    if parse_status == "error":
                        package_parse_errors += 1
                        if parse_error:
                            warnings.append(f"{fingerprint.relative_path}: {parse_error}")

            summary = InventoryScanSummary(
                scan_id=scan_id,
                root_path=str(root),
                files_total=len(fingerprints),
                packages_total=packages_total,
                resources_total=resources_total,
                package_parse_errors=package_parse_errors,
                added=changes.added,
                removed=changes.removed,
                moved=changes.moved,
                modified=changes.modified,
                unchanged=changes.unchanged,
                warnings=warnings,
            )
            _mark_removed_files(conn, root, changes.removed_relative_paths)
            _mark_moved_source_files(conn, root, changes.moved_source_relative_paths)
            _complete_scan(conn, summary)
            _record_event(conn, scan_id, "inventory.scan.completed", summary.to_dict())
            return summary

    def export_latest_snapshot(self, root_path: Path | str) -> dict[str, object]:
        """Export the latest recorded snapshot for support or regression fixtures."""
        root = Path(root_path).expanduser().resolve()
        with self.store.connect() as conn:
            conn.row_factory = sqlite3.Row
            snapshot = conn.execute(
                """
                SELECT
                    s.id AS snapshot_id,
                    s.scan_id,
                    s.root_path,
                    s.created_at,
                    sc.files_total,
                    sc.packages_total,
                    sc.resources_total,
                    sc.package_parse_errors,
                    sc.added,
                    sc.removed,
                    sc.moved,
                    sc.modified,
                    sc.unchanged,
                    sc.warnings_json
                FROM snapshots s
                JOIN scans sc ON sc.id = s.scan_id
                WHERE s.root_path = ?
                ORDER BY s.id DESC
                LIMIT 1
                """,
                (str(root),),
            ).fetchone()
            if snapshot is None:
                raise ValueError(f"No inventory snapshot recorded for: {root}")

            files = conn.execute(
                """
                SELECT
                    sf.relative_path,
                    f.extension,
                    sf.size,
                    sf.sha256,
                    sf.change_status,
                    p.parse_status,
                    p.parse_error,
                    p.resource_count
                FROM snapshot_files sf
                JOIN files f ON f.id = sf.file_id
                LEFT JOIN packages p ON p.file_id = f.id
                WHERE sf.snapshot_id = ?
                ORDER BY sf.relative_path
                """,
                (int(snapshot["snapshot_id"]),),
            ).fetchall()

        return {
            "schema_version": SCHEMA_VERSION,
            "root_path": str(snapshot["root_path"]),
            "scan_id": int(snapshot["scan_id"]),
            "created_at": str(snapshot["created_at"]),
            "summary": {
                "files_total": int(snapshot["files_total"]),
                "packages_total": int(snapshot["packages_total"]),
                "resources_total": int(snapshot["resources_total"]),
                "package_parse_errors": int(snapshot["package_parse_errors"]),
                "added": int(snapshot["added"]),
                "removed": int(snapshot["removed"]),
                "moved": int(snapshot["moved"]),
                "modified": int(snapshot["modified"]),
                "unchanged": int(snapshot["unchanged"]),
                "warnings": json.loads(str(snapshot["warnings_json"])),
            },
            "files": [_export_file_row(row) for row in files],
        }

    def list_scan_history(self, root_path: Path | str, limit: int = 20) -> list[dict[str, object]]:
        """Return recent scan summaries for a Sims 4 folder, newest first."""
        if limit <= 0:
            raise ValueError("Inventory history limit must be greater than zero")

        root = Path(root_path).expanduser().resolve()
        with self.store.connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT
                    id AS scan_id,
                    root_path,
                    started_at,
                    completed_at,
                    status,
                    files_total,
                    packages_total,
                    resources_total,
                    package_parse_errors,
                    added,
                    removed,
                    moved,
                    modified,
                    unchanged,
                    warnings_json
                FROM scans
                WHERE root_path = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (str(root), limit),
            ).fetchall()

        return [_scan_history_row_to_dict(row) for row in rows]


def default_inventory_db_path() -> Path:
    """Return the default Simanalysis-owned inventory database location."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Simanalysis" / "inventory.sqlite3"
    if sys.platform.startswith("win"):
        appdata = Path.home() / "AppData" / "Roaming"
        return appdata / "Simanalysis" / "inventory.sqlite3"
    return Path.home() / ".local" / "share" / "simanalysis" / "inventory.sqlite3"


def _export_file_row(row: sqlite3.Row) -> dict[str, object]:
    package: dict[str, object] | None = None
    if row["parse_status"] is not None:
        package = {
            "parse_status": str(row["parse_status"]),
            "parse_error": row["parse_error"],
            "resource_count": int(row["resource_count"]),
        }
    return {
        "relative_path": str(row["relative_path"]),
        "extension": str(row["extension"]),
        "size": int(row["size"]),
        "sha256": str(row["sha256"]),
        "change_status": str(row["change_status"]),
        "package": package,
    }


def _scan_history_row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return {
        "scan_id": int(row["scan_id"]),
        "root_path": str(row["root_path"]),
        "started_at": str(row["started_at"]),
        "completed_at": row["completed_at"],
        "status": str(row["status"]),
        "files_total": int(row["files_total"]),
        "packages_total": int(row["packages_total"]),
        "resources_total": int(row["resources_total"]),
        "package_parse_errors": int(row["package_parse_errors"]),
        "added": int(row["added"]),
        "removed": int(row["removed"]),
        "moved": int(row["moved"]),
        "modified": int(row["modified"]),
        "unchanged": int(row["unchanged"]),
        "warnings": json.loads(str(row["warnings_json"])),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _discover_file_fingerprints(
    root: Path,
    excluded_paths: set[Path],
) -> _DiscoveryResult:
    fingerprints: list[_FileFingerprint] = []
    warnings: list[str] = []
    resolved_exclusions = {path.expanduser().resolve() for path in excluded_paths}
    for path in sorted(root.rglob("*")):
        relative_path = path.relative_to(root).as_posix()
        if path.is_symlink():
            warnings.append(f"Skipped symlinked path: {relative_path}")
            continue

        if not path.is_file():
            continue

        resolved = path.resolve()
        if resolved in resolved_exclusions:
            continue

        stat = path.stat()
        fingerprints.append(
            _FileFingerprint(
                path=path,
                relative_path=relative_path,
                extension=path.suffix.lower(),
                size=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
                sha256=_sha256(path),
            )
        )
    return _DiscoveryResult(fingerprints=fingerprints, warnings=warnings)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class _ChangeSummary:
    status_by_relative_path: dict[str, str]
    removed_relative_paths: set[str]
    moved_source_relative_paths: set[str]
    added: int
    removed: int
    moved: int
    modified: int
    unchanged: int


def _load_latest_snapshot(
    conn: sqlite3.Connection,
    root: Path,
) -> dict[str, _SnapshotFingerprint]:
    row = conn.execute(
        """
        SELECT id
        FROM snapshots
        WHERE root_path = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (str(root),),
    ).fetchone()
    if row is None:
        return {}

    snapshot_id = int(row[0])
    rows = conn.execute(
        """
        SELECT relative_path, size, sha256
        FROM snapshot_files
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    ).fetchall()
    return {
        str(item[0]): _SnapshotFingerprint(
            relative_path=str(item[0]),
            size=int(item[1]),
            sha256=str(item[2]),
        )
        for item in rows
    }


def _classify_changes(
    previous: dict[str, _SnapshotFingerprint],
    current: list[_FileFingerprint],
) -> _ChangeSummary:
    if not previous:
        return _ChangeSummary(
            status_by_relative_path={fingerprint.relative_path: "added" for fingerprint in current},
            removed_relative_paths=set(),
            moved_source_relative_paths=set(),
            added=len(current),
            removed=0,
            moved=0,
            modified=0,
            unchanged=0,
        )

    current_by_relative = {fingerprint.relative_path: fingerprint for fingerprint in current}
    removed_candidates = set(previous).difference(current_by_relative)
    status_by_relative_path: dict[str, str] = {}
    added_candidates: list[_FileFingerprint] = []
    modified = 0
    unchanged = 0

    for fingerprint in current:
        old = previous.get(fingerprint.relative_path)
        if old is None:
            added_candidates.append(fingerprint)
        elif old.sha256 == fingerprint.sha256 and old.size == fingerprint.size:
            status_by_relative_path[fingerprint.relative_path] = "unchanged"
            unchanged += 1
        else:
            status_by_relative_path[fingerprint.relative_path] = "modified"
            modified += 1

    removed_by_hash: dict[str, list[str]] = {}
    for relative_path in removed_candidates:
        removed_by_hash.setdefault(previous[relative_path].sha256, []).append(relative_path)

    moved_sources: set[str] = set()
    moved = 0
    added = 0
    for fingerprint in added_candidates:
        old_paths = removed_by_hash.get(fingerprint.sha256, [])
        old_path = next((path for path in old_paths if path not in moved_sources), None)
        if old_path is None:
            status_by_relative_path[fingerprint.relative_path] = "added"
            added += 1
        else:
            status_by_relative_path[fingerprint.relative_path] = "moved"
            moved_sources.add(old_path)
            moved += 1

    removed_paths = removed_candidates.difference(moved_sources)
    return _ChangeSummary(
        status_by_relative_path=status_by_relative_path,
        removed_relative_paths=removed_paths,
        moved_source_relative_paths=moved_sources,
        added=added,
        removed=len(removed_paths),
        moved=moved,
        modified=modified,
        unchanged=unchanged,
    )


def _create_scan(conn: sqlite3.Connection, root: Path, started_at: str) -> int:
    cursor = conn.execute(
        """
        INSERT INTO scans (root_path, started_at, status)
        VALUES (?, ?, ?)
        """,
        (str(root), started_at, "running"),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Failed to create inventory scan row")
    return cursor.lastrowid


def _create_snapshot(
    conn: sqlite3.Connection,
    scan_id: int,
    root: Path,
    created_at: str,
    file_count: int,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO snapshots (scan_id, root_path, created_at, file_count)
        VALUES (?, ?, ?, ?)
        """,
        (scan_id, str(root), created_at, file_count),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("Failed to create inventory snapshot row")
    return cursor.lastrowid


def _upsert_file(
    conn: sqlite3.Connection,
    scan_id: int,
    root: Path,
    fingerprint: _FileFingerprint,
) -> int:
    conn.execute(
        """
        INSERT INTO files (
            path, root_path, relative_path, extension, size, mtime_ns, sha256,
            first_seen_scan_id, last_seen_scan_id, present, scan_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'seen')
        ON CONFLICT(path) DO UPDATE SET
            root_path = excluded.root_path,
            relative_path = excluded.relative_path,
            extension = excluded.extension,
            size = excluded.size,
            mtime_ns = excluded.mtime_ns,
            sha256 = excluded.sha256,
            last_seen_scan_id = excluded.last_seen_scan_id,
            present = 1,
            scan_status = 'seen'
        """,
        (
            str(fingerprint.path),
            str(root),
            fingerprint.relative_path,
            fingerprint.extension,
            fingerprint.size,
            fingerprint.mtime_ns,
            fingerprint.sha256,
            scan_id,
            scan_id,
        ),
    )
    file_id = conn.execute(
        "SELECT id FROM files WHERE path = ?",
        (str(fingerprint.path),),
    ).fetchone()
    if file_id is None:
        raise RuntimeError(f"Failed to record file in inventory: {fingerprint.path}")
    return int(file_id[0])


def _mark_removed_files(
    conn: sqlite3.Connection, root: Path, removed_relative_paths: set[str]
) -> None:
    for relative_path in removed_relative_paths:
        conn.execute(
            """
            UPDATE files
            SET present = 0,
                scan_status = 'missing'
            WHERE root_path = ? AND relative_path = ?
            """,
            (str(root), relative_path),
        )


def _mark_moved_source_files(
    conn: sqlite3.Connection,
    root: Path,
    moved_source_relative_paths: set[str],
) -> None:
    for relative_path in moved_source_relative_paths:
        conn.execute(
            """
            UPDATE files
            SET present = 0,
                scan_status = 'moved'
            WHERE root_path = ? AND relative_path = ?
            """,
            (str(root), relative_path),
        )


def _record_package(
    conn: sqlite3.Connection,
    scan_id: int,
    file_id: int,
    package_path: Path,
) -> tuple[str, str | None, int]:
    conn.execute("DELETE FROM resources WHERE file_id = ?", (file_id,))
    try:
        reader = DBPFReader(package_path)
        resources = reader.resources
    except Exception as exc:
        parse_error = str(exc)
        conn.execute(
            """
            INSERT INTO packages (
                file_id, parse_status, parse_error, resource_count, package_kind,
                last_scan_id
            )
            VALUES (?, 'error', ?, 0, 'package', ?)
            ON CONFLICT(file_id) DO UPDATE SET
                parse_status = excluded.parse_status,
                parse_error = excluded.parse_error,
                resource_count = excluded.resource_count,
                package_kind = excluded.package_kind,
                last_scan_id = excluded.last_scan_id
            """,
            (file_id, parse_error, scan_id),
        )
        return "error", parse_error, 0

    for resource in resources:
        conn.execute(
            """
            INSERT INTO resources (
                file_id, type_hex, group_hex, instance_hex, size, compressed_size,
                compressed, last_scan_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                f"0x{resource.type:08x}",
                f"0x{resource.group:08x}",
                f"0x{resource.instance:016x}",
                resource.size,
                resource.compressed_size,
                1 if resource.is_compressed else 0,
                scan_id,
            ),
        )

    conn.execute(
        """
        INSERT INTO packages (
            file_id, parse_status, parse_error, resource_count, package_kind,
            last_scan_id
        )
        VALUES (?, 'ok', NULL, ?, 'package', ?)
        ON CONFLICT(file_id) DO UPDATE SET
            parse_status = excluded.parse_status,
            parse_error = excluded.parse_error,
            resource_count = excluded.resource_count,
            package_kind = excluded.package_kind,
            last_scan_id = excluded.last_scan_id
        """,
        (file_id, len(resources), scan_id),
    )
    return "ok", None, len(resources)


def _complete_scan(conn: sqlite3.Connection, summary: InventoryScanSummary) -> None:
    conn.execute(
        """
        UPDATE scans
        SET completed_at = ?,
            status = 'completed',
            files_total = ?,
            packages_total = ?,
            resources_total = ?,
            package_parse_errors = ?,
            added = ?,
            removed = ?,
            moved = ?,
            modified = ?,
            unchanged = ?,
            warnings_json = ?
        WHERE id = ?
        """,
        (
            _utc_now(),
            summary.files_total,
            summary.packages_total,
            summary.resources_total,
            summary.package_parse_errors,
            summary.added,
            summary.removed,
            summary.moved,
            summary.modified,
            summary.unchanged,
            json.dumps(summary.warnings, sort_keys=True),
            summary.scan_id,
        ),
    )


def _record_event(
    conn: sqlite3.Connection,
    scan_id: int,
    event_type: str,
    payload: dict[str, object],
) -> None:
    conn.execute(
        """
        INSERT INTO event_log (created_at, event_type, scan_id, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (_utc_now(), event_type, scan_id, json.dumps(payload, sort_keys=True)),
    )


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    files_total INTEGER NOT NULL DEFAULT 0,
    packages_total INTEGER NOT NULL DEFAULT 0,
    resources_total INTEGER NOT NULL DEFAULT 0,
    package_parse_errors INTEGER NOT NULL DEFAULT 0,
    added INTEGER NOT NULL DEFAULT 0,
    removed INTEGER NOT NULL DEFAULT 0,
    moved INTEGER NOT NULL DEFAULT 0,
    modified INTEGER NOT NULL DEFAULT 0,
    unchanged INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    root_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    first_seen_scan_id INTEGER NOT NULL REFERENCES scans(id),
    last_seen_scan_id INTEGER NOT NULL REFERENCES scans(id),
    present INTEGER NOT NULL,
    scan_status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_root_relative
ON files(root_path, relative_path);

CREATE INDEX IF NOT EXISTS idx_files_sha256
ON files(sha256);

CREATE TABLE IF NOT EXISTS packages (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    parse_status TEXT NOT NULL,
    parse_error TEXT,
    resource_count INTEGER NOT NULL,
    compression_flags TEXT,
    package_kind TEXT NOT NULL,
    last_scan_id INTEGER NOT NULL REFERENCES scans(id)
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    type_hex TEXT NOT NULL,
    group_hex TEXT NOT NULL,
    instance_hex TEXT NOT NULL,
    size INTEGER NOT NULL,
    compressed_size INTEGER NOT NULL,
    compressed INTEGER NOT NULL,
    last_scan_id INTEGER NOT NULL REFERENCES scans(id)
);

CREATE INDEX IF NOT EXISTS idx_resources_key
ON resources(type_hex, group_hex, instance_hex);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    root_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    file_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_files (
    snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    change_status TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, file_id)
);

CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    scan_id INTEGER REFERENCES scans(id) ON DELETE SET NULL,
    payload_json TEXT NOT NULL
);
"""
