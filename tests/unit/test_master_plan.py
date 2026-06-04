from __future__ import annotations

from pathlib import Path

from simanalysis.master_plan import (
    create_master_plan,
    diff_master_baseline,
    master_baseline_status,
    master_status,
    save_master_baseline,
)


def test_create_master_plan_builds_update_performance_and_creator_lanes(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    versioned = mods / "LittleMsSam_BetterSchool_v1.2"
    missing_version = mods / "NoVersionScript"
    large = mods / "Peacemaker Big Set v3.0"
    versioned.mkdir(parents=True)
    missing_version.mkdir()
    large.mkdir()
    (versioned / "LittleMsSam_BetterSchool.package").write_bytes(b"package")
    (versioned / "LittleMsSam_BetterSchool.ts4script").write_bytes(b"script")
    (missing_version / "script_only.ts4script").write_bytes(b"script")
    big_package = large / "peacemaker_big_set.package"
    with big_package.open("wb") as handle:
        handle.truncate(3 * 1024 * 1024)

    plan = create_master_plan(sims4)

    assert plan["schema_version"] == 1
    assert plan["summary"]["catalog_entries"] == 3
    assert plan["summary"]["creator_profiles"] == 3
    assert plan["summary"]["update_candidates"] == 1
    assert plan["summary"]["performance_actions"] >= 1

    catalog_names = {entry["unit_name"]: entry for entry in plan["catalog"]["entries"]}
    assert catalog_names["LittleMsSam_BetterSchool_v1.2"]["creator"] == "LittleMsSam"
    assert catalog_names["LittleMsSam_BetterSchool_v1.2"]["version_signal"] == "1.2"
    assert catalog_names["NoVersionScript"]["update_status"] == "needs_version_tracking"

    assert plan["updates"]["candidates"] == [
        {
            "unit_id": catalog_names["NoVersionScript"]["unit_id"],
            "unit_name": "NoVersionScript",
            "reason": "script_mod_without_version_signal",
            "severity": "medium",
            "suggested_action": "Add this script mod to the update catalog before changing more mods.",
        }
    ]
    assert plan["performance"]["heavy_units"][0]["unit_name"] == "Peacemaker Big Set v3.0"
    assert plan["creators"]["profiles"][0]["creator"] == "LittleMsSam"


def test_master_status_is_compact_and_read_only(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "LooseCreator_CAS_v2.package").write_bytes(b"package")

    status = master_status(sims4)

    assert status == {
        "schema_version": 1,
        "sims4_dir": str(sims4.resolve()),
        "summary": {
            "active_units": 1,
            "catalog_entries": 1,
            "creator_profiles": 1,
            "performance_actions": 0,
            "update_candidates": 0,
            "warnings": 0,
        },
        "warnings": [],
        "blockers": [],
    }
    assert not (sims4 / "_Simanalysis_MasterPlan").exists()


def test_save_master_baseline_writes_simanalysis_owned_manifest(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    unit = mods / "Creator_Gameplay_v1.0"
    unit.mkdir()
    (unit / "creator_gameplay.package").write_bytes(b"package")

    baseline = save_master_baseline(sims4, label="initial")

    baseline_path = Path(baseline["baseline_path"])
    latest_path = Path(baseline["latest_baseline_path"])
    assert baseline["kind"] == "master_catalog_baseline"
    assert baseline["label"] == "initial"
    assert baseline["summary"]["catalog_entries"] == 1
    assert baseline_path.exists()
    assert latest_path.exists()
    assert baseline_path.parent == sims4 / "_Simanalysis_MasterPlan"
    assert latest_path.parent == sims4 / "_Simanalysis_MasterPlan"
    assert (unit / "creator_gameplay.package").is_file()


def test_diff_master_baseline_reports_added_removed_and_changed_units(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    changed = mods / "ChangedCreator_Tuning_v1.0"
    removed = mods / "RemovedCreator_CAS_v1.0"
    changed.mkdir(parents=True)
    removed.mkdir()
    changed_file = changed / "changed.package"
    removed_file = removed / "removed.package"
    changed_file.write_bytes(b"old")
    removed_file.write_bytes(b"removed")
    baseline = save_master_baseline(sims4)

    changed_file.write_bytes(b"new-and-larger")
    removed_file.unlink()
    removed.rmdir()
    added = mods / "AddedCreator_UI_v1.0"
    added.mkdir()
    (added / "added.package").write_bytes(b"added")

    diff = diff_master_baseline(sims4, baseline["baseline_path"])

    assert diff["summary"] == {
        "added": 1,
        "removed": 1,
        "changed": 1,
        "unchanged": 0,
        "warnings": 0,
    }
    assert [entry["unit_name"] for entry in diff["added"]] == ["AddedCreator_UI_v1.0"]
    assert [entry["unit_name"] for entry in diff["removed"]] == ["RemovedCreator_CAS_v1.0"]
    assert [entry["current"]["unit_name"] for entry in diff["changed"]] == [
        "ChangedCreator_Tuning_v1.0"
    ]


def test_master_baseline_status_reports_missing_baseline_without_writing(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    (sims4 / "Mods").mkdir(parents=True)

    status = master_baseline_status(sims4)

    assert status == {
        "schema_version": 1,
        "sims4_dir": str(sims4.resolve()),
        "baseline_exists": False,
        "baseline_path": None,
        "summary": {
            "added": 0,
            "removed": 0,
            "changed": 0,
            "unchanged": 0,
            "warnings": 0,
        },
        "warnings": [],
        "blockers": ["No master baseline found"],
    }
    assert not (sims4 / "_Simanalysis_MasterPlan").exists()
