# Simanalysis Tauri + stdio Desktop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package Simanalysis as a Tauri v2 desktop app whose React UI invokes a PyInstaller-compiled sidecar over stdio and streams real-time NDJSON progress for mod/tray/save analysis.

**Architecture:** The webview calls two typed Tauri commands (`start_analysis`/`cancel_analysis`); the Rust core spawns the `simanalysis-bridge` sidecar (process-per-task), frames its stdout into NDJSON lines, and forwards them over a `Channel`. The sidecar reuses the existing `ModAnalyzer`/`TrayAnalyzer`/`SaveAnalyzer` and emits the same result payloads as today's WebSocket layer. No network port.

**Tech Stack:** Python 3.9+ (argparse bridge, PyInstaller onefile), Rust + Tauri v2 (`tauri-plugin-shell`, `tauri-plugin-dialog`), React 18 + Vite, `@tauri-apps/api`.

**Design of record:** `docs/superpowers/specs/2026-05-29-tauri-stdio-desktop-design.md` (read §3 protocol, §5 lib.rs, §12 version-verify notes).

**Scope:** MVP = working scan/tray/save analysis with live progress + native folder picker. **Out of scope (follow-up plan):** thumbnails, config persistence, delete-to-trash, update banner, code-signing/notarization — see end of doc.

---

## File Structure

**Python (sidecar + shared core)**
- Create `src/simanalysis/serialization.py` — result→dict transforms shared by the WS layer and the bridge (single source of truth).
- Create `src/simanalysis/bridge/__init__.py` — `simanalysis-bridge` entry: argparse + `main()` loop + error→exit-code mapping.
- Create `src/simanalysis/bridge/protocol.py` — `Emitter` (NDJSON, throttle) + `setup()` (stdout hygiene).
- Create `src/simanalysis/bridge/commands.py` — dispatch `scan-mods`/`scan-tray`/`analyze-save` onto the analyzers.
- Create `run_bridge.py` — PyInstaller entry point.
- Modify `pyproject.toml` — add the `simanalysis-bridge` console script.
- Modify `src/simanalysis/web/api.py` — WS handlers call `serialization.*` (kill duplication).
- Create `tests/unit/test_serialization.py`, `tests/unit/test_bridge_protocol.py`, `tests/unit/test_bridge_commands.py`, `tests/unit/test_bridge_main.py`.

**Build**
- Create `simanalysis-bridge.spec` — PyInstaller onefile (slim).
- Create `scripts/build-sidecar.sh` — build + rename to `simanalysis-bridge-<target-triple>`.

**Tauri shell**
- Create `package.json` (repo root) — `@tauri-apps/cli` + `tauri` script.
- Create `src-tauri/Cargo.toml`, `src-tauri/build.rs`, `src-tauri/src/main.rs`.
- Create `src-tauri/src/lib.rs` — commands + sidecar spawn + NDJSON framer (+ unit test).
- Create `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`.

**Frontend**
- Modify `web/package.json` — add `@tauri-apps/api`, `@tauri-apps/plugin-dialog`.
- Modify `web/vite.config.js` — `base:'./'`, `strictPort`, `clearScreen:false`.
- Modify `web/src/api.js` — `invoke`+`Channel` transport, same public interface.
- Modify `web/src/components/FilePicker.jsx` — native dialog, same props.

---

## Task 1: Prerequisites & working checkout

The current directory is a **bare mirror** repo (no worktree) — you cannot build or commit here. Establish a normal working checkout first.

**Files:** none (environment only).

- [ ] **Step 1: Create a working checkout from the mirror**

```bash
git clone "https://github.com/justaride/Simanalysis.git" ~/src/Simanalysis
cd ~/src/Simanalysis
git checkout -b feat/tauri-stdio-desktop
```

- [ ] **Step 2: Verify toolchains are present**

Run:
```bash
python3 --version && node --version && npm --version && rustc --version && cargo --version
python3 -m pip show pyinstaller >/dev/null 2>&1 && echo "pyinstaller ok" || pip install pyinstaller
```
Expected: Python ≥3.9, Node ≥18, a Rust toolchain, and `pyinstaller ok`.

- [ ] **Step 3: Install the package in editable mode + dev deps**

Run:
```bash
python3 -m pip install -e ".[dev]"
pytest -q
```
Expected: existing suite passes (~219 tests). This is your green baseline.

> All subsequent tasks run inside this checkout. Commit messages end with the Co-Authored-By trailer shown in Task 2.

---

## Task 2: `serialization.py` — shared result transforms

**Files:**
- Create: `src/simanalysis/serialization.py`
- Test: `tests/unit/test_serialization.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_serialization.py
from types import SimpleNamespace

from simanalysis import serialization


def _v(value):
    return SimpleNamespace(value=value)


def test_mod_result_to_dict_shape():
    mod = SimpleNamespace(
        name="A.package", path="/x/A.package", type=_v("package"),
        size=123, author=None, version=None,
    )
    conflict = SimpleNamespace(
        id="c1", severity=_v("high"), type=_v("tuning"),
        description="d", affected_mods=["A.package"], resolution="r",
    )
    perf = SimpleNamespace(
        total_size_mb=1.0, total_resources=2, total_tunings=3, total_scripts=4,
        estimated_load_time_seconds=5.0, estimated_memory_mb=6.0, complexity_score=7,
    )
    result = SimpleNamespace(mods=[mod], conflicts=[conflict], performance=perf)
    analyzer = SimpleNamespace(
        get_summary=lambda r: {"ok": True},
        get_recommendations=lambda r: ["rec"],
    )

    out = serialization.mod_result_to_dict(analyzer, result)

    assert out["summary"] == {"ok": True}
    assert out["recommendations"] == ["rec"]
    assert out["mods"][0] == {
        "name": "A.package", "path": "/x/A.package", "type": "package",
        "size": 123, "author": "Unknown", "version": "Unknown", "conflicts": 1,
    }
    assert out["conflicts"][0]["severity"] == "high"
    assert out["performance"]["complexity_score"] == 7
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_serialization.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simanalysis.serialization'`.

