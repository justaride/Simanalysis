from __future__ import annotations

import json
import struct
from pathlib import Path

from simanalysis.inventory import run_inventory_scan


def write_package(path: Path, payload: bytes = b"resource data") -> None:
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 0)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", 36)
    header[64:68] = struct.pack("<I", 96)

    resource_offset = 96 + 36
    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0x034AEECB)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0x12345678)
    index += struct.pack("<I", resource_offset)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(index) + payload)


def test_first_inventory_scan_records_files_and_package_resources(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    write_package(mods / "Hair.package")
    (mods / "Core.ts4script").write_bytes(b"script")
    (mods / "Archive.zip").write_bytes(b"zip")
    (sims / "Options.ini").write_text("mods=1", encoding="utf-8")
    db = tmp_path / "inventory.sqlite3"

    result = run_inventory_scan(sims, db_path=db)

    assert result["database_path"] == str(db)
    assert result["summary"]["file_count"] == 4
    assert result["summary"]["package_count"] == 1
    assert result["summary"]["script_count"] == 1
    assert result["summary"]["archive_count"] == 1
    assert result["summary"]["added_count"] == 4
    assert result["summary"]["resource_count"] == 1
    assert result["summary"]["package_parse_ok_count"] == 1
    assert result["warnings"] == []


def test_second_identical_inventory_scan_reports_unchanged(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    db = tmp_path / "inventory.sqlite3"

    run_inventory_scan(sims, db_path=db)
    result = run_inventory_scan(sims, db_path=db)

    assert result["summary"]["file_count"] == 1
    assert result["summary"]["added_count"] == 0
    assert result["summary"]["modified_count"] == 0
    assert result["summary"]["removed_count"] == 0
    assert result["summary"]["moved_count"] == 0
    assert result["summary"]["unchanged_count"] == 1


def test_inventory_scan_detects_add_remove_modify_and_move(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    mods.mkdir(parents=True)
    (mods / "keep.package").write_bytes(b"keep")
    (mods / "remove.package").write_bytes(b"remove")
    (mods / "modify.package").write_bytes(b"before")
    (mods / "move.package").write_bytes(b"move-me")
    db = tmp_path / "inventory.sqlite3"
    run_inventory_scan(sims, db_path=db)

    (mods / "remove.package").unlink()
    (mods / "modify.package").write_bytes(b"after")
    (mods / "added.package").write_bytes(b"added")
    (mods / "Nested").mkdir()
    (mods / "move.package").rename(mods / "Nested" / "move.package")

    result = run_inventory_scan(sims, db_path=db)

    assert result["summary"]["added_count"] == 1
    assert result["summary"]["removed_count"] == 1
    assert result["summary"]["modified_count"] == 1
    assert result["summary"]["moved_count"] == 1
    assert result["summary"]["unchanged_count"] == 1


def test_inventory_scan_records_corrupt_package_without_crashing(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    mods.mkdir(parents=True)
    (mods / "bad.package").write_bytes(b"not dbpf")

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3")

    assert result["summary"]["package_count"] == 1
    assert result["summary"]["package_parse_error_count"] == 1
    assert result["packages"][0]["parse_status"] == "error"
    assert "DBPF" in result["packages"][0]["parse_error"]


def test_inventory_scan_writes_explicit_json_export(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    export = tmp_path / "snapshot.json"

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3", export_path=export)
    payload = json.loads(export.read_text(encoding="utf-8"))

    assert result["export_path"] == str(export)
    assert payload["summary"]["file_count"] == 1
    assert payload["files"][0]["rel_path"] == "Mods/A.ts4script"


def test_inventory_scan_skips_app_owned_generated_folders(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    (sims / "_Simanalysis_Treatment").mkdir()
    (sims / "_Simanalysis_Treatment" / "generated.package").write_bytes(b"x")

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3")

    assert result["summary"]["file_count"] == 1
    assert [file["rel_path"] for file in result["files"]] == ["Mods/A.ts4script"]
