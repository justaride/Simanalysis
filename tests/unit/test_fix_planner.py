from __future__ import annotations

from pathlib import Path

from simanalysis.fix_planner import create_fix_plan


def _kinds(plan: dict[str, object]) -> list[str]:
    actions = plan["actions"]
    assert isinstance(actions, list)
    return [str(action["kind"]) for action in actions]


def test_create_fix_plan_detects_read_only_cleanup_candidates(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    (mods / "Alpha").mkdir(parents=True)
    (mods / "Beta").mkdir()
    (mods / "Deep" / "Nested").mkdir(parents=True)

    (mods / "Alpha" / "duplicate.package").write_bytes(b"same")
    (mods / "Beta" / "duplicate.package").write_bytes(b"same")
    (mods / "Deep" / "Nested" / "risky.ts4script").write_bytes(b"script")
    (mods / "Alpha" / "shadow.package").write_bytes(b"shadow")

    disabled = sims4 / "_Disabled_Backup"
    disabled.mkdir()
    (disabled / "shadow.package").write_bytes(b"shadow")

    (sims4 / "localthumbcache.package").write_bytes(b"cache")

    plan = create_fix_plan(sims4)

    assert plan["schema_version"] == 1
    assert plan["dry_run"] is True
    assert plan["sims4_dir"] == str(sims4.resolve())
    assert plan["summary"] == {
        "actions": 4,
        "high": 1,
        "medium": 2,
        "low": 1,
        "warnings": 0,
        "blockers": 0,
    }
    assert _kinds(plan) == [
        "script_too_deep",
        "active_duplicate_file",
        "disabled_shadow_copy",
        "cache_cleanup_candidate",
    ]
    applyable = {action["kind"]: action["can_apply"] for action in plan["actions"]}
    assert applyable == {
        "script_too_deep": False,
        "active_duplicate_file": False,
        "disabled_shadow_copy": False,
        "cache_cleanup_candidate": True,
    }
    for action in plan["actions"]:
        assert action["safety"] == "read_only_plan"

    assert not (sims4 / "_Simanalysis_Fixes").exists()
    assert not (sims4 / "_Simanalysis_Treatment").exists()


def test_create_fix_plan_is_empty_when_world_has_no_fix_candidates(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "Solo").mkdir()
    (mods / "Solo" / "only.package").write_bytes(b"package")

    plan = create_fix_plan(sims4)

    assert plan["actions"] == []
    assert plan["summary"] == {
        "actions": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "warnings": 0,
        "blockers": 0,
    }
