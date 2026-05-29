import io
import json

import pytest

from simanalysis.bridge.protocol import Emitter


def _buf():
    b = io.StringIO()
    return b, Emitter(b)


def test_emit_writes_one_json_line_per_event():
    buf, emit = _buf()
    emit.start("scan-mods", total=0)
    emit.result({"summary": {}})
    emit.done()
    lines = buf.getvalue().splitlines()
    assert len(lines) == 3
    parsed = [json.loads(line) for line in lines]
    assert parsed[0] == {"v": 1, "type": "start", "task": "scan-mods", "total": 0}
    assert parsed[1]["type"] == "result" and parsed[1]["data"] == {"summary": {}}
    assert parsed[2]["type"] == "done"


def test_progress_throttled_but_first_and_last_always_emit():
    buf, emit = _buf()
    emit.progress(1, 100, file="a")
    emit.progress(2, 100, file="b")
    emit.progress(100, 100, file="z")
    currents = [json.loads(line)["current"] for line in buf.getvalue().splitlines()]
    assert currents == [1, 100]


def test_progress_force_overrides_throttle():
    buf, emit = _buf()
    emit.progress(1, 100, file="a")
    emit.progress(2, 100, file="b", force=True)
    assert len(buf.getvalue().splitlines()) == 2


def test_broken_pipe_exits_quietly():
    class Broken(io.StringIO):
        def write(self, *_):
            raise BrokenPipeError()

    emit = Emitter(Broken())
    with pytest.raises(SystemExit) as exc:
        emit.start("scan-mods")
    assert exc.value.code == 0
