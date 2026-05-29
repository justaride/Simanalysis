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
