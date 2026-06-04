# mypy: disable-error-code="no-untyped-def,no-untyped-call"
import io
import json
import sys

import pytest

from simanalysis.bridge import commands, main


def _run(monkeypatch, argv):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    code = main(argv)
    return code, [json.loads(line) for line in buf.getvalue().splitlines()]


def test_scan_mods_full_sequence_exit_zero(monkeypatch, tmp_path):
    class FakeModAnalyzer:
        def __init__(self, calculate_hashes=True):
            pass

        def analyze_directory(self, path, recursive=True, progress_callback=None):
            progress_callback(1, 2, "a.package")
            progress_callback(2, 2, "b.package")
            return object()

        def get_summary(self, r):
            return {"total": 2}

        def get_recommendations(self, r):
            return []

    monkeypatch.setattr(commands, "ModAnalyzer", FakeModAnalyzer)
    monkeypatch.setattr(
        commands.serialization,
        "mod_result_to_dict",
        lambda a, r: {"summary": a.get_summary(r), "mods": []},
    )

    code, events = _run(monkeypatch, ["scan-mods", str(tmp_path)])
    kinds = [e["type"] for e in events]
    assert code == 0
    assert kinds[0] == "start"
    assert "progress" in kinds
    assert kinds[-2:] == ["result", "done"]
    assert all(e["v"] == 1 for e in events)


def test_invalid_path_emits_error_exit_two(monkeypatch):
    code, events = _run(monkeypatch, ["scan-mods", "/no/such/dir/zzz"])
    assert code == 2
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "INVALID_INPUT"


def test_doctor_scan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_doctor_scan(args, emit):
        called["path"] = args.path
        called["mods"] = args.mods
        called["recursive"] = args.recursive
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "doctor-scan", fake_doctor_scan)

    code, events = _run(monkeypatch, ["doctor-scan", str(tmp_path), "--mods", str(tmp_path)])

    assert code == 0
    assert called == {"path": str(tmp_path), "mods": str(tmp_path), "recursive": False}
    assert [event["type"] for event in events] == ["result", "done"]


def test_treatment_plan_command_is_dispatched_with_save(monkeypatch, tmp_path):
    called = {}

    def fake_treatment_plan(args, emit):
        called["args"] = args
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "treatment-plan", fake_treatment_plan)

    code, events = _run(monkeypatch, ["treatment-plan", str(tmp_path), "--save"])

    assert code == 0
    assert called["args"].path == str(tmp_path)
    assert called["args"].mods is None
    assert called["args"].doctor_json is None
    assert called["args"].save is True
    assert [event["type"] for event in events] == ["result", "done"]


def test_treatment_outcome_command_is_dispatched(monkeypatch):
    called = {}

    def fake_treatment_outcome(args, emit):
        called["args"] = args
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "treatment-outcome", fake_treatment_outcome)

    code, events = _run(
        monkeypatch,
        ["treatment-outcome", "manifest.json", "--outcome", "issue_gone"],
    )

    assert code == 0
    assert called["args"].manifest_path == "manifest.json"
    assert called["args"].outcome == "issue_gone"
    assert [event["type"] for event in events] == ["result", "done"]


def test_treatment_apply_restore_status_commands_are_dispatched(monkeypatch):
    called = []

    def fake_handler(args, emit):
        called.append((args.command, args.manifest_path, getattr(args, "step", None)))
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "treatment-apply", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "treatment-restore", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "treatment-status", fake_handler)

    apply_code, apply_events = _run(monkeypatch, ["treatment-apply", "manifest.json"])
    restore_code, restore_events = _run(
        monkeypatch,
        ["treatment-restore", "manifest.json", "--step", "all"],
    )
    status_code, status_events = _run(monkeypatch, ["treatment-status", "manifest.json"])

    assert apply_code == restore_code == status_code == 0
    assert called == [
        ("treatment-apply", "manifest.json", None),
        ("treatment-restore", "manifest.json", "all"),
        ("treatment-status", "manifest.json", None),
    ]
    assert [event["type"] for event in apply_events] == ["result", "done"]
    assert [event["type"] for event in restore_events] == ["result", "done"]
    assert [event["type"] for event in status_events] == ["result", "done"]


def test_live_monitor_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_live_monitor(args, emit):
        called["args"] = args
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "live-monitor", fake_live_monitor)

    code, events = _run(
        monkeypatch,
        [
            "live-monitor",
            str(tmp_path),
            "--mods",
            str(tmp_path),
            "--interval",
            "0.25",
            "--once",
        ],
    )

    assert code == 0
    assert called["args"].path == str(tmp_path)
    assert called["args"].mods == str(tmp_path)
    assert called["args"].interval == 0.25
    assert called["args"].once is True
    assert [event["type"] for event in events] == ["result", "done"]


def test_world_scan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_world_scan(args, emit):
        called["path"] = args.path
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "world-scan", fake_world_scan)

    code, events = _run(monkeypatch, ["world-scan", str(tmp_path)])

    assert code == 0
    assert called == {"path": str(tmp_path)}
    assert [event["type"] for event in events] == ["result", "done"]


