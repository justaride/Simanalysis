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
    monkeypatch.setattr(
        commands.serialization, "mod_result_to_dict", lambda a, r: {"mods": []}
    )

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
