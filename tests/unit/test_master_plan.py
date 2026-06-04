from __future__ import annotations

import json
from pathlib import Path

from simanalysis.master_plan import (
    create_master_plan,
    diff_master_baseline,
    master_baseline_status,
    master_status,
    master_update_registry_status,
    save_master_baseline,
    save_update_registry_template,
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


def test_update_registry_status_reports_missing_registry_without_writing(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    unit = mods / "Creator_Gameplay_v1.0"
    unit.mkdir()
    (unit / "creator_gameplay.package").write_bytes(b"package")

    status = master_update_registry_status(sims4)

    assert status == {
        "schema_version": 1,
        "sims4_dir": str(sims4.resolve()),
        "registry_exists": False,
        "registry_path": None,
        "summary": {
            "catalog_entries": 1,
            "tracked_sources": 0,
            "missing_sources": 1,
            "outdated": 0,
            "current": 0,
            "needs_check": 0,
            "no_installed_version": 0,
            "retired_entries": 0,
            "warnings": 0,
        },
        "entries": [],
        "warnings": [],
        "blockers": ["No update registry found"],
    }
    assert not (sims4 / "_Simanalysis_MasterPlan").exists()


def test_save_update_registry_template_preserves_user_source_fields(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    tracked = mods / "Creator_Gameplay_v1.0"
    tracked.mkdir(parents=True)
    (tracked / "creator_gameplay.package").write_bytes(b"package")

    initial = save_update_registry_template(sims4)
    registry_path = Path(initial["registry_path"])
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["entries"][0]["source_url"] = "https://creator.example/gameplay"
    registry["entries"][0]["latest_version"] = "1.1"
    registry["entries"][0]["last_checked_at"] = "2026-06-04"
    registry["entries"][0]["notes"] = "manual source"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    added = mods / "OtherCreator_CAS_v2.0"
    added.mkdir()
    (added / "other.package").write_bytes(b"package")

    refreshed = save_update_registry_template(sims4)

    entries = {entry["relative_path"]: entry for entry in refreshed["entries"]}
    tracked_entry = entries["Mods/Creator_Gameplay_v1.0"]
    assert refreshed["kind"] == "master_update_registry"
    assert registry_path == sims4 / "_Simanalysis_MasterPlan" / "update-registry.json"
    assert tracked_entry["source_url"] == "https://creator.example/gameplay"
    assert tracked_entry["latest_version"] == "1.1"
    assert tracked_entry["last_checked_at"] == "2026-06-04"
    assert tracked_entry["notes"] == "manual source"
    assert entries["Mods/OtherCreator_CAS_v2.0"]["source_url"] is None
    assert (tracked / "creator_gameplay.package").is_file()


def test_update_registry_status_flags_outdated_current_and_missing_sources(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    outdated = mods / "Creator_Gameplay_v1.0"
    current = mods / "Creator_UI_v2.0"
    missing = mods / "NoSource_Script_v3.0"
    outdated.mkdir(parents=True)
    current.mkdir()
    missing.mkdir()
    (outdated / "gameplay.package").write_bytes(b"package")
    (current / "ui.package").write_bytes(b"package")
    (missing / "script.ts4script").write_bytes(b"script")

    template = save_update_registry_template(sims4)
    registry_path = Path(template["registry_path"])
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    for entry in registry["entries"]:
        if entry["relative_path"] == "Mods/Creator_Gameplay_v1.0":
            entry["source_url"] = "https://creator.example/gameplay"
            entry["latest_version"] = "1.2"
        if entry["relative_path"] == "Mods/Creator_UI_v2.0":
            entry["source_url"] = "https://creator.example/ui"
            entry["latest_version"] = "2.0"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    status = master_update_registry_status(sims4)

    assert status["registry_exists"] is True
    assert status["summary"] == {
        "catalog_entries": 3,
        "tracked_sources": 2,
        "missing_sources": 1,
        "outdated": 1,
        "current": 1,
        "needs_check": 0,
        "no_installed_version": 0,
        "retired_entries": 0,
        "warnings": 0,
    }
    statuses = {entry["relative_path"]: entry["status"] for entry in status["entries"]}
    assert statuses == {
        "Mods/Creator_Gameplay_v1.0": "outdated",
        "Mods/Creator_UI_v2.0": "current",
        "Mods/NoSource_Script_v3.0": "missing_source",
    }
