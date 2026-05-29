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
