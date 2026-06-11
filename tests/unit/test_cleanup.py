"""Tests for read-only Mods cleanup planning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simanalysis.cleanup import CleanupPlanner
from simanalysis.inventory import InventoryScanner, InventoryStore

pytestmark = pytest.mark.synthetic


def _scan_fixture(tmp_path: Path) -> tuple[Path, Path]:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)
    return sims4, db_path


def test_cleanup_plan_groups_exact_duplicates_with_stable_keep_candidate(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    deep = mods / "Creator" / "Nested"
    deep.mkdir(parents=True)
    (mods / "keep.package").write_bytes(b"duplicate")
    (deep / "extra.package").write_bytes(b"duplicate")
    (mods / "other.package").write_bytes(b"unique")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    duplicate = next(item for item in plan["findings"] if item["category"] == "exact_duplicate")
    assert plan["summary"]["duplicate_groups"] == 1
    assert duplicate["evidence"]["keep_candidate"] == "Mods/keep.package"
    assert duplicate["evidence"]["paths"] == [
        "Mods/Creator/Nested/extra.package",
        "Mods/keep.package",
    ]
    assert duplicate["actions"] == [
        {
            "action_id": "duplicate:1",
            "kind": "review_duplicate",
            "source_relative_path": "Mods/Creator/Nested/extra.package",
            "proposed_destination": (
                "_Simanalysis_Cleanup/cleanup-20260611-123456/"
                "duplicates/Mods/Creator/Nested/extra.package"
            ),
            "reason": "Exact duplicate of Mods/keep.package",
        }
    ]


def test_cleanup_plan_flags_archives_support_files_resource_cfg_and_tray(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pack = mods / "Creator"
    pack.mkdir(parents=True)
    (mods / "Resource.cfg").write_text("root resource", encoding="utf-8")
    (pack / "Resource.cfg").write_text("nested resource", encoding="utf-8")
    (mods / "download.zip").write_bytes(b"archive")
    (mods / "preview.png").write_bytes(b"image")
    (mods / "readme.txt").write_text("notes", encoding="utf-8")
    (mods / "lot.trayitem").write_bytes(b"tray")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    categories = [finding["category"] for finding in plan["findings"]]
    assert categories == [
        "duplicate_resource_cfg",
        "inactive_archive",
        "misplaced_tray",
        "support_file",
        "support_file",
    ]
    assert plan["summary"] == {
        "files_considered": 6,
        "finding_count": 5,
        "action_count": 5,
        "duplicate_groups": 0,
        "archives": 1,
        "duplicate_resource_cfg": 1,
        "support_files": 2,
        "misplaced_tray": 1,
    }
    assert all(
        action["kind"].startswith("review_")
        for finding in plan["findings"]
        for action in finding["actions"]
    )


def test_cleanup_plan_ignores_files_outside_mods(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "active.ts4script").write_bytes(b"active")
    tray = sims4 / "Tray"
    tray.mkdir()
    (tray / "real.trayitem").write_bytes(b"tray")
    (sims4 / "notes.zip").write_bytes(b"outside")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    assert plan["summary"]["files_considered"] == 1
    assert plan["findings"] == []
    assert plan["warnings"] == []


def test_cleanup_plan_requires_existing_inventory_database(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    db_path = tmp_path / "inventory.sqlite3"

    with pytest.raises(ValueError, match="No inventory database exists"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)


def test_cleanup_plan_requires_existing_inventory_snapshot(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    db_path = tmp_path / "inventory.sqlite3"
    InventoryStore(db_path).initialize()

    with pytest.raises(ValueError, match="No inventory scan exists"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)


def test_cleanup_plan_export_must_be_outside_sims_root(tmp_path: Path) -> None:
    sims4, db_path = _scan_fixture(tmp_path)
    export_path = sims4 / "cleanup.json"

    with pytest.raises(ValueError, match="outside the selected Sims 4 folder"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").export_plan(
            sims4,
            export_path,
        )

    assert not export_path.exists()


def test_cleanup_plan_export_writes_json_without_sims_folder_mutation(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.7z").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)
    before = sorted(path.relative_to(sims4).as_posix() for path in sims4.rglob("*"))
    export_path = tmp_path / "cleanup-plan.json"

    result = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").export_plan(
        sims4,
        export_path,
    )

    after = sorted(path.relative_to(sims4).as_posix() for path in sims4.rglob("*"))
    assert before == after
    assert not (sims4 / "_Simanalysis_Cleanup").exists()
    assert json.loads(export_path.read_text(encoding="utf-8")) == result
