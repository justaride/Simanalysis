"""Tests for read-only Cache Doctor status."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from simanalysis.cache_doctor import (
    CacheCleaner,
    build_cache_cleanup_plan,
    build_cache_status,
    format_cache_status_text,
    load_cache_manifest,
    write_cache_cleanup_plan,
)
from simanalysis.cli import cli


def test_cache_status_reports_present_cache_targets_without_mutating(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    thumb = sims4 / "localthumbcache.package"
    thumb.write_bytes(b"thumb-cache")
    cache_dir = sims4 / "cache"
    cache_dir.mkdir()
    (cache_dir / "cached.bin").write_bytes(b"cached")

    status = build_cache_status(sims4)

    assert status["status"] == "review_recommended"
    assert status["root_path"] == str(sims4.resolve())
    targets = {target["id"]: target for target in status["targets"]}
    assert targets["localthumbcache"]["present"] is True
    assert targets["localthumbcache"]["size_bytes"] == len(b"thumb-cache")
    assert targets["cache_dir"]["present"] is True
    assert targets["cache_dir"]["item_count"] == 1
    assert status["mutates_files"] is False
    assert thumb.exists()
    assert (cache_dir / "cached.bin").exists()
    assert any("plan/apply" in item for item in status["recommendations"])


def test_cache_status_is_clear_when_known_targets_are_absent(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    status = build_cache_status(sims4)

    assert status["status"] == "no_cache_targets_found"
    assert all(target["present"] is False for target in status["targets"])
    assert status["recommendations"] == [
        "No known Sims 4 cache targets were found in the selected folder."
    ]


def test_cache_status_skips_symlinked_cache_targets(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    external = tmp_path / "external-cache"
    external.mkdir()
    (sims4 / "cache").symlink_to(external, target_is_directory=True)

    status = build_cache_status(sims4)

    cache_target = next(target for target in status["targets"] if target["id"] == "cache_dir")
    assert cache_target["present"] is False
    assert cache_target["status"] == "skipped_symlink"
    assert any("symlink" in warning.lower() for warning in status["warnings"])


def test_format_cache_status_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"cache")

    text = format_cache_status_text(build_cache_status(sims4))

    assert "Cache Doctor" in text
    assert "Read-only: yes" in text
    assert "localthumbcache.package" in text


def test_cache_cli_status_outputs_json(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "avatarcache.package").write_bytes(b"avatar")

    result = CliRunner().invoke(cli, ["cache", "status", str(sims4), "--format", "json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert any(target["id"] == "avatarcache" for target in data["targets"])


def test_cache_cleanup_plan_targets_present_caches_without_mutating(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    thumb = sims4 / "localthumbcache.package"
    thumb.write_bytes(b"thumb-cache")
    cache_dir = sims4 / "cache"
    cache_dir.mkdir()
    (cache_dir / "cached.bin").write_bytes(b"cached")

    plan = build_cache_cleanup_plan(sims4)

    assert plan["status"] == "ready_for_review"
    assert plan["root_path"] == str(sims4.resolve())
    assert plan["action_count"] == 2
    assert plan["blocked_count"] == 0
    assert plan["requires_snapshot"] is True
    assert plan["mutates_files"] is False
    actions = {action["target_id"]: action for action in plan["actions"]}
    assert actions["localthumbcache"]["action_type"] == "quarantine_cache_target"
    assert actions["localthumbcache"]["status"] == "planned"
    assert actions["localthumbcache"]["source_relative_path"] == "localthumbcache.package"
    assert actions["localthumbcache"]["quarantine_relative_path"].startswith(
        "_Simanalysis_CacheDoctor/quarantine/"
    )
    assert actions["localthumbcache"]["expected"]["sha256"]
    assert actions["cache_dir"]["expected"]["item_count"] == 1
    assert thumb.exists()
    assert (cache_dir / "cached.bin").exists()
    assert not (sims4 / "_Simanalysis_CacheDoctor").exists()


def test_cache_cleanup_plan_blocks_symlinked_targets(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    external = tmp_path / "external-cache"
    sims4.mkdir()
    external.mkdir()
    (sims4 / "cache").symlink_to(external, target_is_directory=True)

    plan = build_cache_cleanup_plan(sims4)

    assert plan["status"] == "blocked"
    action = plan["actions"][0]
    assert action["target_id"] == "cache_dir"
    assert action["status"] == "blocked"
    assert "cache_target_symlink" in action["blockers"]
    assert external.exists()
    assert (sims4 / "cache").is_symlink()


def test_cache_cleaner_apply_and_restore_quarantines_without_deleting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.cache_doctor as cache_doctor

    monkeypatch.setattr(cache_doctor, "assert_sims_not_running", lambda: None)
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    thumb = sims4 / "localthumbcache.package"
    thumb.write_bytes(b"thumb-cache")
    cache_dir = sims4 / "cache"
    cache_dir.mkdir()
    (cache_dir / "cached.bin").write_bytes(b"cached")
    plan = write_cache_cleanup_plan(
        build_cache_cleanup_plan(sims4),
        tmp_path / "cache-plan.json",
    )

    manifest = CacheCleaner(clock=lambda: "2026-06-15T10:00:00Z").apply(
        plan["manifest_path"],
        selected_action_ids=["cache-clear-001", "cache-clear-002"],
    )

    manifest_path = Path(manifest["manifest_path"])
    assert manifest["status"] == "applied"
    assert manifest["mutates_files"] is True
    assert manifest_path.exists()
    assert not thumb.exists()
    assert not cache_dir.exists()
    assert Path(manifest["actions"][0]["quarantine_path"]).exists()
    assert Path(manifest["actions"][1]["quarantine_path"]).is_dir()

    restored = CacheCleaner().restore(manifest_path)

    assert restored["status"] == "restored"
    assert thumb.read_bytes() == b"thumb-cache"
    assert (cache_dir / "cached.bin").read_bytes() == b"cached"
    assert all(action["status"] == "restored" for action in restored["actions"])


def test_cache_cleaner_blocks_when_game_process_guard_fires(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.cache_doctor as cache_doctor

    monkeypatch.setattr(
        cache_doctor,
        "assert_sims_not_running",
        lambda: (_ for _ in ()).throw(ValueError("The Sims 4 is running")),
    )
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"thumb-cache")
    plan = write_cache_cleanup_plan(
        build_cache_cleanup_plan(sims4),
        tmp_path / "cache-plan.json",
    )

    with pytest.raises(ValueError, match="The Sims 4 is running"):
        CacheCleaner().apply(plan["manifest_path"], selected_action_ids=["cache-clear-001"])

    assert (sims4 / "localthumbcache.package").exists()


def test_cache_cleaner_restore_refuses_modified_destination(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.cache_doctor as cache_doctor

    monkeypatch.setattr(cache_doctor, "assert_sims_not_running", lambda: None)
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"thumb-cache")
    plan = write_cache_cleanup_plan(
        build_cache_cleanup_plan(sims4),
        tmp_path / "cache-plan.json",
    )
    manifest = CacheCleaner().apply(
        plan["manifest_path"],
        selected_action_ids=["cache-clear-001"],
    )
    (sims4 / "localthumbcache.package").write_bytes(b"user-new-cache")

    with pytest.raises(ValueError, match="Cache restore destination already exists"):
        CacheCleaner().restore(manifest["manifest_path"])

    assert (sims4 / "localthumbcache.package").read_bytes() == b"user-new-cache"
    assert load_cache_manifest(manifest["manifest_path"])["status"] == "applied"


def test_cache_cli_plan_apply_restore_round_trip(tmp_path: Path, monkeypatch) -> None:
    import simanalysis.cache_doctor as cache_doctor

    monkeypatch.setattr(cache_doctor, "assert_sims_not_running", lambda: None)
    sims4 = tmp_path / "The Sims 4"
    plan_path = tmp_path / "cache-plan.json"
    sims4.mkdir()
    (sims4 / "avatarcache.package").write_bytes(b"avatar")
    runner = CliRunner()

    planned = runner.invoke(
        cli,
        [
            "cache",
            "plan",
            str(sims4),
            "--output",
            str(plan_path),
            "--format",
            "json",
        ],
    )

    assert planned.exit_code == 0, planned.output
    plan = json.loads(planned.output)
    assert plan["manifest_path"] == str(plan_path.resolve())

    applied = runner.invoke(
        cli,
        [
            "cache",
            "apply",
            str(plan_path),
            "--action",
            "cache-clear-001",
            "--format",
            "json",
        ],
    )

    assert applied.exit_code == 0, applied.output
    manifest = json.loads(applied.output)
    assert manifest["status"] == "applied"
    assert not (sims4 / "avatarcache.package").exists()

    restored = runner.invoke(
        cli,
        ["cache", "restore", manifest["manifest_path"], "--format", "json"],
    )

    assert restored.exit_code == 0, restored.output
    assert json.loads(restored.output)["status"] == "restored"
    assert (sims4 / "avatarcache.package").read_bytes() == b"avatar"