- [ ] **Step 3: Write the implementation**

```python
# src/simanalysis/serialization.py
"""Result -> JSON-serialisable dict transforms.

Single source of truth shared by the FastAPI/WebSocket layer (simanalysis.web.api)
and the desktop stdio bridge (simanalysis.bridge), so the two transports never drift.
"""
from __future__ import annotations

from typing import Any


def mod_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "mods": [
            {
                "name": m.name,
                "path": str(m.path),
                "type": m.type.value,
                "size": m.size,
                "author": m.author or "Unknown",
                "version": m.version or "Unknown",
                "conflicts": len([c for c in result.conflicts if m.name in c.affected_mods]),
            }
            for m in result.mods
        ],
        "conflicts": [
            {
                "id": c.id,
                "severity": c.severity.value,
                "type": c.type.value,
                "description": c.description,
                "affected_mods": c.affected_mods,
                "resolution": c.resolution,
            }
            for c in result.conflicts
        ],
        "performance": {
            "total_size_mb": result.performance.total_size_mb,
            "total_resources": result.performance.total_resources,
            "total_tunings": result.performance.total_tunings,
            "total_scripts": result.performance.total_scripts,
            "estimated_load_time_seconds": result.performance.estimated_load_time_seconds,
            "estimated_memory_mb": result.performance.estimated_memory_mb,
            "complexity_score": result.performance.complexity_score,
        },
        "recommendations": analyzer.get_recommendations(result),
    }


def tray_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "items": [item.to_dict() for item in result.items],
    }


def save_result_to_dict(analyzer: Any, result: Any) -> dict[str, Any]:
    return {
        "summary": analyzer.get_summary(result),
        "save_info": result.save_data.to_dict(),
        "used_mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size": mod.size,
                "resource_count": mod.resource_count,
                "matching_resources": len(mod.matching_resources),
            }
            for mod in result.used_mods
        ],
        "unused_mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size": mod.size,
                "resource_count": mod.resource_count,
            }
            for mod in result.unused_mods[:100]
        ],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_serialization.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/simanalysis/serialization.py tests/unit/test_serialization.py
git commit -m "feat: extract shared result serializers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `protocol.py` — NDJSON emitter + stdout hygiene

**Files:**
- Create: `src/simanalysis/bridge/__init__.py` (empty placeholder this task), `src/simanalysis/bridge/protocol.py`
- Test: `tests/unit/test_bridge_protocol.py`

- [ ] **Step 1: Create the package marker**

```bash
mkdir -p src/simanalysis/bridge
: > src/simanalysis/bridge/__init__.py   # filled in Task 5
```

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_bridge_protocol.py
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
    emit.progress(1, 100, file="a")    # first -> always
    emit.progress(2, 100, file="b")    # within 50ms, not first/last -> suppressed
    emit.progress(100, 100, file="z")  # last -> always
    currents = [json.loads(line)["current"] for line in buf.getvalue().splitlines()]
    assert currents == [1, 100]


def test_progress_force_overrides_throttle():
    buf, emit = _buf()
    emit.progress(1, 100, file="a")
    emit.progress(2, 100, file="b", force=True)
    assert len(buf.getvalue().splitlines()) == 2


def test_broken_pipe_exits_quietly():
    class Broken(io.StringIO):
        def write(self, *_):  # noqa: D401
            raise BrokenPipeError()

    emit = Emitter(Broken())
    with pytest.raises(SystemExit) as exc:
        emit.start("scan-mods")
    assert exc.value.code == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/unit/test_bridge_protocol.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simanalysis.bridge.protocol'`.

- [ ] **Step 4: Write the implementation**

