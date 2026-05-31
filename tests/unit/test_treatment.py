from __future__ import annotations

import json
from pathlib import Path

import pytest

import simanalysis.treatment as treatment
from simanalysis.treatment import (
    assert_safe_unit_move,
    contains_symlink,
    create_plan,
    load_session,
    unit_for_path,
)


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


def test_create_plan_with_save_writes_manifest(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pkg = mods / "Creator" / "menu.package"
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b"x")

    plan = create_plan(sims4, mods, _doctor_payload(pkg), save=True)

    manifest = Path(plan["manifest_path"])
    assert manifest == sims4.resolve() / "_Simanalysis_Treatment" / f"{plan['session_id']}.json"
    assert manifest.exists()
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["status"] == "planned"
    assert saved["manifest_path"] == str(manifest)
    assert saved["active_candidates"][0]["unit_name"] == "Creator"


def test_create_plan_with_save_replaces_manifest_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pkg = mods / "Creator" / "menu.package"
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b"x")
    replacements: list[tuple[Path, Path]] = []
    real_replace = treatment.os.replace

    def record_replace(source: str | Path, destination: str | Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(treatment.os, "replace", record_replace)

    plan = create_plan(sims4, mods, _doctor_payload(pkg), save=True)

    manifest = Path(plan["manifest_path"])
    assert len(replacements) == 1
    temp_manifest, replaced_manifest = replacements[0]
    assert replaced_manifest == manifest
    assert temp_manifest.parent == manifest.parent
    assert temp_manifest.name.startswith(f".{manifest.name}.")
    assert not list(manifest.parent.glob(f".{manifest.name}.*.tmp"))


def test_load_session_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Manifest not found"):
        load_session(tmp_path / "missing.json")


def test_load_session_rejects_invalid_json(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.json"
    manifest.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Manifest is not valid JSON"):
        load_session(manifest)


def test_load_session_rejects_non_object_json(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.json"
    manifest.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="Manifest must be a JSON object"):
        load_session(manifest)


def test_load_session_rejects_missing_required_keys(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"version": 1, "session_id": "bisect-test"}), encoding="utf-8")

    with pytest.raises(ValueError, match="missing required keys"):
        load_session(manifest)


def test_load_session_rejects_unsupported_version(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 2,
                "session_id": "bisect-test",
                "sims4_dir": str(tmp_path),
                "mods_dir": str(tmp_path / "Mods"),
                "disabled_dir": str(tmp_path / "Disabled"),
                "status": "planned",
                "steps": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported treatment manifest version"):
        load_session(manifest)


def test_contains_symlink_detects_nested_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "link").symlink_to(tmp_path)

    assert contains_symlink(root) is True


def test_assert_safe_unit_move_allows_direct_mods_child_to_active_disabled_dir(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    source.mkdir(parents=True)
    disabled.mkdir(parents=True)

    assert_safe_unit_move(source, disabled / "Creator", mods, disabled)


def test_assert_safe_unit_move_rejects_symlink(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    mods.mkdir(parents=True)
    disabled.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    link = mods / "LinkOut"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        assert_safe_unit_move(link, disabled / "LinkOut", mods, disabled)


def test_assert_safe_unit_move_rejects_path_escape(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    outside = tmp_path / "outside"
    mods.mkdir(parents=True)
    disabled.mkdir(parents=True)
    outside.mkdir()

    with pytest.raises(ValueError, match="outside Mods"):
        assert_safe_unit_move(outside, disabled / "outside", mods, disabled)


def test_assert_safe_unit_move_rejects_missing_source(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    mods.mkdir(parents=True)
    disabled.mkdir(parents=True)

    with pytest.raises(ValueError, match="Source path is missing"):
        assert_safe_unit_move(mods / "Missing", disabled / "Missing", mods, disabled)


def test_assert_safe_unit_move_rejects_non_direct_child_of_mods(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator" / "Nested.package"
    source.parent.mkdir(parents=True)
    disabled.mkdir(parents=True)
    source.write_bytes(b"x")

    with pytest.raises(ValueError, match="direct child of Mods"):
        assert_safe_unit_move(source, disabled / "Nested.package", mods, disabled)


def test_assert_safe_unit_move_rejects_destination_outside_disabled_dir(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    source.mkdir(parents=True)
    disabled.mkdir(parents=True)

    with pytest.raises(ValueError, match="active disabled folder"):
        assert_safe_unit_move(source, sims4 / "Other" / "Creator", mods, disabled)


def test_assert_safe_unit_move_rejects_missing_disabled_dir(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    source.mkdir(parents=True)

    with pytest.raises(ValueError, match="Disabled folder does not exist"):
        assert_safe_unit_move(source, disabled / "Creator", mods, disabled)


def test_assert_safe_unit_move_rejects_symlinked_disabled_dir(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    real_disabled = tmp_path / "real-disabled"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    source.mkdir(parents=True)
    real_disabled.mkdir()
    disabled.symlink_to(real_disabled, target_is_directory=True)

    with pytest.raises(ValueError, match="Disabled folder must not be a symlink"):
        assert_safe_unit_move(source, disabled / "Creator", mods, disabled)


def test_assert_safe_unit_move_rejects_destination_collision(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    dest = disabled / "Creator"
    source.mkdir(parents=True)
    dest.mkdir(parents=True)

    with pytest.raises(ValueError, match="Destination already exists"):
        assert_safe_unit_move(source, dest, mods, disabled)
