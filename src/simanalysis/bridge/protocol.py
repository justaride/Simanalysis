"""NDJSON stdio protocol for the Simanalysis desktop bridge.

stdout MUST stay pure NDJSON or the Rust line-parser chokes, so setup() redirects
sys.stdout -> stderr and emits only through a private handle to the real stdout.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import time
from typing import Any

PROTOCOL_VERSION = 1


class Emitter:
    def __init__(self, stream: io.TextIOBase) -> None:
        self._out = stream
        self._last_progress = 0.0

    def _write(self, obj: dict[str, Any]) -> None:
        obj.setdefault("v", PROTOCOL_VERSION)
        try:
            self._out.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
            self._out.write("\n")
            self._out.flush()
        except BrokenPipeError:
            # Parent (Tauri) closed the read end, e.g. on cancel. Raise SystemExit
            # (a BaseException) rather than returning: it unwinds cleanly through the
            # analyzer's own `except Exception` blocks, so a cancelled scan terminates
            # promptly instead of writing into a dead pipe for the rest of the run.
            raise SystemExit(0) from None

    def start(self, task: str, total: int = 0) -> None:
        # total=0 means "unknown at start"; consumers should treat the first
        # progress event as authoritative for the real total.
        self._write({"type": "start", "task": task, "total": total})

    def progress(
        self,
        current: int,
        total: int,
        *,
        file: str | None = None,
        stage: str | None = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and current not in (1, total) and (now - self._last_progress) < 0.05:
            return
        self._last_progress = now
        evt: dict[str, Any] = {"type": "progress", "current": current, "total": total}
        if file is not None:
            evt["file"] = file
        if stage is not None:
            evt["stage"] = stage
        self._write(evt)

    def result(self, data: dict[str, Any]) -> None:
        self._write({"type": "result", "data": data})

    def error(self, message: str, code: str = "ERROR") -> None:
        self._write({"type": "error", "code": code, "message": message})

    def done(self) -> None:
        self._write({"type": "done"})


def setup() -> Emitter:
    """Capture real stdout for NDJSON; point sys.stdout at stderr so stray prints
    / library chatter cannot corrupt the data stream."""
    real_stdout = sys.stdout
    with contextlib.suppress(AttributeError, ValueError):
        real_stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    sys.stdout = sys.stderr
    return Emitter(real_stdout)
