from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

import simanalysis.treatment as treatment
from simanalysis.treatment import (
    apply_next_step,
    assert_safe_unit_move,
    contains_symlink,
    create_plan,
    load_session,
    record_outcome,
    restore_session,
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
                            "package_path": str(
                                ui_path.parent.parent / "_Disabled" / "old.package"
                            ),
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


def _saved_bisect_session(tmp_path: Path, names: list[str]) -> tuple[Path, Path, Path]:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    for name in names:
        unit = mods / name
        unit.mkdir(parents=True)
        (unit / f"{name}.package").write_bytes(name.encode())

    candidates = [
        {
            "unit_path": str(mods / name),
            "unit_name": name,
            "unit_kind": "folder",
            "evidence": [],
            "rank": index,
        }
        for index, name in enumerate(names)
    ]
    now = treatment.utc_now().isoformat().replace("+00:00", "Z")
    manifest_path = sims4 / "_Simanalysis_Treatment" / "bisect-test.json"
    disabled_dir = sims4 / "_Disabled_Simanalysis_Bisect_test"
    session: dict[str, object] = {
        "version": 1,
        "session_id": "bisect-test",
        "created_at": now,
        "updated_at": now,
        "sims4_dir": str(sims4),
        "mods_dir": str(mods),
        "disabled_dir": str(disabled_dir),
        "manifest_path": str(manifest_path),
        "status": "planned",
        "active_candidates": candidates,
        "remaining_candidates": [candidate["unit_path"] for candidate in candidates],
        "current_removed": [],
        "next_batch": [str(mods / name) for name in names[: (len(names) + 1) // 2]],
        "steps": [],
        "warnings": [],
        "blockers": [],
    }
    manifest = Path(cast(str, session["manifest_path"]))
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(session), encoding="utf-8")
    return manifest, mods, disabled_dir


def _allow_file_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(treatment, "assert_sims_not_running", lambda: None)


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
                {
                    "mod": "Low.ts4script",
                    "status": "active",
                    "top_suspect_count": 1,
                    "crash_count": 1,
                },
                {
                    "mod": "High.ts4script",
                    "status": "active",
                    "top_suspect_count": 1,
                    "crash_count": 1,
                },
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
    assert (
        plan["active_candidates"][0]["evidence"][0]["reason"]
        == "active script suspect (high confidence)"
    )


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
                {
                    "mod": "Active.ts4script",
                    "status": "active",
                    "top_suspect_count": 1,
                    "crash_count": 1,
                },
            ],
            "findings": [
                {
                    "suspects": [
                        {"mod": "Active.ts4script", "status": "active", "confidence": "high"}
                    ]
                },
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


def test_load_session_rejects_missing_mutation_fields(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.pop("current_removed")
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="current_removed"):
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


def test_load_session_rejects_non_string_path_fields(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["mods_dir"] = ["not", "a", "path"]
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="mods_dir must be a string"):
        load_session(manifest)


def test_load_session_rejects_non_list_candidate_fields(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["remaining_candidates"] = "not-a-list"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="remaining_candidates must be a list"):
        load_session(manifest)


def test_load_session_rejects_unknown_status(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["status"] = "surprising"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown treatment session status"):
        load_session(manifest)


def test_load_session_rejects_non_list_steps(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["steps"] = {"step": "bad"}
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="steps must be a list"):
        load_session(manifest)


def test_load_session_rejects_mods_dir_outside_sims4(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    outside_mods = tmp_path / "Other Mods"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["mods_dir"] = str(outside_mods)
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Sims 4 Mods folder"):
        load_session(manifest)


def test_load_session_rejects_disabled_dir_outside_sims4(tmp_path: Path) -> None:
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha"])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["disabled_dir"] = str(tmp_path / "_Disabled_Simanalysis_Bisect_outside")
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Simanalysis bisect folder"):
        load_session(manifest)


def test_assert_sims_not_running_rejects_running_sims(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> treatment.subprocess.CompletedProcess[str]:
        return treatment.subprocess.CompletedProcess(
            args=["ps"],
            returncode=0,
            stdout="/Applications/The Sims 4.app\n",
        )

    monkeypatch.setattr(treatment.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="The Sims 4 is running"):
        treatment.assert_sims_not_running()


def test_assert_sims_not_running_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: object, **kwargs: object) -> treatment.subprocess.CompletedProcess[str]:
        raise treatment.subprocess.CalledProcessError(1, ["ps"])

    monkeypatch.setattr(treatment.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="running processes could not be checked"):
        treatment.assert_sims_not_running()


def test_assert_safe_unit_move_rejects_symlinked_mods_root(tmp_path: Path) -> None:
    real_mods = tmp_path / "real-mods"
    real_mods.mkdir()
    mods = tmp_path / "The Sims 4" / "Mods"
    mods.parent.mkdir()
    mods.symlink_to(real_mods, target_is_directory=True)
    source = mods / "Creator"
    source.mkdir()
    disabled = tmp_path / "The Sims 4" / "_Disabled_Simanalysis_Bisect_test"
    disabled.mkdir()

    with pytest.raises(ValueError, match="Mods folder must not be a symlink"):
        assert_safe_unit_move(source, disabled / "Creator", mods, disabled)


def test_apply_next_step_moves_first_half_and_updates_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])

    session = apply_next_step(manifest)

    removed = [str(mods / "Alpha"), str(mods / "Beta")]
    assert session["status"] == "awaiting_result"
    assert session["steps"][0]["status"] == "applied"
    assert session["current_removed"] == removed
    assert session["next_batch"] == []
    assert [record["status"] for record in session["steps"][0]["removed_units"]] == [
        "moved",
        "moved",
    ]
    assert not (mods / "Alpha").exists()
    assert not (mods / "Beta").exists()
    assert (disabled / "Alpha").is_dir()
    assert (disabled / "Beta").is_dir()

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["status"] == "awaiting_result"
    assert saved["steps"][0]["status"] == "applied"
    assert saved["current_removed"] == removed


def test_record_outcome_rejects_non_applied_latest_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["steps"][-1]["status"] = "awaiting_result"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Latest treatment step is not applied"):
        record_outcome(manifest, "same_issue")


def test_record_same_issue_restores_removed_batch_and_narrows_to_other_half(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)

    session = record_outcome(manifest, "same_issue")

    assert session["status"] == "confirmed_candidate"
    assert session["remaining_candidates"] == [str(mods / "Gamma")]
    assert session["current_removed"] == []
    assert session["next_batch"] == []
    assert session["steps"][-1]["outcome"] == "same_issue"
    assert (mods / "Alpha").is_dir()
    assert (mods / "Beta").is_dir()
    assert not (disabled / "Alpha").exists()
    assert not (disabled / "Beta").exists()


def test_same_issue_late_save_failure_keeps_narrowed_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    real_write_session = treatment._write_session
    calls = 0

    def flaky_write_session(session: dict) -> dict:
        nonlocal calls
        calls += 1
        if calls == 6:
            raise OSError("disk full")
        return real_write_session(session)

    monkeypatch.setattr(treatment, "_write_session", flaky_write_session)

    with pytest.raises(OSError, match="disk full"):
        record_outcome(manifest, "same_issue")

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["remaining_candidates"] == [str(mods / "Gamma")]
    assert saved["current_removed"] == []
    assert saved["steps"][-1]["outcome"] == "same_issue"
    assert saved["steps"][-1]["status"] == "restored"
    assert (mods / "Alpha").is_dir()
    assert (mods / "Beta").is_dir()
    assert not (disabled / "Alpha").exists()
    assert not (disabled / "Beta").exists()


def test_same_issue_restore_retry_finalizes_after_collision_is_fixed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    (mods / "Beta").mkdir()

    with pytest.raises(ValueError, match="Restore destination already exists"):
        record_outcome(manifest, "same_issue")

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert saved["remaining_candidates"] == [str(mods / "Gamma")]
    assert saved["current_removed"] == [str(mods / "Beta")]
    assert saved["steps"][-1]["outcome"] == "same_issue"
    assert (mods / "Alpha").is_dir()
    assert (disabled / "Beta").is_dir()

    (mods / "Beta").rmdir()
    restored = restore_session(manifest)

    assert restored["status"] == "confirmed_candidate"
    assert restored["remaining_candidates"] == [str(mods / "Gamma")]
    assert restored["current_removed"] == []
    assert restored["steps"][-1]["status"] == "restored"
    assert (mods / "Beta").is_dir()
    assert not (disabled / "Beta").exists()


def test_record_issue_gone_keeps_removed_batch_as_remaining(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)

    session = record_outcome(manifest, "issue_gone")

    removed = [str(mods / "Alpha"), str(mods / "Beta")]
    assert session["status"] == "planned"
    assert session["remaining_candidates"] == removed
    assert session["current_removed"] == removed
    assert session["next_batch"] == removed[:1]
    assert [record["status"] for record in session["steps"][-1]["removed_units"]] == [
        "kept_disabled",
        "kept_disabled",
    ]
    assert not (mods / "Alpha").exists()
    assert (disabled / "Alpha").is_dir()


def test_apply_after_issue_gone_restores_held_batch_then_moves_next_half(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    record_outcome(manifest, "issue_gone")

    session = apply_next_step(manifest)

    assert session["status"] == "awaiting_result"
    assert session["remaining_candidates"] == [str(mods / "Alpha"), str(mods / "Beta")]
    assert session["current_removed"] == [str(mods / "Alpha")]
    assert session["steps"][0]["status"] == "restored"
    assert session["steps"][1]["status"] == "applied"
    assert session["steps"][1]["removed_units"][0]["source"] == str(mods / "Alpha")
    assert not (mods / "Alpha").exists()
    assert (mods / "Beta").is_dir()
    assert (disabled / "Alpha").is_dir()
    assert not (disabled / "Beta").exists()


def test_apply_save_failure_after_move_leaves_restorable_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    real_write_session = treatment._write_session
    calls = 0

    def flaky_write_session(session: dict) -> dict:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("disk full")
        return real_write_session(session)

    monkeypatch.setattr(treatment, "_write_session", flaky_write_session)

    with pytest.raises(OSError, match="disk full"):
        apply_next_step(manifest)

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    records = saved["steps"][-1]["removed_units"]
    assert saved["status"] == "blocked"
    assert saved["current_removed"] == [str(mods / "Alpha")]
    assert records[0]["status"] == "moved"
    assert not (mods / "Alpha").exists()
    assert (disabled / "Alpha").is_dir()

    restored = restore_session(manifest)

    assert restored["current_removed"] == []
    assert (mods / "Alpha").is_dir()
    assert not (disabled / "Alpha").exists()


def test_restore_latest_step_moves_units_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)

    session = restore_session(manifest)

    assert session["status"] == "planned"
    assert session["current_removed"] == []
    assert session["next_batch"] == [str(mods / "Alpha"), str(mods / "Beta")]
    assert [record["status"] for record in session["steps"][-1]["removed_units"]] == [
        "restored",
        "restored",
    ]
    assert session["steps"][-1]["status"] == "restored"
    assert (mods / "Alpha").is_dir()
    assert (mods / "Beta").is_dir()
    assert not (disabled / "Alpha").exists()


def test_restore_latest_step_rejects_nested_disabled_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    nested = disabled / "Nested"
    nested.mkdir()
    (disabled / "Alpha").rename(nested / "Alpha")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["steps"][-1]["removed_units"][0]["destination"] = str(nested / "Alpha")
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="direct child of active disabled folder"):
        restore_session(manifest)

    assert not (mods / "Alpha").exists()
    assert (nested / "Alpha").is_dir()


def test_restore_latest_step_saves_partial_progress_and_blocks_on_later_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, disabled = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    (mods / "Beta").mkdir()

    with pytest.raises(ValueError, match="Restore destination already exists"):
        restore_session(manifest)

    saved = json.loads(manifest.read_text(encoding="utf-8"))
    records = saved["steps"][-1]["removed_units"]
    assert saved["status"] == "blocked"
    assert saved["steps"][-1]["status"] == "blocked"
    assert saved["current_removed"] == [str(mods / "Beta")]
    assert records[0]["status"] == "restored"
    assert records[1]["status"] == "blocked"
    assert (mods / "Alpha").is_dir()
    assert not (disabled / "Alpha").exists()
    assert (disabled / "Beta").is_dir()

    (mods / "Beta").rmdir()
    restored = restore_session(manifest)

    assert restored["status"] == "planned"
    assert restored["current_removed"] == []
    assert restored["steps"][-1]["status"] == "restored"
    assert restored["steps"][-1]["removed_units"][1]["status"] == "restored"
    assert (mods / "Beta").is_dir()
    assert not (disabled / "Beta").exists()


def test_different_issue_marks_manual_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, _, _ = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)

    session = record_outcome(manifest, "different_issue")

    assert session["status"] == "manual_review"
    assert session["steps"][-1]["outcome"] == "different_issue"