def test_fix_plan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_fix_plan(args, emit):
        called["path"] = args.path
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "fix-plan", fake_fix_plan)

    code, events = _run(monkeypatch, ["fix-plan", str(tmp_path)])

    assert code == 0
    assert called == {"path": str(tmp_path)}
    assert [event["type"] for event in events] == ["result", "done"]


def test_master_plan_status_commands_are_dispatched(monkeypatch, tmp_path):
    called = []

    def fake_handler(args, emit):
        called.append((args.command, args.path))
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "master-plan", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "master-status", fake_handler)

    plan_code, plan_events = _run(monkeypatch, ["master-plan", str(tmp_path)])
    status_code, status_events = _run(monkeypatch, ["master-status", str(tmp_path)])

    assert plan_code == status_code == 0
    assert called == [
        ("master-plan", str(tmp_path)),
        ("master-status", str(tmp_path)),
    ]
    assert [event["type"] for event in plan_events] == ["result", "done"]
    assert [event["type"] for event in status_events] == ["result", "done"]


def test_master_baseline_commands_are_dispatched(monkeypatch, tmp_path):
    called = []

    def fake_handler(args, emit):
        called.append(
            (
                args.command,
                args.path,
                getattr(args, "label", None),
                getattr(args, "baseline", None),
            )
        )
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "master-baseline-save", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "master-baseline-diff", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "master-baseline-status", fake_handler)

    save_code, save_events = _run(
        monkeypatch,
        ["master-baseline-save", str(tmp_path), "--label", "initial"],
    )
    diff_code, diff_events = _run(
        monkeypatch,
        ["master-baseline-diff", str(tmp_path), "--baseline", "baseline.json"],
    )
    status_code, status_events = _run(monkeypatch, ["master-baseline-status", str(tmp_path)])

    assert save_code == diff_code == status_code == 0
    assert called == [
        ("master-baseline-save", str(tmp_path), "initial", None),
        ("master-baseline-diff", str(tmp_path), None, "baseline.json"),
        ("master-baseline-status", str(tmp_path), None, None),
    ]
    assert [event["type"] for event in save_events] == ["result", "done"]
    assert [event["type"] for event in diff_events] == ["result", "done"]
    assert [event["type"] for event in status_events] == ["result", "done"]


def test_fix_apply_restore_status_commands_are_dispatched(monkeypatch, tmp_path):
    called = []

    def fake_handler(args, emit):
        called.append((args.command, getattr(args, "path", None), getattr(args, "manifest_path", None), getattr(args, "kind", None)))
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "fix-apply", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "fix-restore", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "fix-session-status", fake_handler)

    apply_code, apply_events = _run(
        monkeypatch,
        ["fix-apply", str(tmp_path), "--kind", "cache_cleanup"],
    )
    restore_code, restore_events = _run(monkeypatch, ["fix-restore", "manifest.json"])
    status_code, status_events = _run(monkeypatch, ["fix-session-status", "manifest.json"])

    assert apply_code == restore_code == status_code == 0
    assert called == [
        ("fix-apply", str(tmp_path), None, "cache_cleanup"),
        ("fix-restore", None, "manifest.json", None),
        ("fix-session-status", None, "manifest.json", None),
    ]
    assert [event["type"] for event in apply_events] == ["result", "done"]
    assert [event["type"] for event in restore_events] == ["result", "done"]
    assert [event["type"] for event in status_events] == ["result", "done"]


def test_treatment_plan_malformed_doctor_json_is_invalid_input(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    doctor_json = tmp_path / "doctor.json"
    doctor_json.write_text(
        json.dumps(
            {
                "script_crashes": {"ranked_mods": [1], "findings": []},
                "ui_crashes": {"findings": [1]},
            }
        ),
        encoding="utf-8",
    )

    code, events = _run(
        monkeypatch,
        ["treatment-plan", str(sims4), "--doctor-json", str(doctor_json)],
    )

    assert code == 2
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "INVALID_INPUT"
    assert "Doctor JSON" in events[-1]["message"]


def test_unknown_command_argparse_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        main(["bogus-command"])
    assert exc.value.code == 2


def test_broken_pipe_returns_zero(monkeypatch, tmp_path):
    class FakeModAnalyzer:
        def __init__(self, calculate_hashes=True):
            pass

        def analyze_directory(self, path, recursive=True, progress_callback=None):
            raise BrokenPipeError()

    monkeypatch.setattr(commands, "ModAnalyzer", FakeModAnalyzer)
    code, _events = _run(monkeypatch, ["scan-mods", str(tmp_path)])
    assert code == 0


def test_internal_error_returns_one_with_error_event(monkeypatch, tmp_path):
    class FakeModAnalyzer:
        def __init__(self, calculate_hashes=True):
            pass

        def analyze_directory(self, path, recursive=True, progress_callback=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(commands, "ModAnalyzer", FakeModAnalyzer)
    code, events = _run(monkeypatch, ["scan-mods", str(tmp_path)])
    assert code == 1
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "INTERNAL"
