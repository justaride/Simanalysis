from __future__ import annotations

from pathlib import Path

from simanalysis.live_monitoring import (
    LiveMonitor,
    build_snapshot,
    changed_fingerprints,
    discover_log_files,
)


def test_discover_log_files_finds_script_and_ui_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    script_log = sims4 / "lastException.txt"
    ui_log = sims4 / "lastUIException_1.txt"
    ignored = sims4 / "notify.glob"
    script_log.write_text("script", encoding="utf-8")
    ui_log.write_text("ui", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")

    discovered = discover_log_files(sims4)

    assert [(item.kind, item.path.name) for item in discovered] == [
        ("script", "lastException.txt"),
        ("ui", "lastUIException_1.txt"),
    ]


def test_build_snapshot_records_stable_file_fingerprints(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    log = sims4 / "lastException.txt"
    log.write_text("first crash", encoding="utf-8")

    snapshot, warnings = build_snapshot(sims4)

    fingerprint = snapshot[str(log.resolve())]
    assert warnings == []
    assert fingerprint.path == str(log.resolve())
    assert fingerprint.name == "lastException.txt"
    assert fingerprint.kind == "script"
    assert fingerprint.size == len("first crash")
    assert fingerprint.mtime_ns > 0
    assert len(fingerprint.digest) == 16


def test_changed_fingerprints_detects_new_and_modified_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    script_log = sims4 / "lastException.txt"
    script_log.write_text("old", encoding="utf-8")
    previous, previous_warnings = build_snapshot(sims4)
    assert previous_warnings == []

    script_log.write_text("new content", encoding="utf-8")
    ui_log = sims4 / "lastUIException.txt"
    ui_log.write_text("ui", encoding="utf-8")
    current, current_warnings = build_snapshot(sims4)

    changed = changed_fingerprints(previous, current)

    assert current_warnings == []
    assert [item.name for item in changed] == ["lastException.txt", "lastUIException.txt"]


def test_build_snapshot_warns_when_log_cannot_be_read(monkeypatch, tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    log = sims4 / "lastException.txt"
    log.write_text("crash", encoding="utf-8")

    def fail_fingerprint(discovered):
        raise OSError("permission denied")

    monkeypatch.setattr(
        "simanalysis.live_monitoring.fingerprint_log",
        fail_fingerprint,
    )

    snapshot, warnings = build_snapshot(sims4)

    assert snapshot == {}
    assert warnings == ["Could not read lastException.txt: permission denied"]


def test_live_monitor_baseline_ignores_existing_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastException.txt").write_text("existing", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods)

    def fail_doctor_builder(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Doctor should not run when no log changed")

    def fail_treatment_planner(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Treatment should not run when no log changed")

    result = monitor.poll(fail_doctor_builder, fail_treatment_planner)

    assert result["changed_logs"] == []
    assert result["watched_log_count"] == 1
    assert result["doctor_summary"] == {}
    assert result["treatment"] == {
        "candidate_count": 0,
        "first_batch_count": 0,
        "manifest_path": None,
        "warnings": [],
        "blockers": [],
    }
    assert result["recommended_next_action"] == "waiting"


def test_live_monitor_with_empty_prior_snapshot_detects_existing_log(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastUIException.txt").write_text("ui crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})

    result = monitor.poll(
        lambda base, mods_dir, recursive: {
            "summary": {"script_reports": 0, "ui_findings": 1, "ui_active": 0},
            "script_crashes": {},
            "ui_crashes": {},
        },
        lambda base, mods_dir, doctor_payload, *, save=False: {
            "active_candidates": [],
            "next_batch": [],
            "manifest_path": None,
            "warnings": ["No active Doctor candidates can be moved."],
            "blockers": [],
        },
    )

    assert [log["name"] for log in result["changed_logs"]] == ["lastUIException.txt"]