```python
# src/simanalysis/bridge/protocol.py
"""NDJSON stdio protocol for the Simanalysis desktop bridge.

stdout MUST stay pure NDJSON or the Rust line-parser chokes, so setup() redirects
sys.stdout -> stderr and emits only through a private handle to the real stdout.
"""
from __future__ import annotations

import io
import json
import sys
import time
from typing import Any, Optional

PROTOCOL_VERSION = 1


class Emitter:
    def __init__(self, stream: "io.TextIOBase") -> None:
        self._out = stream
        self._last_progress = 0.0

    def _write(self, obj: dict[str, Any]) -> None:
        obj.setdefault("v", PROTOCOL_VERSION)
        try:
            self._out.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
            self._out.write("\n")
            self._out.flush()
        except BrokenPipeError:
            # Parent (Tauri) closed the read end, e.g. on cancel. Exit quietly.
            raise SystemExit(0)

    def start(self, task: str, total: int = 0) -> None:
        self._write({"type": "start", "task": task, "total": total})

    def progress(
        self,
        current: int,
        total: int,
        *,
        file: Optional[str] = None,
        stage: Optional[str] = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        # Throttle to ~20/s; always emit first and last (mirrors web/api.py).
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
    try:
        real_stdout.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    sys.stdout = sys.stderr
    return Emitter(real_stdout)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_bridge_protocol.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add src/simanalysis/bridge/__init__.py src/simanalysis/bridge/protocol.py tests/unit/test_bridge_protocol.py
git commit -m "feat: add NDJSON emitter + stdout hygiene for desktop bridge

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `commands.py` — dispatch onto analyzers

**Files:**
- Create: `src/simanalysis/bridge/commands.py`
- Test: `tests/unit/test_bridge_commands.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_bridge_commands.py
import argparse
import io
import json

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
    import pytest

    missing = tmp_path / "nope"
    args = argparse.Namespace(path=str(missing), quick=False, recursive=True)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.scan_mods(args, Emitter(io.StringIO()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bridge_commands.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'simanalysis.bridge.commands'`.

- [ ] **Step 3: Write the implementation**

```python
# src/simanalysis/bridge/commands.py
"""Dispatch desktop-bridge commands onto the existing analysis core."""
from __future__ import annotations

import argparse
from pathlib import Path

from simanalysis import serialization
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.bridge.protocol import Emitter


def _require_dir(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Invalid directory path: {path}")
    return p


def scan_mods(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-mods")
    analyzer = ModAnalyzer(calculate_hashes=not args.quick)
    result = analyzer.analyze_directory(
        path,
        recursive=args.recursive,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.mod_result_to_dict(analyzer, result))
    emit.done()


def scan_tray(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-tray")
    analyzer = TrayAnalyzer()
    result = analyzer.analyze_directory(
        path,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.tray_result_to_dict(analyzer, result))
    emit.done()


def analyze_save(args: argparse.Namespace, emit: Emitter) -> None:
    save_path = Path(args.save_path).expanduser().resolve()
    if not save_path.exists():
        raise ValueError("Save file not found")
    mods_path = _require_dir(args.mods_path)
    emit.start("analyze-save")
    analyzer = SaveAnalyzer()
    result = analyzer.analyze_save(
        save_path,
        mods_path,
        progress_callback=lambda stage, c, t: emit.progress(c, t, stage=stage),
    )
    emit.result(serialization.save_result_to_dict(analyzer, result))
    emit.done()


DISPATCH = {
    "scan-mods": scan_mods,
    "scan-tray": scan_tray,
    "analyze-save": analyze_save,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bridge_commands.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/simanalysis/bridge/commands.py tests/unit/test_bridge_commands.py
git commit -m "feat: add bridge command dispatch onto analyzers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `bridge/__init__.py` — argparse + `main()` with exit codes

**Files:**
- Modify: `src/simanalysis/bridge/__init__.py`
- Test: `tests/unit/test_bridge_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_bridge_main.py
import io
import json
import sys

import pytest

from simanalysis.bridge import commands, main


def _run(monkeypatch, argv):
    """Run main() with stdout captured to a StringIO (mirrors setup() hygiene)."""
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
        commands.serialization, "mod_result_to_dict",
        lambda a, r: {"summary": a.get_summary(r), "mods": []},
    )

    code, events = _run(monkeypatch, ["scan-mods", str(tmp_path)])
    kinds = [e["type"] for e in events]
    assert code == 0
    assert kinds[0] == "start"
    assert "progress" in kinds
    assert kinds[-2:] == ["result", "done"]
    # every line is valid JSON with a protocol version
    assert all(e["v"] == 1 for e in events)


def test_invalid_path_emits_error_exit_two(monkeypatch):
    code, events = _run(monkeypatch, ["scan-mods", "/no/such/dir/zzz"])
    assert code == 2
    assert events[-1]["type"] == "error"
    assert events[-1]["code"] == "INVALID_INPUT"


def test_unknown_command_argparse_exits(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        main(["bogus-command"])
    assert exc.value.code == 2  # argparse usage error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bridge_main.py -v`
Expected: FAIL — `ImportError: cannot import name 'main' from 'simanalysis.bridge'`.

- [ ] **Step 3: Write the implementation**

```python
# src/simanalysis/bridge/__init__.py
"""`simanalysis-bridge` — headless NDJSON stdio entry point for the Tauri desktop app."""
from __future__ import annotations

import argparse
import sys
import traceback

from simanalysis.bridge import commands
from simanalysis.bridge.protocol import setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simanalysis-bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mods = sub.add_parser("scan-mods")
    p_mods.add_argument("path")
    p_mods.add_argument("--quick", action="store_true")
    p_mods.add_argument("--no-recursive", dest="recursive", action="store_false")
    p_mods.set_defaults(recursive=True)

    p_tray = sub.add_parser("scan-tray")
    p_tray.add_argument("path")

    p_save = sub.add_parser("analyze-save")
    p_save.add_argument("save_path")
    p_save.add_argument("mods_path")

    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    emit = setup()  # MUST run before any analysis so stdout is clean NDJSON
    try:
        commands.DISPATCH[args.command](args, emit)
        return 0
    except ValueError as exc:  # expected validation errors
        emit.error(str(exc), code="INVALID_INPUT")
        return 2
    except BrokenPipeError:
        return 0
    except Exception as exc:  # unexpected: full traceback to stderr, summary to UI
        traceback.print_exc()
        emit.error(f"{type(exc).__name__}: {exc}", code="INTERNAL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bridge_main.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the whole suite (no regressions)**

Run: `pytest -q`
Expected: baseline + new tests all pass.

- [ ] **Step 6: Commit**

```bash
git add src/simanalysis/bridge/__init__.py tests/unit/test_bridge_main.py
git commit -m "feat: add bridge main entry with NDJSON exit-code mapping

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: PyInstaller entry + console script + smoke test

**Files:**
- Create: `run_bridge.py`
- Modify: `pyproject.toml` (`[project.scripts]`)

- [ ] **Step 1: Create the PyInstaller entry**

```python
# run_bridge.py
#!/usr/bin/env python3
"""PyInstaller entry point for the Simanalysis stdio bridge sidecar."""
import multiprocessing
import sys

if sys.platform.startswith("win"):
    multiprocessing.freeze_support()

from simanalysis.bridge import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Add the console script entry**

In `pyproject.toml`, under `[project.scripts]`, add the second line:

```toml
[project.scripts]
simanalysis = "simanalysis.cli:main"
simanalysis-bridge = "simanalysis.bridge:main"
```

- [ ] **Step 3: Reinstall and smoke-test the NDJSON stream against an empty dir**

Run:
```bash
python3 -m pip install -e . >/dev/null
mkdir -p /tmp/empty_mods
python3 run_bridge.py scan-mods /tmp/empty_mods
```
Expected: only JSON lines on stdout, ending with a `result` then `done`, e.g.:
```
{"v":1,"type":"start","task":"scan-mods","total":0}
{"v":1,"type":"result","data":{...}}
{"v":1,"type":"done"}
```
(An empty dir yields zero mods; the analyzer still returns a result.)

- [ ] **Step 4: Verify stdout is pure JSON (no stray text)**

Run:
```bash
python3 run_bridge.py scan-mods /tmp/empty_mods | python3 -c "import sys,json; [json.loads(l) for l in sys.stdin]; print('all lines parse as JSON')"
```
Expected: `all lines parse as JSON` (non-zero exit if any line is not JSON).

- [ ] **Step 5: Commit**

```bash
git add run_bridge.py pyproject.toml
git commit -m "feat: add PyInstaller entry + simanalysis-bridge console script

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: PyInstaller sidecar spec + build script

**Files:**
- Create: `simanalysis-bridge.spec`
- Create: `scripts/build-sidecar.sh`

- [ ] **Step 1: Create the PyInstaller spec (onefile, slim)**

```python
# simanalysis-bridge.spec
# -*- mode: python ; coding: utf-8 -*-
# Headless stdio bridge sidecar: a single `simanalysis-bridge` binary,
# no web server and no web/dist.
block_cipher = None

a = Analysis(
    ['run_bridge.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'simanalysis.analyzers.mod_analyzer',
        'simanalysis.analyzers.tray_analyzer',
        'simanalysis.analyzers.save_analyzer',
    ],
    hookspath=[],
    runtime_hooks=[],
    # Trim the web/TUI stacks the bridge never imports.
    excludes=['fastapi', 'uvicorn', 'starlette', 'textual', 'aiohttp', 'jinja2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='simanalysis-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,        # UPX off: avoids AV false-positives.
    runtime_tmpdir=None,
    console=True,     # needs real stdio pipes; Tauri spawns it with no window.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)
```

- [ ] **Step 2: Create the build script**

```bash
# scripts/build-sidecar.sh
#!/usr/bin/env bash
# Build the stdio bridge as a single binary and place it where Tauri expects it.
set -euo pipefail

TRIPLE="$(rustc -Vv | sed -n 's/^host: //p')"
pyinstaller --clean --noconfirm simanalysis-bridge.spec

mkdir -p src-tauri/binaries
SRC="dist/simanalysis-bridge"
DEST="src-tauri/binaries/simanalysis-bridge-${TRIPLE}"
if [ -f "${SRC}.exe" ]; then
  SRC="${SRC}.exe"
  DEST="${DEST}.exe"
fi

cp "${SRC}" "${DEST}"
chmod +x "${DEST}" 2>/dev/null || true
echo "Sidecar ready: ${DEST}"
```

- [ ] **Step 3: Build the sidecar and verify it streams NDJSON**

Run:
```bash
chmod +x scripts/build-sidecar.sh
./scripts/build-sidecar.sh
TRIPLE="$(rustc -Vv | sed -n 's/^host: //p')"
"src-tauri/binaries/simanalysis-bridge-${TRIPLE}" scan-mods /tmp/empty_mods | tail -1
```
Expected: build prints `Sidecar ready: …`; the last line is `{"v":1,"type":"done"}`.

> If the build fails on a missing import, remove the offending name from `excludes` in the spec (an analyzer imports it transitively) and rebuild. Do **not** add stray prints — they'd corrupt stdout.

- [ ] **Step 4: Ignore build artifacts**

Append to `.gitignore`:
```
/build/
/dist/
/src-tauri/binaries/
/src-tauri/target/
```

- [ ] **Step 5: Commit**

```bash
git add simanalysis-bridge.spec scripts/build-sidecar.sh .gitignore
git commit -m "build: PyInstaller onefile sidecar + build-sidecar script

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Frontend deps + Vite config + initial build

This produces `web/dist`, which Tauri's `frontendDist` needs before `cargo build` (Task 10) can compile `generate_context!`.

**Files:**
- Modify: `web/package.json`
- Modify: `web/vite.config.js`

- [ ] **Step 1: Add Tauri JS deps**

Run:
```bash
cd web
npm install @tauri-apps/api@^2 @tauri-apps/plugin-dialog@^2
cd ..
```
Expected: both appear under `dependencies` in `web/package.json`.

- [ ] **Step 2: Apply Tauri-friendly Vite settings**

Edit `web/vite.config.js` — add `base`, `clearScreen`, and `server` to the existing `defineConfig({...})` object (keep the existing `plugins`):

```js
  base: './',            // assets load from the bundled file:// root
  clearScreen: false,    // keep Rust/Vite logs visible during `tauri dev`
  server: { port: 5173, strictPort: true },
```

- [ ] **Step 3: Build the frontend**

Run:
```bash
npm --prefix web run build
ls web/dist/index.html
```
Expected: build succeeds; `web/dist/index.html` exists.

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json web/vite.config.js
git commit -m "build: add Tauri JS deps and Vite desktop config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Tauri scaffold (config + boilerplate)

**Files:**
- Create: `package.json` (repo root), `src-tauri/Cargo.toml`, `src-tauri/build.rs`, `src-tauri/src/main.rs`, `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`
- Create: a placeholder icon at `src-tauri/icons/icon.png`

- [ ] **Step 1: Root `package.json` (Tauri CLI)**

```json
{
  "name": "simanalysis-desktop",
  "private": true,
  "scripts": { "tauri": "tauri" },
  "devDependencies": { "@tauri-apps/cli": "^2" }
}
```
Run: `npm install`
Expected: `@tauri-apps/cli` installed at repo root.

- [ ] **Step 2: `src-tauri/Cargo.toml`**

```toml
[package]
name = "simanalysis-desktop"
version = "2.1.2"
edition = "2021"

[lib]
name = "simanalysis_desktop_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"
tauri-plugin-dialog = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

- [ ] **Step 3: `src-tauri/build.rs`**

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 4: `src-tauri/src/main.rs`**

```rust
// Prevents an extra console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    simanalysis_desktop_lib::run()
}
```

- [ ] **Step 5: `src-tauri/tauri.conf.json`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Simanalysis",
  "version": "2.1.2",
  "identifier": "com.justaride.simanalysis",
  "build": {
    "frontendDist": "../web/dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "npm --prefix web run dev",
    "beforeBuildCommand": "npm --prefix web run build"
  },
  "app": {
    "windows": [
      { "title": "Simanalysis", "width": 1280, "height": 800, "resizable": true, "label": "main" }
    ],
    "security": {
      "csp": "default-src 'self'; img-src 'self' asset: data:; style-src 'self' 'unsafe-inline'; connect-src 'self' ipc: http://ipc.localhost"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/simanalysis-bridge"],
    "icon": ["icons/icon.png"]
  }
}
```

- [ ] **Step 6: `src-tauri/capabilities/default.json`**

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Core capability for the main window.",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "dialog:allow-open",
    {
      "identifier": "shell:allow-execute",
      "allow": [
        { "name": "binaries/simanalysis-bridge", "sidecar": true, "args": true }
      ]
    }
  ]
}
```

- [ ] **Step 7: Provide an icon**

Run:
```bash
mkdir -p src-tauri/icons
# Use any 512x512 PNG; the Tauri CLI can also generate a full icon set:
#   npm run tauri icon path/to/logo.png
# For now, drop a placeholder so the build resolves:
cp web/public/*.png src-tauri/icons/icon.png 2>/dev/null || \
  printf '' > src-tauri/icons/icon.png   # replace before release
```
Expected: `src-tauri/icons/icon.png` exists. (Replace with a real icon before any release build.)

- [ ] **Step 8: Commit**

```bash
git add package.json package-lock.json src-tauri/Cargo.toml src-tauri/build.rs \
  src-tauri/src/main.rs src-tauri/tauri.conf.json src-tauri/capabilities/default.json \
  src-tauri/icons/icon.png
git commit -m "feat: scaffold Tauri v2 shell config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `lib.rs` — commands, sidecar spawn, NDJSON framer (with unit test)

**Files:**
- Create: `src-tauri/src/lib.rs`

The only pure-logic unit is the line framer (`drain_complete_lines`); we test it directly. The rest is integration-verified in Task 13.

- [ ] **Step 1: Write `lib.rs` with the framer factored out and a `#[cfg(test)]` test**

```rust
//! Simanalysis Tauri desktop core.
//!
//! Owns the lifecycle of the PyInstaller-compiled `simanalysis-bridge` sidecar.
//! The webview never touches the shell: it calls the typed `start_analysis` /
//! `cancel_analysis` commands and receives NDJSON events over a Tauri Channel.

use std::collections::HashMap;
use std::sync::Mutex;

use serde::Deserialize;
use serde_json::Value;
use tauri::ipc::Channel;
use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Tracks live sidecar children so an in-flight task can be cancelled.
#[derive(Default)]
struct ChildRegistry(Mutex<HashMap<String, CommandChild>>);

/// Options forwarded to the bridge. Field names arrive camelCase from JS.
#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct AnalysisOptions {
    #[serde(default)]
    quick: bool,
    #[serde(default = "default_true")]
    recursive: bool,
    /// analyze-save only: the Mods directory to correlate against.
    #[serde(default)]
    mods_path: Option<String>,
}
fn default_true() -> bool {
    true
}

/// Build the sidecar argv. Args are passed as an array (no shell), so paths with
/// spaces/unicode are safe — no command injection.
fn build_args(kind: &str, path: &str, opts: &AnalysisOptions) -> Result<Vec<String>, String> {
    let mut args: Vec<String> = Vec::new();
    match kind {
        "scan-mods" => {
            args.push("scan-mods".into());
            args.push(path.into());
            if opts.quick {
                args.push("--quick".into());
            }
            if !opts.recursive {
                args.push("--no-recursive".into());
            }
        }
        "scan-tray" => {
            args.push("scan-tray".into());
            args.push(path.into());
        }
        "analyze-save" => {
            let mods = opts
                .mods_path
                .as_deref()
                .ok_or("analyze-save requires options.modsPath")?;
            args.push("analyze-save".into());
            args.push(path.into()); // save file
            args.push(mods.into()); // mods dir
        }
        other => return Err(format!("unknown analysis kind: {other}")),
    }
    Ok(args)
}

/// Drain all complete (newline-terminated) lines from `buf`, returning each line
/// WITHOUT its trailing '\n'. Any partial trailing line stays in `buf`.
fn drain_complete_lines(buf: &mut Vec<u8>) -> Vec<Vec<u8>> {
    let mut out = Vec::new();
    while let Some(nl) = buf.iter().position(|&b| b == b'\n') {
        let line: Vec<u8> = buf.drain(..=nl).collect();
        out.push(line[..line.len() - 1].to_vec());
    }
    out
}

/// Parse one NDJSON line and forward it to the frontend. Returns true if the line
/// was a `result` event (used to detect a clean run vs. a crash).
fn forward_line(on_event: &Channel<Value>, line: &[u8]) -> bool {
    let text = match std::str::from_utf8(line) {
        Ok(t) => t.trim(),
        Err(_) => return false,
    };
    if text.is_empty() {
        return false;
    }
    match serde_json::from_str::<Value>(text) {
        Ok(value) => {
            let is_result = value.get("type").and_then(|t| t.as_str()) == Some("result");
            let _ = on_event.send(value);
            is_result
        }
        Err(e) => {
            eprintln!("dropping non-JSON stdout line: {e}: {text}");
            false
        }
    }
}

#[tauri::command]
async fn start_analysis(
    app: AppHandle,
    task_id: String,
    kind: String,
    path: String,
    options: AnalysisOptions,
    on_event: Channel<Value>,
) -> Result<(), String> {
    let args = build_args(&kind, &path, &options)?;

    // `.sidecar("simanalysis-bridge")` resolves to
    // binaries/simanalysis-bridge-<target-triple> (tauri.conf.json externalBin).
    let sidecar = app
        .shell()
        .sidecar("simanalysis-bridge")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(args);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    app.state::<ChildRegistry>()
        .0
        .lock()
        .unwrap()
        .insert(task_id.clone(), child);

    let reader_app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buf: Vec<u8> = Vec::new();
        let mut saw_result = false;

        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    buf.extend_from_slice(&bytes);
                    for line in drain_complete_lines(&mut buf) {
                        if forward_line(&on_event, &line) {
                            saw_result = true;
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    if let Ok(text) = std::str::from_utf8(&bytes) {
                        let t = text.trim_end();
                        if !t.is_empty() {
                            eprintln!("[bridge:{task_id}] {t}");
                        }
                    }
                }
                CommandEvent::Error(err) => {
                    let _ = on_event.send(serde_json::json!({
                        "v": 1, "type": "error", "code": "IO_ERROR", "message": err
                    }));
                }
                CommandEvent::Terminated(payload) => {
                    if !buf.is_empty() {
                        if forward_line(&on_event, &buf) {
                            saw_result = true;
                        }
                        buf.clear();
                    }
                    let code = payload.code.unwrap_or(-1);
                    if code != 0 && !saw_result {
                        let _ = on_event.send(serde_json::json!({
                            "v": 1, "type": "error", "code": "CRASHED",
                            "message": format!("analyzer exited with code {code}; see logs")
                        }));
                    }
                    break;
                }
                _ => {}
            }
        }

        reader_app
            .state::<ChildRegistry>()
            .0
            .lock()
            .unwrap()
            .remove(&task_id);
    });

    Ok(())
}

#[tauri::command]
fn cancel_analysis(app: AppHandle, task_id: String) -> Result<(), String> {
    if let Some(child) = app
        .state::<ChildRegistry>()
        .0
        .lock()
        .unwrap()
        .remove(&task_id)
    {
        child
            .kill()
            .map_err(|e| format!("failed to kill task {task_id}: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
fn health() -> Value {
    serde_json::json!({ "status": "ok", "version": env!("CARGO_PKG_VERSION") })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(ChildRegistry::default())
        .invoke_handler(tauri::generate_handler![
            start_analysis,
            cancel_analysis,
            health
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::drain_complete_lines;

    #[test]
    fn frames_lines_across_chunk_boundaries() {
        let mut buf = Vec::new();
        buf.extend_from_slice(b"{\"a\":1}\n{\"b\""); // 1 complete + 1 partial
        let lines = drain_complete_lines(&mut buf);
        assert_eq!(lines, vec![b"{\"a\":1}".to_vec()]);
        assert_eq!(buf, b"{\"b\"".to_vec());

        buf.extend_from_slice(b":2}\n"); // completes the partial
        let lines = drain_complete_lines(&mut buf);
        assert_eq!(lines, vec![b"{\"b\":2}".to_vec()]);
        assert!(buf.is_empty());
    }

    #[test]
    fn no_complete_line_keeps_buffer() {
        let mut buf = b"partial".to_vec();
        assert!(drain_complete_lines(&mut buf).is_empty());
        assert_eq!(buf, b"partial".to_vec());
    }
}
```

- [ ] **Step 2: Run the framer unit test**

Run: `cargo test --manifest-path src-tauri/Cargo.toml`
Expected: PASS — `frames_lines_across_chunk_boundaries` and `no_complete_line_keeps_buffer` both green. (First run downloads crates.)

- [ ] **Step 3: Compile the whole crate**

Run: `cargo build --manifest-path src-tauri/Cargo.toml`
Expected: compiles. If `generate_context!` complains about `frontendDist`, confirm `web/dist/index.html` exists (Task 8).

> **Version check (spec §12):** if `.sidecar("simanalysis-bridge")` or `CommandEvent` paths don't resolve, confirm them against your installed `tauri-plugin-shell` version and adjust imports. The framer test does not depend on these.

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/lib.rs
git commit -m "feat: Tauri core — sidecar spawn, NDJSON framer, analysis commands

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Rewrite `web/src/api.js` to the Tauri transport

**Files:**
- Modify: `web/src/api.js` (full replacement)

No JS test runner exists in this repo, so this task is verified by lint + build + the Task 13 E2E. The public interface (`scanMods/scanTray/analyzeSave/health` + `{onStart,onProgress,onComplete,onError}`) is preserved so views don't change.

- [ ] **Step 1: Replace the file contents**

```js
// web/src/api.js
// Tauri-backed transport. Drop-in replacement for the old WebSocket client:
// public functions and callback shape are unchanged, so the React views keep
// calling api.scanMods(path, { onProgress, onComplete, ... }) as before.
import { invoke, Channel } from '@tauri-apps/api/core';

function runAnalysis(kind, path, options, callbacks) {
  const taskId = crypto.randomUUID();
  const channel = new Channel();

  channel.onmessage = (msg) => {
    switch (msg.type) {
      case 'start':
        callbacks?.onStart?.();
        break;
      case 'progress':
        callbacks?.onProgress?.({
          current: msg.current,
          total: msg.total,
          file: msg.file,
          stage: msg.stage,
        });
        break;
      case 'result':
        callbacks?.onComplete?.(msg.data);
        break;
      case 'error':
        callbacks?.onError?.(msg.message ?? 'Analysis failed');
        break;
      // 'done': completion is signalled by 'result'; no extra UI action.
    }
  };

  invoke('start_analysis', { taskId, kind, path, options, onEvent: channel })
    .catch((e) => callbacks?.onError?.(String(e)));

  // Mirror the old return contract (callers can cancel/close the task).
  const cancel = () => invoke('cancel_analysis', { taskId }).catch(() => {});
  return { taskId, cancel, close: cancel };
}

export const api = {
  health: () => invoke('health'),
  scanMods: (path, callbacks) =>
    runAnalysis('scan-mods', path, { quick: false, recursive: true }, callbacks),
  scanTray: (path, callbacks) =>
    runAnalysis('scan-tray', path, {}, callbacks),
  analyzeSave: (savePath, modsPath, callbacks) =>
    runAnalysis('analyze-save', savePath, { modsPath }, callbacks),
};

export default api; // preserve the existing default export the views import
```

- [ ] **Step 2: Lint and build**

Run:
```bash
npm --prefix web run lint
npm --prefix web run build
```
Expected: lint passes (0 warnings — the script uses `--max-warnings 0`); build succeeds.

> If lint flags the unused `axios` import elsewhere, leave unrelated files alone; only `api.js` changed here.

- [ ] **Step 3: Commit**

```bash
git add web/src/api.js
git commit -m "feat: route frontend analysis through Tauri invoke + Channel

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: `FilePicker.jsx` — native folder dialog (same props)

**Files:**
- Modify: `web/src/components/FilePicker.jsx` (full replacement)

The custom modal browser depended on `GET /api/system/browse`, which is gone. Replace it with the native OS dialog while keeping the exact props (`isOpen/onClose/onSelect/initialPath/selectDirectory`) so `ModManager.jsx` and `SaveAnalyzer.jsx` are untouched.

- [ ] **Step 1: Replace the file contents**

```jsx
// web/src/components/FilePicker.jsx
// Native OS file/folder picker via Tauri. Keeps the original props so callers
// (ModManager, SaveAnalyzer) don't change; renders no custom UI of its own.
import { useEffect, useRef } from 'react';
import { open } from '@tauri-apps/plugin-dialog';

function FilePicker({ isOpen, onClose, onSelect, initialPath, selectDirectory = true }) {
  const busy = useRef(false);

  useEffect(() => {
    if (!isOpen || busy.current) return;
    busy.current = true;

    (async () => {
      try {
        const selected = await open({
          directory: selectDirectory,
          multiple: false,
          defaultPath: initialPath || undefined,
        });
        if (selected) {
          onSelect(typeof selected === 'string' ? selected : selected[0]);
        }
      } catch (err) {
        // User cancelled or dialog failed; nothing to surface.
        console.error('file dialog error', err);
      } finally {
        busy.current = false;
        onClose();
      }
    })();
    // Re-run only when the dialog is (re)opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return null;
}

export default FilePicker;
```

- [ ] **Step 2: Lint and build**

Run:
```bash
npm --prefix web run lint
npm --prefix web run build
```
Expected: both pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/components/FilePicker.jsx
git commit -m "feat: native folder picker via tauri-plugin-dialog

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: End-to-end verification (dev build)

**Files:** none (manual verification).

- [ ] **Step 1: Rebuild the sidecar (api/bridge may have changed)**

Run: `./scripts/build-sidecar.sh`
Expected: `Sidecar ready: …`.

- [ ] **Step 2: Launch the desktop app in dev mode**

Run (from repo root): `npm run tauri dev`
Expected: Vite starts on :5173, the Rust core compiles, and the Simanalysis window opens showing the React UI.

- [ ] **Step 3: Verify the streaming scan path**

In the app: open the Mod Manager, click the folder picker → the **native OS dialog** appears → choose a real Sims 4 `Mods` folder.
Expected: a live progress indicator advances (current/total/file), then results (mods/conflicts/performance) render. No terminal window pops up for the sidecar.

- [ ] **Step 4: Verify cancellation**

Start a scan on a large folder and trigger cancel (or close the view) mid-scan.
Expected: progress stops promptly; no orphaned `simanalysis-bridge` process remains (`pgrep -fl simanalysis-bridge` returns nothing).

- [ ] **Step 5: Verify tray + save flows**

Run a Tray scan (TrayOrganizer) and a Save analysis (SaveAnalyzer, picking a `.save` file + Mods dir).
Expected: both stream progress and render results.

- [ ] **Step 6: Confirm no network port is opened**

Run while a scan is in progress: `lsof -iTCP -sTCP:LISTEN -P | grep -i simanalysis || echo "no listening sockets"`
Expected: `no listening sockets` (stdio-only; the FastAPI server is not on this path).

- [ ] **Step 7: Commit a short verification note**

```bash
mkdir -p docs/superpowers
cat > docs/superpowers/2026-05-29-desktop-mvp-verification.md <<'EOF'
# Desktop MVP verification (2026-05-29)
- tauri dev launches; window renders React UI: PASS
- native folder dialog selects Mods folder: PASS
- mod scan streams progress + renders results: PASS
- cancel kills sidecar, no orphan process: PASS
- tray + save flows stream + render: PASS
- no listening TCP sockets during scan: PASS
EOF
git add docs/superpowers/2026-05-29-desktop-mvp-verification.md
git commit -m "docs: record desktop MVP verification

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Out of scope — follow-up plan

These spec §10 / §11 items are **not** required for a working scan/analyze app and should be their own plan:

- **Config persistence** (`GET/POST /api/config`) → `@tauri-apps/plugin-store` or `get_config`/`set_config` commands writing `~/.simanalysis/config.json`. ModManager currently `fetch`es `/api/config`; until ported, it should fall back to an empty last-scan-path (small edit, or accept the failed fetch — it already `try/catch`es).
- **Thumbnails** (`GET /api/mods/thumbnail`) → `get_thumbnail(path)` command + `thumb://` asset protocol or base64. Until ported, ModManager's `<img>` shows a broken image (non-blocking).
- **Delete-to-trash** (`DELETE /api/mods/file`) → `delete_mod_file(path)` command using the `trash` crate + audit log.
- **Update banner** (`GET /api/updates`) → stub `check_updates` → `{update_available:false}`, or Tauri Updater later.
- **Signing/notarization & installers** → macOS Developer ID + notarization, Windows code-signing cert, multi-arch; configure `tauri.conf.json > bundle` and CI.

> Note: ModManager and Layout currently call the not-yet-ported endpoints via `fetch` and already wrap them in `try/catch`, so the app runs without them (degraded: no persisted path, broken thumbnails, dead update banner). Port them in the follow-up plan.

---

## Self-review notes (completed)

- **Spec coverage:** §3 protocol → Tasks 3/5/10; §5 lib.rs → Task 10; §6 Python bridge → Tasks 2–6; §6 sidecar spec/build → Task 7; §7 api.js/vite → Tasks 8/11; §10 file-browse → Task 12 (native dialog); remaining §10 items → explicitly deferred. §1 serialization dedup in `web/api.py` is noted in the spec but **not yet wired** — add as an optional cleanup task (below) since it's a pure refactor with existing test coverage.
- **Optional cleanup (not blocking MVP):** after Task 5, edit `src/simanalysis/web/api.py`'s three WS handlers + `POST /api/scan` to call `serialization.mod_result_to_dict` / `tray_result_to_dict` / `save_result_to_dict`, then run `pytest -q`. Deferred to avoid touching the running server path during the desktop MVP.
- **Placeholder scan:** no TBD/TODO; every code step contains complete code; verification steps give exact commands + expected output.
- **Type/name consistency:** command names (`start_analysis`/`cancel_analysis`/`health`), kinds (`scan-mods`/`scan-tray`/`analyze-save`), and option keys (`quick`/`recursive`/`modsPath`) match across `lib.rs`, `api.js`, and the Python argparse subcommands.