def test_render_handoff_summarizes_session_and_recovery_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    manifest, mods, _ = _saved_bisect_session(tmp_path, ["Alpha", "Beta", "Gamma"])
    apply_next_step(manifest)
    session = record_outcome(manifest, "issue_gone")
    session["warnings"].append("Fixture warning: verify against the latest crash log.")
    session["blockers"].append("Fixture blocker: pause before another mutation.")

    handoff = treatment.render_handoff(session)

    assert "# Simanalysis Bisect Handoff" in handoff
    assert "Session: `bisect-test`" in handoff
    assert f"Manifest: `{manifest}`" in handoff
    assert "Status: `planned`" in handoff
    assert "Candidates: 3" in handoff
    assert "Remaining: 2" in handoff
    assert "Current Removed: 2" in handoff
    assert f"- `Alpha` - folder - `{mods / 'Alpha'}`" in handoff
    assert f"- `Beta` - folder - `{mods / 'Beta'}`" in handoff
    assert "Step `step-1` - `applied` - outcome `issue_gone`" in handoff
    assert "Fixture warning: verify against the latest crash log." in handoff
    assert "Fixture blocker: pause before another mutation." in handoff
    assert f'simanalysis bisect restore "{manifest}" --step all' in handoff
    assert f'simanalysis bisect record-verdict "{manifest}" --verdict same_issue' in handoff
    assert "Handoff generation is read-only" in handoff


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
