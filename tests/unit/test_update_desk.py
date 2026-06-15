"""Tests for read-only Update Desk staging status."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from click.testing import CliRunner

from simanalysis.cli import cli
from simanalysis.update_desk import (
    UpdateInstaller,
    build_update_install_plan,
    build_update_staging_status,
    format_update_install_plan_text,
    format_update_staging_text,
    load_update_manifest,
)


def test_update_staging_status_classifies_downloads_and_source_bindings(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Simanalysis Staging"
    staging.mkdir()
    archive = staging / "cool_mod.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("Mods/cool.package", b"package")
    (staging / "cool_mod.zip.source.json").write_text(
        json.dumps(
            {
                "source_url": "https://example.test/cool",
                "creator": "Example Creator",
                "downloaded_at": "2026-06-15T07:00:00Z",
            }
        )
    )
    package = staging / "loose.package"
    script = staging / "helper.ts4script"
    package.write_bytes(b"package")
    script.write_bytes(b"script")

    status = build_update_staging_status(staging)

    assert status["status"] == "review_recommended"
    assert status["staging_path"] == str(staging.resolve())
    assert status["item_count"] == 3
    assert status["archive_count"] == 1
    assert status["package_count"] == 1
    assert status["script_count"] == 1
    assert status["mutates_files"] is False
    items = {item["name"]: item for item in status["items"]}
    assert items["cool_mod.zip"]["kind"] == "archive"
    assert items["cool_mod.zip"]["archive_scan"]["status"] == "readable_zip"
    assert items["cool_mod.zip"]["archive_scan"]["member_count"] == 1
    assert items["cool_mod.zip"]["source_binding"]["status"] == "bound"
    assert items["loose.package"]["source_binding"]["status"] == "missing"
    assert package.exists()
    assert script.exists()
    assert archive.exists()


def test_update_staging_status_surfaces_archive_path_escape(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    archive = staging / "unsafe.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escape.package", b"package")

    status = build_update_staging_status(staging)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert "archive_path_escape" in signal_ids
    item = status["items"][0]
    assert item["archive_scan"]["status"] == "unsafe_members"
    assert item["archive_scan"]["unsafe_members"] == ["../escape.package"]
    assert archive.exists()


def test_update_staging_status_surfaces_corrupt_archives_and_path_safety(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "broken.zip").write_bytes(b"not a zip")
    (staging / "._broken.zip").write_bytes(b"appledouble")
    (staging / "download.package.icloud").write_bytes(b"icloud")
    external = tmp_path / "external.package"
    external.write_bytes(b"external")
    (staging / "linked.package").symlink_to(external)

    status = build_update_staging_status(staging)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert {
        "archive_unreadable",
        "appledouble_noise",
        "icloud_placeholder",
        "symlink_skipped",
    } <= signal_ids
    assert status["item_count"] == 1
    assert status["items"][0]["archive_scan"]["status"] == "unreadable_zip"


def test_update_staging_status_reports_missing_staging_folder(tmp_path: Path) -> None:
    staging = tmp_path / "Missing Staging"

    status = build_update_staging_status(staging)

    assert status["status"] == "missing_staging_folder"
    assert status["item_count"] == 0
    assert status["signals"][0]["id"] == "missing_staging_folder"
    assert status["mutates_files"] is False


def test_format_update_staging_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    text = format_update_staging_text(build_update_staging_status(staging))

    assert "Update Desk" in text
    assert "Read-only: yes" in text
    assert "loose.package" in text


def test_update_staging_status_cli_outputs_json(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    result = CliRunner().invoke(
        cli,
        ["updates", "status", str(staging), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert data["package_count"] == 1
    assert data["mutates_files"] is False


def test_update_install_plan_plans_loose_mod_files_without_mutating(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    package = staging / "loose.package"
    script = staging / "helper.ts4script"
    package.write_bytes(b"package")
    script.write_bytes(b"script")
    (staging / "loose.package.source.json").write_text(
        json.dumps({"source_url": "https://example.test/loose", "creator": "Creator"})
    )

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "ready_for_review"
    assert plan["staging_path"] == str(staging.resolve())
    assert plan["mods_path"] == str(mods.resolve())
    assert plan["mutates_files"] is False
    assert plan["mutates_mods"] is False
    assert plan["requires_snapshot"] is True
    assert plan["copy_count"] == 2
    assert plan["blocked_count"] == 0
    actions = {action["source_name"]: action for action in plan["actions"]}
    assert actions["loose.package"]["action_type"] == "copy_staged_file"
    assert actions["loose.package"]["status"] == "planned"
    assert actions["loose.package"]["destination_relative_path"] == "loose.package"
    assert actions["loose.package"]["expected"]["sha256"]
    assert actions["loose.package"]["source_binding"]["status"] == "bound"
    assert actions["helper.ts4script"]["destination_relative_path"] == "helper.ts4script"
    assert package.exists()
    assert script.exists()
    assert not (mods / "loose.package").exists()
    assert not (mods / "helper.ts4script").exists()


def test_update_install_plan_reviews_archives_without_extraction(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    archive = staging / "cool_mod.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("Mods/cool.package", b"package")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "ready_for_review"
    assert plan["archive_review_count"] == 1
    action = plan["actions"][0]
    assert action["action_type"] == "review_archive"
    assert action["status"] == "review_required"
    assert action["archive_scan"]["status"] == "readable_zip"
    assert action["archive_scan"]["member_count"] == 1
    assert action["destination_path"] is None
    assert archive.exists()
    assert not any(mods.iterdir())


def test_update_install_plan_blocks_unsafe_archive_and_destination_clashes(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (mods / "loose.package").write_bytes(b"existing")
    (mods / "Helper.ts4script").write_bytes(b"case collision")
    (staging / "loose.package").write_bytes(b"new")
    (staging / "helper.ts4script").write_bytes(b"script")
    with ZipFile(staging / "unsafe.zip", "w") as zip_file:
        zip_file.writestr("../escape.package", b"package")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "blocked"
    blockers = {blocker for action in plan["actions"] for blocker in action.get("blockers", [])}
    assert {"destination_exists", "case_collision", "archive_path_escape"} <= blockers
    assert not any(child.name == "helper.ts4script" for child in mods.iterdir())
    assert (mods / "Helper.ts4script").read_bytes() == b"case collision"


def test_format_update_install_plan_text_surfaces_manifest_gate(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    text = format_update_install_plan_text(build_update_install_plan(staging, mods))

    assert "Update Desk Install Plan" in text
    assert "Mods mutation: no" in text
    assert "Snapshot required: yes" in text
    assert "loose.package" in text


def test_update_install_plan_cli_outputs_json_and_writes_manifest(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    output = tmp_path / "plan.json"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    result = CliRunner().invoke(
        cli,
        [
            "updates",
            "plan",
            str(staging),
            "--mods",
            str(mods),
            "--output",
            str(output),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert data["status"] == "ready_for_review"
    assert data["manifest_path"] == str(output.resolve())
    assert saved == data
    assert data["mutates_mods"] is False
    assert not (mods / "loose.package").exists()


def test_update_commit_and_undo_cli_round_trip_with_manifest(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    plan_path = tmp_path / "update-plan.json"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    runner = CliRunner()
    assert (
        runner.invoke(
            cli,
            [
                "updates",
                "plan",
                str(staging),
                "--mods",
                str(mods),
                "--output",
                str(plan_path),
            ],
        ).exit_code
        == 0
    )

    commit = runner.invoke(
        cli,
        [
            "updates",
            "commit",
            str(plan_path),
            "--action",
            "update-copy-001",
            "--format",
            "json",
        ],
    )

    assert commit.exit_code == 0, commit.output
    applied = json.loads(commit.output)
    manifest_path = Path(applied["manifest_path"])
    assert applied["status"] == "applied"
    assert (mods / "loose.package").exists()

    undo = runner.invoke(
        cli,
        ["updates", "undo", str(manifest_path), "--format", "json"],
    )

    assert undo.exit_code == 0, undo.output
    restored = json.loads(undo.output)
    assert restored["status"] == "undone"
    assert not (mods / "loose.package").exists()


def test_update_commit_cli_requires_explicit_action_selection(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    plan_path = tmp_path / "update-plan.json"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    runner = CliRunner()
    assert (
        runner.invoke(
            cli,
            [
                "updates",
                "plan",
                str(staging),
                "--mods",
                str(mods),
                "--output",
                str(plan_path),
            ],
        ).exit_code
        == 0
    )

    result = runner.invoke(cli, ["updates", "commit", str(plan_path)])

    assert result.exit_code != 0
    assert "Choose at least one update action" in result.output


def test_update_installer_commits_and_undoes_selected_copy_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    source = staging / "loose.package"
    source.write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)

    manifest = UpdateInstaller(clock=lambda: "2026-06-15T09:00:00Z").commit_plan(
        plan,
        selected_action_ids=["update-copy-001"],
    )

    manifest_path = Path(manifest["manifest_path"])
    destination = mods / "loose.package"
    assert manifest["status"] == "applied"
    assert manifest["mutates_mods"] is True
    assert manifest_path.exists()
    assert source.exists()
    assert destination.read_bytes() == b"package"
    assert manifest["actions"][0]["status"] == "copied"
    assert (
        manifest["actions"][0]["installed"]["sha256"]
        == manifest["actions"][0]["expected"]["sha256"]
    )

    restored = UpdateInstaller().undo(manifest_path)

    assert restored["status"] == "undone"
    assert source.exists()
    assert not destination.exists()
    assert restored["actions"][0]["status"] == "undone"


def test_update_installer_requires_explicit_action_selection(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)

    with pytest.raises(ValueError, match="Choose at least one update action"):
        UpdateInstaller().stage_plan(plan)


def test_update_installer_refuses_stale_snapshot_before_copy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    source = staging / "loose.package"
    source.write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)
    source.write_bytes(b"changed")

    with pytest.raises(ValueError, match="no longer matches update plan evidence"):
        UpdateInstaller().commit_plan(plan, selected_action_ids=["update-copy-001"])

    assert not (mods / "loose.package").exists()


def test_update_installer_rejects_symlinked_source_without_copying(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    outside = tmp_path / "outside.package"
    staging.mkdir()
    mods.mkdir()
    outside.write_bytes(b"outside")
    source = staging / "loose.package"
    source.write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)
    source.unlink()
    source.symlink_to(outside)

    with pytest.raises(ValueError, match="symlinked update source"):
        UpdateInstaller().commit_plan(plan, selected_action_ids=["update-copy-001"])

    assert not (mods / "loose.package").exists()
    assert outside.read_bytes() == b"outside"


def test_update_installer_rejects_tampered_destination_escape(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)
    plan["actions"][0]["destination_relative_path"] = "../escape.package"
    plan["actions"][0]["destination_path"] = str(tmp_path / "escape.package")

    with pytest.raises(ValueError, match="Update destination must be under Mods"):
        UpdateInstaller().stage_plan(plan, selected_action_ids=["update-copy-001"])


def test_update_installer_blocks_when_game_process_guard_fires(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(
        update_desk,
        "assert_sims_not_running",
        lambda: (_ for _ in ()).throw(ValueError("The Sims 4 is running")),
    )
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)

    with pytest.raises(ValueError, match="The Sims 4 is running"):
        UpdateInstaller().commit_plan(plan, selected_action_ids=["update-copy-001"])

    assert not (mods / "loose.package").exists()


def test_update_installer_undo_recovers_copying_action_after_crash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    installer = UpdateInstaller()
    manifest = installer.stage_plan(
        build_update_install_plan(staging, mods),
        selected_action_ids=["update-copy-001"],
    )
    manifest_path = Path(manifest["manifest_path"])
    destination = mods / "loose.package"
    destination.write_bytes(b"package")
    manifest["status"] = "applying"
    manifest["actions"][0]["status"] = "copying"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    restored = installer.undo(manifest_path)

    assert restored["status"] == "undone"
    assert restored["actions"][0]["status"] == "undone"
    assert not destination.exists()


def test_update_installer_undo_refuses_modified_installed_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    manifest = UpdateInstaller().commit_plan(
        build_update_install_plan(staging, mods),
        selected_action_ids=["update-copy-001"],
    )
    destination = mods / "loose.package"
    destination.write_bytes(b"user changed it")

    with pytest.raises(ValueError, match="no longer matches update manifest evidence"):
        UpdateInstaller().undo(manifest["manifest_path"])

    assert destination.exists()
    assert load_update_manifest(manifest["manifest_path"])["status"] == "applied"
