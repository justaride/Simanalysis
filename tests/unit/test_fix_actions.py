from __future__ import annotations

import json
from pathlib import Path

import pytest

import simanalysis.fix_actions as fix_actions
from simanalysis.fix_actions import apply_cache_cleanup, load_fix_session, restore_fix_session
from simanalysis.fix_planner import create_fix_plan


def _allow_file_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fix_actions, "assert_sims_not_running", lambda: None)


def test_cache_cleanup_action_is_applyable_in_fix_plan(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"cache")

    plan = create_fix_plan(sims4)

    action = plan["actions"][0]
    assert action["kind"] == "cache_cleanup_candidate"
    assert action["can_apply"] is True
    assert action["proposed_operation"] == "move_to_simanalysis_cache_backup"


def test_apply_cache_cleanup_moves_cache_with_manifest_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    cache_file = sims4 / "localthumbcache.package"
    cache_dir = sims4 / "cache"
    cache_file.write_bytes(b"cache")
    cache_dir.mkdir()
    (cache_dir / "thumb.dat").write_bytes(b"thumb")

    session = apply_cache_cleanup(sims4)

    manifest = Path(session["manifest_path"])
    assert manifest.exists()
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert saved["kind"] == "cache_cleanup"
    assert saved["status"] == "applied"
    assert len(saved["records"]) == 2
    assert not cache_file.exists()
    assert not cache_dir.exists()
    assert (Path(saved["backup_dir"]) / "localthumbcache.package").is_file()
    assert (Path(saved["backup_dir"]) / "cache").is_dir()


def test_restore_fix_session_moves_cache_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_file_moves(monkeypatch)
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    cache_file = sims4 / "localthumbcache.package"
    cache_file.write_bytes(b"cache")
    session = apply_cache_cleanup(sims4)

    restored = restore_fix_session(session["manifest_path"])

    assert restored["status"] == "restored"
    assert cache_file.is_file()
    assert not (Path(session["backup_dir"]) / "localthumbcache.package").exists()


def test_apply_cache_cleanup_refuses_when_sims_process_guard_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"cache")
    monkeypatch.setattr(
        fix_actions,
        "assert_sims_not_running",
        lambda: (_ for _ in ()).throw(ValueError("Refusing to move files while The Sims 4 is running")),
    )

    with pytest.raises(ValueError, match="The Sims 4 is running"):
        apply_cache_cleanup(sims4)

    assert (sims4 / "localthumbcache.package").is_file()
    assert not (sims4 / "_Simanalysis_Fixes").exists()


def test_load_fix_session_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Fix manifest not found"):
        load_fix_session(tmp_path / "missing.json")
