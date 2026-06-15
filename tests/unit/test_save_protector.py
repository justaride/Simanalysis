"""Tests for read-only Save Protector status."""

import json
from pathlib import Path

from click.testing import CliRunner

from simanalysis.cli import cli
from simanalysis.save_protector import (
    build_save_protector_status,
    detect_case_collisions,
    format_save_protector_text,
)


def test_save_protector_groups_primary_saves_and_backups_without_mutating(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    saves = sims4 / "saves"
    saves.mkdir(parents=True)
    primary = saves / "Slot_00000001.save"
    backup = saves / "Slot_00000001.save.ver0"
    orphan_backup = saves / "Slot_00000002.save.ver1"
    primary.write_bytes(b"primary-save")
    backup.write_bytes(b"backup-save")
    orphan_backup.write_bytes(b"backup-only")

    status = build_save_protector_status(sims4)

    assert status["status"] == "review_recommended"
    assert status["root_path"] == str(sims4.resolve())
    assert status["saves_path"] == str(saves.resolve())
    assert status["primary_save_count"] == 1
    assert status["backup_count"] == 2
    assert status["mutates_files"] is False
    groups = {group["slot"]: group for group in status["save_groups"]}
    assert groups["Slot_00000001"]["primary"]["name"] == "Slot_00000001.save"
    assert groups["Slot_00000001"]["backup_count"] == 1
    assert groups["Slot_00000002"]["primary"] is None
    assert groups["Slot_00000002"]["backup_count"] == 1
    assert primary.exists()
    assert backup.exists()
    assert any("copy" in item.lower() for item in status["recommendations"])


def test_save_protector_reports_missing_saves_folder(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    status = build_save_protector_status(sims4)

    assert status["status"] == "missing_saves_folder"
    assert status["primary_save_count"] == 0
    assert status["backup_count"] == 0
    assert status["save_groups"] == []
    assert status["signals"][0]["id"] == "missing_saves_folder"


def test_save_protector_surfaces_macos_and_path_safety_signals(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    saves = sims4 / "saves"
    saves.mkdir(parents=True)
    (saves / "._Slot_00000001.save").write_bytes(b"appledouble")
    (saves / "Slot_00000002.save.icloud").write_bytes(b"icloud")
    external = tmp_path / "external.save"
    external.write_bytes(b"external")
    (saves / "Slot_00000003.save").symlink_to(external)

    status = build_save_protector_status(sims4)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert {"appledouble_noise", "icloud_placeholder", "symlink_skipped"} <= signal_ids
    assert any("symlink" in warning.lower() for warning in status["warnings"])
    assert status["primary_save_count"] == 0


def test_detect_case_collisions_is_casefold_based() -> None:
    signals = detect_case_collisions(
        [
            "saves/Slot_0000000A.save",
            "saves/slot_0000000a.save",
            "saves/Slot_0000000B.save",
        ]
    )

    assert len(signals) == 1
    assert signals[0]["id"] == "case_collision"
    assert signals[0]["paths"] == [
        "saves/Slot_0000000A.save",
        "saves/slot_0000000a.save",
    ]


def test_format_save_protector_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    saves = sims4 / "saves"
    saves.mkdir(parents=True)
    (saves / "Slot_00000001.save").write_bytes(b"save")

    text = format_save_protector_text(build_save_protector_status(sims4))

    assert "Save Protector" in text
    assert "Read-only: yes" in text
    assert "Slot_00000001" in text


def test_save_protector_cli_status_outputs_json(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    saves = sims4 / "saves"
    saves.mkdir(parents=True)
    (saves / "Slot_00000001.save").write_bytes(b"save")

    result = CliRunner().invoke(
        cli,
        ["save-protector", "status", str(sims4), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert data["primary_save_count"] == 1
    assert data["mutates_files"] is False
