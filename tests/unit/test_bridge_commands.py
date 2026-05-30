import argparse
import io
import json

import pytest

from simanalysis.bridge import commands
from simanalysis.bridge.protocol import Emitter


def test_scan_mods_drives_emitter_in_order(monkeypatch, tmp_path):
    class FakeModAnalyzer:
        def __init__(self, calculate_hashes=True):
            self.calculate_hashes = calculate_hashes

        def analyze_directory(self, path, recursive=True, progress_callback=None):
            progress_callback(1, 1, "a.package")
            return object()

        def get_summary(self, r):
            return {}

        def get_recommendations(self, r):
            return []

    monkeypatch.setattr(commands, "ModAnalyzer", FakeModAnalyzer)
    monkeypatch.setattr(commands.serialization, "mod_result_to_dict", lambda a, r: {"mods": []})

    buf = io.StringIO()
    args = argparse.Namespace(path=str(tmp_path), quick=True, recursive=True)
    commands.scan_mods(args, Emitter(buf))

    kinds = [json.loads(line)["type"] for line in buf.getvalue().splitlines()]
    assert kinds == ["start", "progress", "result", "done"]


def test_scan_mods_rejects_missing_dir(tmp_path):
    missing = tmp_path / "nope"
    args = argparse.Namespace(path=str(missing), quick=False, recursive=True)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.scan_mods(args, Emitter(io.StringIO()))


def test_scan_tray_drives_emitter_in_order(monkeypatch, tmp_path):
    class FakeTrayAnalyzer:
        def analyze_directory(self, path, progress_callback=None):
            progress_callback(1, 1, "household.trayitem")
            return object()

        def get_summary(self, r):
            return {}

    monkeypatch.setattr(commands, "TrayAnalyzer", FakeTrayAnalyzer)
    monkeypatch.setattr(commands.serialization, "tray_result_to_dict", lambda a, r: {"items": []})

    buf = io.StringIO()
    args = argparse.Namespace(path=str(tmp_path))
    commands.scan_tray(args, Emitter(buf))

    kinds = [json.loads(line)["type"] for line in buf.getvalue().splitlines()]
    assert kinds == ["start", "progress", "result", "done"]


