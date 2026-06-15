"""Tests for Patch Day Shield state and risk classification."""

import json
from pathlib import Path

import pytest

from simanalysis.patch_day import (
    build_patch_day_status,
    format_patch_day_text,
    record_patch_baseline,
)


def test_patch_day_status_marks_risk_classes_unknown_after_version_change(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "GameVersion.txt").write_text("1.108.329.1020\n", encoding="utf-8")
    state_path = tmp_path / "patch-day-state.json"
    state_path.write_text(
        json.dumps(
            {
                "roots": {
                    str(sims4.resolve()): {
                        "game_version": "1.107.151.1020",
                        "recorded_at": "2026-06-14T20:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    status = build_patch_day_status(sims4, state_path=state_path)

    assert status["status"] == "changed"
    assert status["patch_detected"] is True
    assert status["current_game_version"] == "1.108.329.1020"
    assert status["last_known_game_version"] == "1.107.151.1020"
    assert {risk["id"]: risk["status"] for risk in status["risk_classes"]} == {
        "script_mods": "unknown_after_patch",
        "ui_mods": "unknown_after_patch",
        "gameplay_tuning": "unknown_after_patch",
        "build_buy_and_cas": "unknown_after_patch",
    }
    assert status["automatic_reenable"] is False
    assert "vanilla test" in " ".join(status["recommendations"]).lower()
    assert "save copy" in " ".join(status["recommendations"]).lower()


def test_patch_day_status_can_include_classification_summary_without_safe_marking(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "GameVersion.txt").write_text("1.108.329.1020\n", encoding="utf-8")
    (mods / "helper.ts4script").write_bytes(b"script")
    state_path = tmp_path / "patch-day-state.json"
    state_path.write_text(
        json.dumps(
            {
                "roots": {
                    str(sims4.resolve()): {
                        "game_version": "1.107.151.1020",
                        "recorded_at": "2026-06-14T20:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    status = build_patch_day_status(sims4, state_path=state_path, mods_dir=mods)

    assert status["status"] == "changed"
    assert status["classification_summary"]["label_counts"] == {"script": 1}
    assert status["classification_summary"]["automatic_safe_marking"] is False
    assert status["risk_classes"][0]["status"] == "unknown_after_patch"


def test_record_patch_baseline_writes_current_game_version(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "GameVersion.txt").write_text("1.108.329.1020\n", encoding="utf-8")
    state_path = tmp_path / "patch-day-state.json"

    status = record_patch_baseline(
        sims4,
        state_path=state_path,
        recorded_at="2026-06-15T02:00:00Z",
    )

    assert status["status"] == "recorded"
    assert status["patch_detected"] is False
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["roots"][str(sims4.resolve())]["game_version"] == "1.108.329.1020"
    assert saved["roots"][str(sims4.resolve())]["recorded_at"] == "2026-06-15T02:00:00Z"


def test_patch_day_status_reports_missing_game_version_without_overclaiming(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    status = build_patch_day_status(sims4, state_path=tmp_path / "state.json")

    assert status["status"] == "missing_game_version"
    assert status["patch_detected"] is False
    assert status["risk_classes"] == []
    assert status["warnings"] == ["GameVersion.txt was not found in the selected Sims 4 folder."]


def test_record_patch_baseline_requires_game_version(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    with pytest.raises(ValueError, match=r"GameVersion\.txt"):
        record_patch_baseline(sims4, state_path=tmp_path / "state.json")


def test_format_patch_day_text_surfaces_changed_state() -> None:
    text = format_patch_day_text(
        {
            "status": "changed",
            "patch_detected": True,
            "current_game_version": "1.108.329.1020",
            "last_known_game_version": "1.107.151.1020",
            "risk_classes": [
                {
                    "label": "Script mods",
                    "status": "unknown_after_patch",
                    "reason": "Game version changed.",
                }
            ],
            "recommendations": ["Run a vanilla test before re-enabling mods."],
            "warnings": [],
        }
    )

    assert "Patch Day Shield" in text
    assert "Status: changed" in text
    assert "Script mods: unknown_after_patch" in text
    assert "Run a vanilla test" in text
