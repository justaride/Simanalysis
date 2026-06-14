"""Tests for the read-only inventory ledger."""

from __future__ import annotations

import sqlite3
import struct
import zlib
from hashlib import sha256
from pathlib import Path

import pytest

from simanalysis.inventory import InventoryScanner

pytestmark = pytest.mark.synthetic


def _create_package(path: Path, resource_type: int = 0x545AC67A) -> None:
    """Create a tiny Sims 4 DBPF package with one resource."""
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[12:16] = struct.pack("<I", 0)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", 36)
    header[64:68] = struct.pack("<I", 96)

    resource_data = b'<I c="Buff" i="fixture" m="buffs.buff" s="123" />'
    compressed_data = zlib.compress(resource_data)
    resource_offset = 96 + 36

    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", resource_type)
    index += struct.pack("<I", 0x00000000)
    index += struct.pack("<I", 0x00000000)
    index += struct.pack("<I", 0x0000007B)
    index += struct.pack("<I", resource_offset)
    index += struct.pack("<I", len(compressed_data))
    index += struct.pack("<I", len(resource_data))
    index += struct.pack("<H", 0x5A42)
    index += struct.pack("<H", 1)

    path.write_bytes(bytes(header) + bytes(index) + compressed_data)


def test_inventory_scan_records_file_package_resource_snapshot_and_event(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    package_path = mods / "truth.package"
    options_path = sims4 / "Options.ini"
    _create_package(package_path)
    options_path.write_text("uiscale = 100", encoding="utf-8")

    db_path = tmp_path / "inventory.sqlite3"
    summary = InventoryScanner(db_path).scan(sims4)

    assert summary.files_total == 2
    assert summary.packages_total == 1
    assert summary.resources_total == 1
    assert summary.package_parse_errors == 0
    assert summary.added == 2
    assert package_path.exists()
    assert options_path.exists()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        files = conn.execute(
            "SELECT relative_path, extension, present FROM files ORDER BY relative_path"
        ).fetchall()
        package = conn.execute(
            "SELECT parse_status, parse_error, resource_count FROM packages"
        ).fetchone()
        resource = conn.execute(
            "SELECT type_hex, group_hex, instance_hex, compressed FROM resources"
        ).fetchone()
        snapshot = conn.execute(
            "SELECT file_count FROM snapshots WHERE scan_id = ?",
            (summary.scan_id,),
        ).fetchone()
        event = conn.execute(
            "SELECT event_type FROM event_log WHERE scan_id = ?",
            (summary.scan_id,),
        ).fetchone()

    assert [row["relative_path"] for row in files] == ["Mods/truth.package", "Options.ini"]
    assert {row["extension"] for row in files} == {".ini", ".package"}
    assert {row["present"] for row in files} == {1}
    assert dict(package) == {
        "parse_status": "ok",
        "parse_error": None,
        "resource_count": 1,
    }
    assert dict(resource) == {
        "type_hex": "0x545ac67a",
        "group_hex": "0x00000000",
        "instance_hex": "0x000000000000007b",
        "compressed": 1,
    }
    assert snapshot["file_count"] == 2
    assert event["event_type"] == "inventory.scan.completed"


def test_inventory_scan_reports_unchanged_files_on_second_run(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    _create_package(mods / "truth.package")
    (sims4 / "Options.ini").write_text("uiscale = 100", encoding="utf-8")

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    first = scanner.scan(sims4)
    second = scanner.scan(sims4)

    assert first.added == 2
    assert second.files_total == 2
    assert second.added == 0
    assert second.modified == 0
    assert second.removed == 0
    assert second.moved == 0
    assert second.unchanged == 2

    with sqlite3.connect(tmp_path / "inventory.sqlite3") as conn:
        statuses = conn.execute(
            """
            SELECT sf.change_status
            FROM snapshot_files sf
            JOIN snapshots s ON s.id = sf.snapshot_id
            WHERE s.scan_id = ?
            ORDER BY sf.relative_path
            """,
            (second.scan_id,),
        ).fetchall()

    assert [row[0] for row in statuses] == ["unchanged", "unchanged"]


def test_inventory_scan_reports_added_removed_modified_and_moved_files(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    original_package = mods / "truth.package"
    options_path = sims4 / "Options.ini"
    removed_path = sims4 / "Old.txt"
    _create_package(original_package)
    options_path.write_text("uiscale = 100", encoding="utf-8")
    removed_path.write_text("old", encoding="utf-8")

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    scanner.scan(sims4)

    moved_package = mods / "Nested" / "truth.package"
    moved_package.parent.mkdir()
    original_package.rename(moved_package)
    options_path.write_text("uiscale = 90", encoding="utf-8")
    removed_path.unlink()
    (sims4 / "New.txt").write_text("new", encoding="utf-8")

    summary = scanner.scan(sims4)

    assert summary.added == 1
    assert summary.removed == 1
    assert summary.modified == 1
    assert summary.moved == 1
    assert summary.unchanged == 0

    with sqlite3.connect(tmp_path / "inventory.sqlite3") as conn:
        rows = conn.execute(
            """
            SELECT relative_path, present, scan_status
            FROM files
            ORDER BY relative_path
            """
        ).fetchall()
        statuses = conn.execute(
            """
            SELECT sf.relative_path, sf.change_status
            FROM snapshot_files sf
            JOIN snapshots s ON s.id = sf.snapshot_id
            WHERE s.scan_id = ?
            ORDER BY sf.relative_path
            """,
            (summary.scan_id,),
        ).fetchall()

    present_by_path = {row[0]: (row[1], row[2]) for row in rows}
    assert present_by_path["Mods/truth.package"] == (0, "moved")
    assert present_by_path["Old.txt"] == (0, "missing")
    assert present_by_path["Mods/Nested/truth.package"] == (1, "seen")
    assert dict(statuses) == {
        "Mods/Nested/truth.package": "moved",
        "New.txt": "added",
        "Options.ini": "modified",
    }


def test_inventory_scan_records_corrupt_package_and_exports_snapshot(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    broken = mods / "broken.package"
    broken_bytes = b"not a dbpf package"
    broken.write_bytes(broken_bytes)

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    summary = scanner.scan(sims4)
    exported = scanner.export_latest_snapshot(sims4)

    assert summary.files_total == 1
    assert summary.packages_total == 1
    assert summary.resources_total == 0
    assert summary.package_parse_errors == 1
    assert "Mods/broken.package" in summary.warnings[0]

    assert exported["schema_version"] == 1
    assert exported["root_path"] == str(sims4.resolve())
    assert exported["scan_id"] == summary.scan_id
    assert exported["summary"]["package_parse_errors"] == 1
    assert exported["files"] == [
        {
            "relative_path": "Mods/broken.package",
            "extension": ".package",
            "size": len(broken_bytes),
            "sha256": sha256(broken_bytes).hexdigest(),
            "change_status": "added",
            "package": {
                "parse_status": "error",
                "parse_error": "File too small: expected at least 96 bytes, got 18",
                "resource_count": 0,
            },
        }
    ]


def test_inventory_scan_skips_symlinked_files_without_following_them(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    outside = tmp_path / "outside"
    mods.mkdir(parents=True)
    outside.mkdir()
    outside_package = outside / "outside.package"
    outside_package.write_bytes(b"outside package")
    linked_package = mods / "linked.package"
    linked_package.symlink_to(outside_package)
    options_path = sims4 / "Options.ini"
    options_path.write_text("uiscale = 100", encoding="utf-8")

    db_path = tmp_path / "inventory.sqlite3"
    summary = InventoryScanner(db_path).scan(sims4)

    assert linked_package.is_symlink()
    assert outside_package.exists()
    assert summary.files_total == 1
    assert summary.packages_total == 0
    assert summary.resources_total == 0
    assert summary.warnings == ["Skipped symlinked path: Mods/linked.package"]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT relative_path FROM files ORDER BY relative_path").fetchall()

    assert [row[0] for row in rows] == ["Options.ini"]


def test_inventory_history_returns_latest_scans_first_with_limit(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    options_path = sims4 / "Options.ini"
    options_path.write_text("uiscale = 100", encoding="utf-8")

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    first = scanner.scan(sims4)
    options_path.write_text("uiscale = 90", encoding="utf-8")
    second = scanner.scan(sims4)

    history = scanner.list_scan_history(sims4, limit=1)

    assert history == [
        {
            "scan_id": second.scan_id,
            "root_path": str(sims4.resolve()),
            "started_at": history[0]["started_at"],
            "completed_at": history[0]["completed_at"],
            "status": "completed",
            "files_total": 1,
            "packages_total": 0,
            "resources_total": 0,
            "package_parse_errors": 0,
            "added": 0,
            "removed": 0,
            "moved": 0,
            "modified": 1,
            "unchanged": 0,
            "warnings": [],
        }
    ]

    all_history = scanner.list_scan_history(sims4, limit=10)
    assert [item["scan_id"] for item in all_history] == [second.scan_id, first.scan_id]


def test_inventory_latest_file_events_include_removed_and_moved_sources(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    moving = mods / "moving.package"
    removed = sims4 / "old.txt"
    modified = sims4 / "Options.ini"
    _create_package(moving)
    removed.write_text("old", encoding="utf-8")
    modified.write_text("uiscale = 100", encoding="utf-8")

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    scanner.scan(sims4)

    moved_to = mods / "Nested" / "moving.package"
    moved_to.parent.mkdir()
    moving.rename(moved_to)
    removed.unlink()
    modified.write_text("uiscale = 90", encoding="utf-8")
    added = sims4 / "new.txt"
    added.write_text("new", encoding="utf-8")

    summary = scanner.scan(sims4)
    changes = scanner.latest_file_events(sims4, include_unchanged=False)

    assert changes["scan_id"] == summary.scan_id
    assert changes["root_path"] == str(sims4.resolve())
    assert changes["summary"] == {
        "added": 1,
        "removed": 1,
        "moved": 1,
        "modified": 1,
        "unchanged": 0,
    }
    assert [
        (event["relative_path"], event["change_status"], event["previous_relative_path"])
        for event in changes["events"]
    ] == [
        ("Mods/Nested/moving.package", "moved", "Mods/moving.package"),
        ("Mods/moving.package", "moved_source", "Mods/Nested/moving.package"),
        ("Options.ini", "modified", None),
        ("new.txt", "added", None),
        ("old.txt", "removed", None),
    ]


def test_inventory_latest_file_events_can_include_unchanged_files(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    options = sims4 / "Options.ini"
    notes = sims4 / "notes.txt"
    options.write_text("uiscale = 100", encoding="utf-8")
    notes.write_text("same", encoding="utf-8")

    scanner = InventoryScanner(tmp_path / "inventory.sqlite3")
    scanner.scan(sims4)
    options.write_text("uiscale = 90", encoding="utf-8")
    summary = scanner.scan(sims4)

    changes = scanner.latest_file_events(sims4, include_unchanged=True)

    assert changes["scan_id"] == summary.scan_id
    assert [(event["relative_path"], event["change_status"]) for event in changes["events"]] == [
        ("Options.ini", "modified"),
        ("notes.txt", "unchanged"),
    ]
