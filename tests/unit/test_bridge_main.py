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
        called["inventory_db"] = args.inventory_db
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "doctor-scan", fake_doctor_scan)

    db_path = tmp_path / "inventory.sqlite3"
    code, events = _run(
        monkeypatch,
        [
            "doctor-scan",
            str(tmp_path),
            "--mods",
            str(tmp_path),
            "--inventory-db",
            str(db_path),
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "mods": str(tmp_path),
        "recursive": False,
        "inventory_db": str(db_path),
    }
    assert [event["type"] for event in events] == ["result", "done"]


def test_inventory_scan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    db_path = tmp_path / "inventory.sqlite3"

    def fake_inventory_scan(args, emit):
        called["path"] = args.path
        called["db"] = args.db
        called["export"] = args.export
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "inventory-scan", fake_inventory_scan)

    code, events = _run(
        monkeypatch,
        ["inventory-scan", str(tmp_path), "--db", str(db_path), "--export"],
    )

    assert code == 0
    assert called == {"path": str(tmp_path), "db": str(db_path), "export": True}
    assert [event["type"] for event in events] == ["result", "done"]


def test_inventory_history_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    db_path = tmp_path / "inventory.sqlite3"

    def fake_inventory_history(args, emit):
        called["path"] = args.path
        called["db"] = args.db
        called["limit"] = args.limit
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "inventory-history", fake_inventory_history)

    code, events = _run(
        monkeypatch,
        ["inventory-history", str(tmp_path), "--db", str(db_path), "--limit", "5"],
    )

    assert code == 0
    assert called == {"path": str(tmp_path), "db": str(db_path), "limit": 5}
    assert [event["type"] for event in events] == ["result", "done"]


def test_inventory_file_events_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    db_path = tmp_path / "inventory.sqlite3"

    def fake_inventory_file_events(args, emit):
        called["path"] = args.path
        called["db"] = args.db
        called["include_unchanged"] = args.include_unchanged
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "inventory-file-events", fake_inventory_file_events)

    code, events = _run(
        monkeypatch,
        [
            "inventory-file-events",
            str(tmp_path),
            "--db",
            str(db_path),
            "--include-unchanged",
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "db": str(db_path),
        "include_unchanged": True,
    }
    assert [event["type"] for event in events] == ["result", "done"]


def test_patch_day_commands_are_dispatched(monkeypatch, tmp_path):
    calls = []
    state_path = tmp_path / "patch-day-state.json"

    def fake_handler(args, emit):
        calls.append((args.command, args.path, args.state))
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "patch-day-status", fake_handler)
    monkeypatch.setitem(commands.DISPATCH, "patch-day-record", fake_handler)

    status_code, status_events = _run(
        monkeypatch,
        ["patch-day-status", str(tmp_path), "--state", str(state_path)],
    )
    record_code, record_events = _run(
        monkeypatch,
        ["patch-day-record", str(tmp_path), "--state", str(state_path)],
    )

    assert status_code == record_code == 0
    assert calls == [
        ("patch-day-status", str(tmp_path), str(state_path)),
        ("patch-day-record", str(tmp_path), str(state_path)),
    ]
    assert [event["type"] for event in status_events] == ["result", "done"]
    assert [event["type"] for event in record_events] == ["result", "done"]


def test_cache_status_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_cache_status(args, emit):
        called["command"] = args.command
        called["path"] = args.path
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "cache-status", fake_cache_status)

    code, events = _run(monkeypatch, ["cache-status", str(tmp_path)])

    assert code == 0
    assert called == {"command": "cache-status", "path": str(tmp_path)}
    assert [event["type"] for event in events] == ["result", "done"]


def test_save_protector_status_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_save_protector_status(args, emit):
        called["command"] = args.command
        called["path"] = args.path
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(
        commands.DISPATCH,
        "save-protector-status",
        fake_save_protector_status,
    )

    code, events = _run(monkeypatch, ["save-protector-status", str(tmp_path)])

    assert code == 0
    assert called == {"command": "save-protector-status", "path": str(tmp_path)}
    assert [event["type"] for event in events] == ["result", "done"]