def test_analyze_save_uses_stage_callback_and_emits_in_order(monkeypatch, tmp_path):
    save_file = tmp_path / "Slot.save"
    save_file.write_bytes(b"x")
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    class FakeSaveAnalyzer:
        def analyze_save(self, save_path, mods_path, progress_callback=None):
            progress_callback("reading", 1, 3)  # (stage, current, total)
            return object()

        def get_summary(self, r):
            return {}

    monkeypatch.setattr(commands, "SaveAnalyzer", FakeSaveAnalyzer)
    monkeypatch.setattr(
        commands.serialization, "save_result_to_dict", lambda a, r: {"save_info": {}}
    )

    buf = io.StringIO()
    args = argparse.Namespace(save_path=str(save_file), mods_path=str(mods_dir))
    commands.analyze_save(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [e["type"] for e in events] == ["start", "progress", "result", "done"]
    progress = next(e for e in events if e["type"] == "progress")
    assert progress["stage"] == "reading"
    assert progress["current"] == 1
    assert progress["total"] == 3


def test_analyze_save_rejects_missing_save_file(tmp_path):
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    args = argparse.Namespace(save_path=str(tmp_path / "missing.save"), mods_path=str(mods_dir))
    with pytest.raises(ValueError, match="Save file not found"):
        commands.analyze_save(args, Emitter(io.StringIO()))


def test_thumbnail_found(monkeypatch, tmp_path):
    f = tmp_path / "m.package"
    f.write_bytes(b"x")

    class FakeSvc:
        def get_thumbnail(self, p):
            return b"PNGDATA"

    monkeypatch.setattr(commands, "ThumbnailService", FakeSvc)
    buf = io.StringIO()
    commands.thumbnail(argparse.Namespace(path=str(f)), Emitter(buf))
    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    res = next(e for e in events if e["type"] == "result")
    assert res["data"]["found"] is True
    assert res["data"]["b64"]  # base64 string present


def test_thumbnail_missing(monkeypatch, tmp_path):
    f = tmp_path / "m.package"
    f.write_bytes(b"x")

    class FakeSvc:
        def get_thumbnail(self, p):
            return None

    monkeypatch.setattr(commands, "ThumbnailService", FakeSvc)
    buf = io.StringIO()
    commands.thumbnail(argparse.Namespace(path=str(f)), Emitter(buf))
    res = next(
        json.loads(line)
        for line in buf.getvalue().splitlines()
        if json.loads(line)["type"] == "result"
    )
    assert res["data"]["found"] is False


def test_doctor_scan_emits_combined_result(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "Mods").mkdir()
    crash_log = sims4 / "lastException.txt"
    ui_log = sims4 / "lastUIException.txt"
    crash_log.write_text("crash", encoding="utf-8")
    ui_log.write_text("ui", encoding="utf-8")

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir, extra_roots=()):
            assert mods_dir == sims4 / "Mods"
            return {"mod.py": "Active.ts4script"}

        def analyze(self, reports, index):
            assert reports == [crash_report]
            assert index == {"mod.py": "Active.ts4script"}
            return type(
                "CrashResult",
                (),
                {
                    "summary": {
                        "reports": 1,
                        "active_culprits": 1,
                        "disabled_culprits": 0,
                        "not_installed_culprits": 0,
                        "base_game_only": 0,
                    },
                    "parse_errors": [],
                },
            )()

    class FakeUICrashAnalyzer:
        index_errors = ["bad package"]

        def build_resource_index(self, mods_dir, extra_roots=(), target_keys=None):
            assert mods_dir == sims4 / "Mods"
            assert target_keys == {123}
            return {123: ["hit"]}

        def analyze(self, reports, index):
            assert reports == [ui_report]
            assert index == {123: ["hit"]}
            return type(
                "UIResult",
                (),
                {
                    "summary": {
                        "unique_findings": 1,
                        "occurrences": 3,
                        "active_findings": 0,
                        "disabled_findings": 1,
                        "not_found_findings": 0,
                        "no_key_findings": 0,
                    },
                    "parse_errors": [],
                    "index_errors": ["bad package"],
                },
            )()

    crash_report = type("CrashReport", (), {"signature": "crash-sig"})()
    ui_report = type("UIReport", (), {"keys": [123]})()
    monkeypatch.setattr(commands, "CrashAnalyzer", FakeCrashAnalyzer)
    monkeypatch.setattr(commands, "UICrashAnalyzer", FakeUICrashAnalyzer)
    monkeypatch.setattr(commands, "parse_exception_file", lambda path: [crash_report])
    monkeypatch.setattr(commands, "parse_ui_exception_file", lambda path: [ui_report])
    monkeypatch.setattr(commands, "discover_disabled_roots", lambda base: [])
    monkeypatch.setattr(commands, "_is_disabled_name", lambda name: False)
    monkeypatch.setattr(
        commands.serialization,
        "crash_result_to_dict",
        lambda result: {"summary": result.summary, "parse_errors": result.parse_errors},
    )
    monkeypatch.setattr(
        commands.serialization,
        "ui_result_to_dict",
        lambda result: {
            "summary": result.summary,
            "parse_errors": result.parse_errors,
            "index_errors": result.index_errors,
        },
    )

    buf = io.StringIO()
    commands.doctor_scan(
        argparse.Namespace(path=str(sims4), mods=None, recursive=False),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "start",
        "progress",
        "progress",
        "result",
        "done",
    ]
    data = next(event["data"] for event in events if event["type"] == "result")
    assert data["summary"] == {
        "script_reports": 1,
        "script_active": 1,
        "script_disabled": 0,
        "script_not_installed": 0,
        "script_base_game_only": 0,
        "ui_findings": 1,
        "ui_occurrences": 3,
        "ui_active": 0,
        "ui_disabled": 1,
        "ui_not_found": 0,
        "ui_no_key": 0,
        "parse_errors": 0,
        "index_errors": 1,
    }
    assert data["script_crashes"]["summary"]["reports"] == 1
    assert data["ui_crashes"]["summary"]["unique_findings"] == 1


def test_doctor_scan_rejects_missing_sims_dir(tmp_path):
    args = argparse.Namespace(path=str(tmp_path / "missing"), mods=None, recursive=False)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.doctor_scan(args, Emitter(io.StringIO()))
