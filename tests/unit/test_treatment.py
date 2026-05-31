from __future__ import annotations

from pathlib import Path

from simanalysis.treatment import create_plan, unit_for_path


def _doctor_payload(ui_path: Path, script_name: str = "Active.ts4script") -> dict:
    return {
        "summary": {"script_active": 1, "ui_active": 1},
        "script_crashes": {
            "ranked_mods": [
                {
                    "mod": script_name,
                    "status": "active",
                    "confidence": "high",
                    "top_suspect_count": 2,
                    "crash_count": 2,
                },
                {
                    "mod": "Disabled.ts4script",
                    "status": "disabled",
                    "confidence": "high",
                    "top_suspect_count": 10,
                    "crash_count": 10,
                },
            ],
            "findings": [],
            "parse_errors": [],
        },
        "ui_crashes": {
            "findings": [
                {
                    "status": "active",
                    "reason": "key found in active package",
                    "report": {"source_file": "lastUIException.txt", "signature": "ui-sig"},
                    "hits": [
                        {
                            "status": "active",
                            "package_name": "menu.package",
                            "package_path": str(ui_path),
                        },
                        {
                            "status": "disabled",
                            "package_name": "old.package",
                            "package_path": str(ui_path.parent.parent / "_Disabled" / "old.package"),
                        },
                    ],
                },
                {
                    "status": "not_found",
                    "reason": "key not found",
                    "report": {"source_file": "lastUIException.txt", "signature": "missing"},
                    "hits": [],
                },
            ],
            "parse_errors": [],
            "index_errors": [],
        },
    }


def test_unit_for_path_uses_top_level_mods_child(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    nested = mods / "Creator" / "Nested" / "menu.package"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")

    unit = unit_for_path(nested, mods)

    assert unit is not None
    assert unit.unit_path == str(mods / "Creator")
    assert unit.unit_name == "Creator"
    assert unit.unit_kind == "folder"


def test_unit_for_path_keeps_direct_file_as_unit(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()
    direct = mods / "Standalone.ts4script"
    direct.write_bytes(b"x")

    unit = unit_for_path(direct, mods)

    assert unit is not None
    assert unit.unit_path == str(direct)
    assert unit.unit_name == "Standalone.ts4script"
    assert unit.unit_kind == "file"


def test_unit_for_path_preserves_symlink_unit_inside_mods(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    outside = tmp_path / "outside" / "Creator"
    package = outside / "menu.package"
    mods.mkdir()
    outside.mkdir(parents=True)
    package.write_bytes(b"x")
    (mods / "Creator").symlink_to(outside, target_is_directory=True)

    unit = unit_for_path(mods / "Creator" / "menu.package", mods)

    assert unit is not None
    assert unit.unit_path == str(mods / "Creator")
    assert unit.unit_name == "Creator"
    assert unit.unit_kind == "folder"


def test_unit_for_path_rejects_parent_directory_escape(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    outside = tmp_path / "outside"
    package = outside / "menu.package"
    mods.mkdir()
    outside.mkdir()
    package.write_bytes(b"x")

    assert unit_for_path(mods / ".." / "outside" / "menu.package", mods) is None


def test_create_plan_collects_only_active_doctor_candidates_without_writing(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    ui_pkg = mods / "Creator" / "menu.package"
    script = mods / "Scripts" / "Active.ts4script"
    ui_pkg.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    ui_pkg.write_bytes(b"package")
    script.write_bytes(b"script")

    plan = create_plan(sims4, mods, _doctor_payload(ui_pkg), save=False)

    assert plan["manifest_path"] is None
    assert not (sims4 / "_Simanalysis_Treatment").exists()
    assert [c["unit_name"] for c in plan["active_candidates"]] == ["Creator", "Scripts"]
    assert plan["next_batch"] == [str(mods / "Creator")]
    assert plan["status"] == "planned"
    assert plan["warnings"] == []


def test_create_plan_skips_disabled_folders_under_mods(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled_script = mods / "_DisabledOld" / "Active.ts4script"
    disabled_package = mods / "_QuarantineUI" / "menu.package"
    disabled_script.parent.mkdir(parents=True)
    disabled_package.parent.mkdir(parents=True)
    disabled_script.write_bytes(b"script")
    disabled_package.write_bytes(b"package")

    payload = _doctor_payload(disabled_package)
    plan = create_plan(sims4, mods, payload, save=False)

    assert plan["active_candidates"] == []
    assert plan["next_batch"] == []
    assert plan["warnings"] == ["No active Doctor candidates can be moved."]


def test_create_plan_ranks_script_candidates_from_finding_confidence(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    high = mods / "Zulu" / "High.ts4script"
    low = mods / "Alpha" / "Low.ts4script"
    for path in (high, low):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"script")

    payload = {
        "summary": {"script_active": 2, "ui_active": 0},
        "script_crashes": {
            "ranked_mods": [
                {"mod": "Low.ts4script", "status": "active", "top_suspect_count": 1, "crash_count": 1},
                {"mod": "High.ts4script", "status": "active", "top_suspect_count": 1, "crash_count": 1},
            ],
            "findings": [
                {"suspects": [{"mod": "Low.ts4script", "status": "active", "confidence": "low"}]},
                {"suspects": [{"mod": "High.ts4script", "status": "active", "confidence": "high"}]},
            ],
            "parse_errors": [],
        },
        "ui_crashes": {"findings": [], "parse_errors": [], "index_errors": []},
    }

    plan = create_plan(sims4, mods, payload, save=False)

    assert [candidate["unit_name"] for candidate in plan["active_candidates"]] == ["Zulu", "Alpha"]
    assert plan["active_candidates"][0]["evidence"][0]["reason"] == "active script suspect (high confidence)"


def test_create_plan_discovers_script_inside_symlinked_mod_unit(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    outside = tmp_path / "outside" / "Creator"
    script = outside / "Active.ts4script"
    mods.mkdir(parents=True)
    outside.mkdir(parents=True)
    script.write_bytes(b"script")
    (mods / "Creator").symlink_to(outside, target_is_directory=True)

    payload = {
        "summary": {"script_active": 1, "ui_active": 0},
        "script_crashes": {
            "ranked_mods": [
                {"mod": "Active.ts4script", "status": "active", "top_suspect_count": 1, "crash_count": 1},
            ],
            "findings": [
                {"suspects": [{"mod": "Active.ts4script", "status": "active", "confidence": "high"}]},
            ],
            "parse_errors": [],
        },
        "ui_crashes": {"findings": [], "parse_errors": [], "index_errors": []},
    }

    plan = create_plan(sims4, mods, payload, save=False)

    assert [candidate["unit_name"] for candidate in plan["active_candidates"]] == ["Creator"]
    assert plan["active_candidates"][0]["unit_path"] == str(mods / "Creator")
    assert plan["active_candidates"][0]["evidence"][0]["path"] == str(
        mods / "Creator" / "Active.ts4script"
    )