def test_tray_protector_status_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_tray_protector_status(args, emit):
        called["command"] = args.command
        called["path"] = args.path
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(
        commands.DISPATCH,
        "tray-protector-status",
        fake_tray_protector_status,
    )

    code, events = _run(monkeypatch, ["tray-protector-status", str(tmp_path)])

    assert code == 0
    assert called == {"command": "tray-protector-status", "path": str(tmp_path)}
    assert [event["type"] for event in events] == ["result", "done"]


def test_cleanup_plan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    db_path = tmp_path / "inventory.sqlite3"
    export_path = tmp_path / "cleanup.json"

    def fake_cleanup_plan(args, emit):
        called["path"] = args.path
        called["db"] = args.db
        called["export"] = args.export
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "cleanup-plan", fake_cleanup_plan)

    code, events = _run(
        monkeypatch,
        [
            "cleanup-plan",
            str(tmp_path),
            "--db",
            str(db_path),
            "--export",
            str(export_path),
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "db": str(db_path),
        "export": str(export_path),
    }
    assert [event["type"] for event in events] == ["result", "done"]


def test_cleanup_stage_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    plan_path = tmp_path / "plan.json"

    def fake_cleanup_stage(args, emit):
        called["path"] = args.path
        called["plan"] = args.plan
        called["actions"] = args.action
        called["all_actions"] = args.all_actions
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "cleanup-stage", fake_cleanup_stage)

    code, events = _run(
        monkeypatch,
        [
            "cleanup-stage",
            str(tmp_path),
            "--plan",
            str(plan_path),
            "--action",
            "duplicate:1",
            "--action",
            "archive:1",
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "plan": str(plan_path),
        "actions": ["duplicate:1", "archive:1"],
        "all_actions": False,
    }
    assert [event["type"] for event in events] == ["result", "done"]


def test_cleanup_operation_commands_are_dispatched(monkeypatch):
    calls = []

    def fake_handler(args, emit):
        calls.append((args.command, getattr(args, "manifest_path", None)))
        emit.result({"ok": True})
        emit.done()

    for command in ("cleanup-apply", "cleanup-restore", "cleanup-status"):
        monkeypatch.setitem(commands.DISPATCH, command, fake_handler)

    for command in ("cleanup-apply", "cleanup-restore", "cleanup-status"):
        code, events = _run(monkeypatch, [command, "manifest.json"])
        assert code == 0
        assert [event["type"] for event in events] == ["result", "done"]

    assert calls == [
        ("cleanup-apply", "manifest.json"),
        ("cleanup-restore", "manifest.json"),
        ("cleanup-status", "manifest.json"),
    ]


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
    monkeypatch.setitem(commands.DISPATCH, "treatment-handoff", fake_handler)

    apply_code, apply_events = _run(monkeypatch, ["treatment-apply", "manifest.json"])
    restore_code, restore_events = _run(
        monkeypatch,
        ["treatment-restore", "manifest.json", "--step", "all"],
    )
    status_code, status_events = _run(monkeypatch, ["treatment-status", "manifest.json"])
    handoff_code, handoff_events = _run(monkeypatch, ["treatment-handoff", "manifest.json"])

    assert apply_code == restore_code == status_code == handoff_code == 0
    assert called == [
        ("treatment-apply", "manifest.json", None),
        ("treatment-restore", "manifest.json", "all"),
        ("treatment-status", "manifest.json", None),
        ("treatment-handoff", "manifest.json", None),
    ]
    assert [event["type"] for event in apply_events] == ["result", "done"]
    assert [event["type"] for event in restore_events] == ["result", "done"]
    assert [event["type"] for event in status_events] == ["result", "done"]
    assert [event["type"] for event in handoff_events] == ["result", "done"]


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
