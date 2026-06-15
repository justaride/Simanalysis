"""Tests for read-only Update Desk staging status."""

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo

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
    with ZipFile(script, "w") as zip_file:
        zip_file.writestr("helper.py", "import socket\n")

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
    assert items["loose.package"]["classification"]["label"] == "unknown"
    assert items["helper.ts4script"]["classification"]["label"] == "script"
    assert items["helper.ts4script"]["classification"]["confidence"] == "high"
    assert items["helper.ts4script"]["script_security"]["risk_level"] == "elevated"
    assert items["helper.ts4script"]["script_security"]["executes_code"] is False
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


def test_update_install_plan_plans_zip_members_to_extraction_staging_without_extracting(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    archive = staging / "cool_mod.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("Mods/cool.package", b"package")
        zip_file.writestr("nested/helper.ts4script", b"script")
        zip_file.writestr("readme.txt", b"readme")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "ready_for_review"
    assert plan["archive_review_count"] == 1
    assert plan["archive_member_count"] == 2
    member_actions = [
        action for action in plan["actions"] if action["action_type"] == "stage_archive_member"
    ]
    assert [action["archive_member_path"] for action in member_actions] == [
        "Mods/cool.package",
        "nested/helper.ts4script",
    ]
    package_action = member_actions[0]
    assert package_action["status"] == "planned"
    assert package_action["source_relative_path"] == "cool_mod.zip"
    assert package_action["destination_relative_path"] == "cool.package"
    assert package_action["destination_path"] == str(mods.resolve() / "cool.package")
    assert package_action["expected"] == {
        "size": len(b"package"),
        "sha256": sha256(b"package").hexdigest(),
    }
    assert package_action["extracts_directly_to_mods"] is False
    assert package_action["extraction_staging_relative_path"].startswith(
        "_Simanalysis_UpdateDesk/archive-members/cool_mod/"
    )
    assert package_action["extraction_staging_path"].startswith(str(staging.resolve()))
    assert not package_action["extraction_staging_path"].startswith(str(mods.resolve()))
    assert not (staging / "_Simanalysis_UpdateDesk").exists()
    assert not any(mods.iterdir())


def test_update_install_plan_blocks_duplicate_zip_member_destinations(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    with ZipFile(staging / "duplicates.zip", "w") as zip_file:
        zip_file.writestr("first/dupe.package", b"first")
        zip_file.writestr("second/dupe.package", b"second")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "blocked"
    member_actions = [
        action for action in plan["actions"] if action["action_type"] == "stage_archive_member"
    ]
    assert len(member_actions) == 2
    assert all("duplicate_destination" in action["blockers"] for action in member_actions)
    assert not (staging / "_Simanalysis_UpdateDesk").exists()
    assert not any(mods.iterdir())


def test_update_install_plan_blocks_unsafe_zip_members_without_planned_extraction(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    link_info = ZipInfo("Mods/link.package")
    link_info.external_attr = 0o120777 << 16
    with ZipFile(staging / "unsafe.zip", "w") as zip_file:
        zip_file.writestr("../escape.package", b"package")
        zip_file.writestr(link_info, b"target.package")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "blocked"
    assert plan["archive_member_count"] == 0
    archive_action = next(
        action for action in plan["actions"] if action["action_type"] == "review_archive"
    )
    assert {"archive_path_escape", "archive_symlink_entry"} <= set(archive_action["blockers"])
    assert not any(action["action_type"] == "stage_archive_member" for action in plan["actions"])
    assert not (staging / "_Simanalysis_UpdateDesk").exists()
    assert not any(mods.iterdir())


def test_update_install_plan_blocks_corrupt_zip_without_planned_extraction(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "broken.zip").write_bytes(b"not a zip")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "blocked"
    assert plan["archive_member_count"] == 0
    archive_action = plan["actions"][0]
    assert archive_action["action_type"] == "review_archive"
    assert archive_action["blockers"] == ["archive_unreadable"]
    assert not (staging / "_Simanalysis_UpdateDesk").exists()
    assert not any(mods.iterdir())


def test_update_install_plan_keeps_rar_and_7z_review_only_without_engine(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "creator.rar").write_bytes(b"rar")
    (staging / "set.7z").write_bytes(b"7z")

    plan = build_update_install_plan(staging, mods)

    assert plan["status"] == "blocked"
    assert plan["archive_member_count"] == 0
    actions = {action["source_name"]: action for action in plan["actions"]}
    assert actions["creator.rar"]["action_type"] == "review_archive"
    assert actions["creator.rar"]["archive_scan"]["status"] == "listing_unsupported"
    assert actions["creator.rar"]["blockers"] == ["archive_listing_unsupported"]
    assert actions["set.7z"]["archive_scan"]["status"] == "listing_unsupported"
    assert not any(action["action_type"] == "stage_archive_member" for action in plan["actions"])
    assert not (staging / "_Simanalysis_UpdateDesk").exists()
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("requires_snapshot", False, "must require snapshot approval"),
        ("mutates_files", True, "must be read-only"),
        ("mutates_mods", True, "must not declare Mods mutation"),
    ],
)
def test_update_installer_refuses_tampered_plan_safety_gates(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    plan = build_update_install_plan(staging, mods)
    plan[field] = value

    with pytest.raises(ValueError, match=message):
        UpdateInstaller().stage_plan(plan, selected_action_ids=["update-copy-001"])

    assert not (mods / "loose.package").exists()


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


def test_update_installer_refuses_stale_source_size_before_copy(
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
    source.write_bytes(b"changed-size")

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


def test_update_installer_partial_copy_failure_can_be_undone(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import simanalysis.update_desk as update_desk

    real_copy2 = update_desk.shutil.copy2
    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)

    def flaky_copy2(source: str, destination: str) -> str:
        if Path(source).name == "second.package":
            raise OSError("simulated copy failure")
        return str(real_copy2(source, destination))

    monkeypatch.setattr(update_desk.shutil, "copy2", flaky_copy2)
    staging = tmp_path / "Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "first.package").write_bytes(b"first")
    (staging / "second.package").write_bytes(b"second")
    installer = UpdateInstaller()
    manifest = installer.stage_plan(
        build_update_install_plan(staging, mods),
        selected_action_ids=["update-copy-001", "update-copy-002"],
    )
    manifest_path = Path(manifest["manifest_path"])

    with pytest.raises(OSError, match="simulated copy failure"):
        installer.apply(manifest_path)

    partial = load_update_manifest(manifest_path)
    assert partial["status"] == "partial"
    assert [action["status"] for action in partial["actions"]] == ["copied", "blocked"]
    assert (mods / "first.package").exists()
    assert not (mods / "second.package").exists()

    restored = installer.undo(manifest_path)

    assert restored["status"] == "undone"
    assert [action["status"] for action in restored["actions"]] == ["undone", "blocked"]
    assert not (mods / "first.package").exists()
    assert not (mods / "second.package").exists()


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
