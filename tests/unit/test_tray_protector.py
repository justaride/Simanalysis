"""Tests for read-only Tray dependency status."""

import json
from pathlib import Path

from click.testing import CliRunner

from simanalysis.cli import cli
from simanalysis.tray_protector import (
    build_tray_status,
    detect_case_collisions,
    format_tray_status_text,
)


def test_tray_status_groups_tray_files_and_sidecar_signals_without_mutating(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    anchored = tray / "family.trayitem"
    household_info = tray / "family.hhi"
    orphan_sidecar = tray / "lot_without_anchor.bpi"
    anchored.write_bytes(b"tray")
    household_info.write_bytes(b"hhi")
    orphan_sidecar.write_bytes(b"bpi")

    status = build_tray_status(sims4)

    assert status["status"] == "review_recommended"
    assert status["root_path"] == str(sims4.resolve())
    assert status["tray_path"] == str(tray.resolve())
    assert status["tray_file_count"] == 3
    assert status["group_count"] == 2
    assert status["anchored_group_count"] == 1
    assert status["sidecar_only_group_count"] == 1
    assert status["mutates_files"] is False
    groups = {group["stem"]: group for group in status["groups"]}
    assert groups["family"]["has_trayitem"] is True
    assert groups["family"]["type_hint"] == "Household"
    assert groups["lot_without_anchor"]["has_trayitem"] is False
    signal_ids = {signal["id"] for signal in status["signals"]}
    assert "probable_build_buy_sidecar_without_anchor" in signal_ids
    assert anchored.exists()
    assert household_info.exists()
    assert orphan_sidecar.exists()


def test_tray_dependency_signals_are_confidence_labeled(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    (tray / "family.trayitem").write_bytes(b"tray")
    (tray / "family.hhi").write_bytes(b"hhi")
    (tray / "lot.trayitem").write_bytes(b"tray")
    (tray / "lot.bpi").write_bytes(b"bpi")
    (tray / "orphan.blueprint").write_bytes(b"blueprint")
    (tray / "solo.trayitem").write_bytes(b"tray")

    status = build_tray_status(sims4)

    groups = {group["stem"]: group for group in status["groups"]}
    family_signal = groups["family"]["dependency_signals"][0]
    lot_signal = groups["lot"]["dependency_signals"][0]
    orphan_signal = groups["orphan"]["dependency_signals"][0]
    solo_signal = groups["solo"]["dependency_signals"][0]

    assert family_signal["id"] == "likely_cas_dependency_scope"
    assert family_signal["dependency_kind"] == "cas"
    assert family_signal["confidence"] == "likely"
    assert family_signal["evidence"]
    assert lot_signal["id"] == "likely_build_buy_dependency_scope"
    assert lot_signal["dependency_kind"] == "build_buy"
    assert lot_signal["confidence"] == "likely"
    assert orphan_signal["id"] == "probable_build_buy_sidecar_without_anchor"
    assert orphan_signal["confidence"] == "probable"
    assert orphan_signal["anchor_state"] == "missing"
    assert solo_signal["id"] == "unknown_dependency_scope"
    assert solo_signal["confidence"] == "unknown"
    assert all("guarantee" not in signal["message"].lower() for signal in status["signals"])


def test_tray_status_reports_missing_tray_folder(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    status = build_tray_status(sims4)

    assert status["status"] == "missing_tray_folder"
    assert status["tray_file_count"] == 0
    assert status["groups"] == []
    assert status["signals"][0]["id"] == "missing_tray_folder"


def test_tray_status_surfaces_macos_and_path_safety_signals(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    (tray / "._family.trayitem").write_bytes(b"appledouble")
    (tray / "evicted.trayitem.icloud").write_bytes(b"icloud")
    external = tmp_path / "external.trayitem"
    external.write_bytes(b"external")
    (tray / "linked.trayitem").symlink_to(external)

    status = build_tray_status(sims4)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert {"appledouble_noise", "icloud_placeholder", "symlink_skipped"} <= signal_ids
    assert status["tray_file_count"] == 0
    assert any("symlink" in warning.lower() for warning in status["warnings"])


def test_detect_case_collisions_is_casefold_based() -> None:
    signals = detect_case_collisions(
        [
            "Tray/Family.trayitem",
            "Tray/family.trayitem",
            "Tray/Other.trayitem",
        ]
    )

    assert len(signals) == 1
    assert signals[0]["id"] == "case_collision"
    assert signals[0]["paths"] == [
        "Tray/Family.trayitem",
        "Tray/family.trayitem",
    ]


def test_format_tray_status_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    (tray / "family.trayitem").write_bytes(b"tray")

    text = format_tray_status_text(build_tray_status(sims4))

    assert "Tray Protector" in text
    assert "Read-only: yes" in text
    assert "family" in text
    assert "[unknown; unknown]" in text


def test_tray_status_cli_outputs_json(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    (tray / "family.trayitem").write_bytes(b"tray")

    result = CliRunner().invoke(
        cli,
        ["tray", "status", str(sims4), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert data["tray_file_count"] == 1
    assert data["mutates_files"] is False
