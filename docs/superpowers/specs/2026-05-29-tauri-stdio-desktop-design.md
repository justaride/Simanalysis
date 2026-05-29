# Simanalysis Desktop — Tauri v2 + stdio NDJSON sidecar

**Status:** Design approved (brainstorming), pending spec review
**Date:** 2026-05-29
**Author:** architecture session

## Decisions (locked)

| Axis | Choice | Why |
|---|---|---|
| Desktop shell | **Tauri v2** | Tiny bundle (system WebView), capability-based security, first-class sidecar + `Channel` streaming. |
| Backend IPC | **stdio NDJSON pipes** | No network port → smallest attack surface; removes today's `allow_origins=["*"]` localhost server. |
| Invocation | **Process-per-task** | Analysis is a discrete op; crash isolation; cancel = kill child. |
| Spawn/parse owner | **Rust core (approach A)** | Webview gets no shell access; line-framing + cancel registry centralized in one trusted place. |
| Distribution | **Local dev build first** | Signing/notarization deferred (see §10). |

## 1. What already exists (and what we reuse vs. replace)

The repo (`justaride/Simanalysis`, v2.1.2) is a Sims 4 DBPF/save analyzer:

- **Analysis core** — `ModAnalyzer`, `TrayAnalyzer`, `SaveAnalyzer` under `src/simanalysis/analyzers/`. These are synchronous, CPU-bound, and **already expose progress callbacks**:
  - `ModAnalyzer(calculate_hashes=not quick).analyze_directory(path, recursive=, progress_callback=cb)` where `cb(current:int, total:int, filename:str)`
  - `TrayAnalyzer().analyze_directory(path, progress_callback=cb)` — same `cb` signature
  - `SaveAnalyzer().analyze_save(save_path, mods_path, progress_callback=cb)` where `cb(stage:str, current:int, total:int)`
  - plus `analyzer.get_summary(result)` and `analyzer.get_recommendations(result)`
- **Transport today** — `src/simanalysis/web/api.py` is a FastAPI app whose WebSocket handlers (`/api/ws/scan`, `/api/ws/scan/tray`, `/api/ws/analyze/save`) run the analyzer in a thread pool and stream JSON: `{status:'scanning',current,total,file}` → `{status:'complete',result}` → `{status:'error',message}`, throttled to ~20/s.
- **Frontend** — Vite + React 18 SPA in `web/`. `web/src/api.js` is a WebSocket client exposing `scanMods/scanTray/analyzeSave(path, {onStart,onProgress,onComplete,onError})`. Views (`Dashboard.jsx`, `ModManager.jsx`, `SaveAnalyzer.jsx`, …) consume that callback API.
- **Packaging today** — `simanalysis.spec` (PyInstaller, onedir) bundles `run_standalone.py` → `run_web_gui()` (uvicorn on `127.0.0.1:8000`) + `web/dist`, then auto-opens a browser. i.e. *local web server + browser*, not a native shell.

**Reuse:** the entire analysis core and its progress callbacks; the exact `result` JSON shapes.
**Replace:** the transport. The WebSocket-over-localhost path is swapped for a Tauri shell that spawns a headless sidecar and reads NDJSON from its stdout. The FastAPI server is **not** on the desktop path (it can remain for a future "server mode").

> **Key insight:** we are changing *transport*, not analysis logic. The result payloads stay byte-for-byte identical, so React views need no data-shape changes.

## 2. Architecture

```
┌─────────────────────────── Tauri v2 app ───────────────────────────┐
│  WebView — existing React/Vite SPA (web/)                           │
│    views/* (unchanged) ──► web/src/api.js (rewritten internals)     │
│        │  invoke('start_analysis', { taskId, kind, path, options,   │
│        │                             onEvent: Channel })            │
│        │  invoke('cancel_analysis', { taskId })                     │
│        ▼                                                             │
│  Rust core — src-tauri/src/lib.rs  ◄── "the main script" (A)        │
│    • #[tauri::command] start_analysis / cancel_analysis / health    │
│    • app.shell().sidecar("simanalysis-bridge").args([...]).spawn()  │
│    • read CommandEvent::Stdout bytes → frame NDJSON → Channel.send   │
│    • ChildRegistry: Mutex<HashMap<taskId, CommandChild>> for cancel  │
│        │  argv: ["scan-mods", "<path>", "--quick"]                  │
│        ▼                                                             │
│  Sidecar — simanalysis-bridge-<target-triple> (PyInstaller onefile) │
│    NDJSON on stdout · logs/tracebacks on stderr · exit 0|nonzero    │
│        └─ reuses ModAnalyzer / TrayAnalyzer / SaveAnalyzer          │
│           + simanalysis.serialization (extracted from web/api.py)   │
└─────────────────────────────────────────────────────────────────────┘
        No TCP port. No FastAPI/uvicorn on this path.
```

The renderer never touches the shell. It calls two typed commands and receives a stream over a Tauri **`Channel`** — the idiomatic v2 streaming primitive, auto-routed per invocation (no global event-name bookkeeping, no listener leaks).

## 3. The NDJSON protocol (single source of truth)

**stdout = pure NDJSON, one compact JSON object per line. stderr = everything else. Exit 0 after `done`, non-zero after `error`/crash.**

```jsonc
{"v":1,"type":"start","task":"scan-mods","total":0}
{"v":1,"type":"progress","current":12,"total":340,"file":"foo.package"}
{"v":1,"type":"progress","stage":"hashing","current":2,"total":5}   // save flow
{"v":1,"type":"result","data":{ /* identical to today's WS 'result' payload */ }}
{"v":1,"type":"done"}
// failure:
{"v":1,"type":"error","code":"INVALID_INPUT","message":"Invalid directory path: ..."}
```

- `v` — protocol version (forward-compat).
- `type` ∈ `start | progress | result | error | done`. (No `log` type — logs go to stderr.)
- `result.data` — the existing WS payload (`summary / mods / conflicts / performance / recommendations` for mods; `summary / items` for tray; `summary / save_info / used_mods / unused_mods` for save).

**Three failure modes this design pins down explicitly** — these are where stdio JSON bridges usually break:

1. **stdout hygiene.** On startup the bridge captures the *real* stdout for NDJSON, then reassigns `sys.stdout = sys.stderr` so any stray `print()`, warning, traceback, or library chatter lands on stderr and can't corrupt the stream. JSON is flushed per line; UTF-8 forced.
2. **Line framing on the Rust side.** `CommandEvent::Stdout` delivers **byte chunks**, not guaranteed lines — so the reader buffers and splits on `\n`, flushing a trailing newline-less line on `Terminated`. Malformed lines are logged and skipped, never fatal.
3. **Cancellation = kill.** Process-per-task means cancel is `child.kill()`; Python catches `BrokenPipeError` and exits 0. No in-band cancel protocol.

## 4. Components / deliverables

```
src/simanalysis/
  serialization.py        NEW   result→dict transforms EXTRACTED from web/api.py
  bridge/__init__.py      NEW   `simanalysis-bridge` entry (argparse, NDJSON main loop)
  bridge/protocol.py      NEW   Emitter + stdout-hygiene setup + 20/s throttle
  bridge/commands.py      NEW   dispatch scan-mods/scan-tray/analyze-save → analyzers
  web/api.py              EDIT  WS handlers call serialization.py (kill duplication)

run_bridge.py             NEW   PyInstaller entry for the sidecar
simanalysis-bridge.spec   NEW   PyInstaller onefile (slim: no fastapi/uvicorn/web/dist)
scripts/build-sidecar.sh  NEW   build + rename to simanalysis-bridge-<triple>

package.json              NEW   root: @tauri-apps/cli + "tauri" script
src-tauri/
  Cargo.toml              NEW   tauri 2, tauri-plugin-shell, serde, serde_json
  build.rs                NEW   tauri_build::build()
  tauri.conf.json         NEW   externalBin, devUrl, frontendDist, before*Command
  capabilities/default.json NEW core:default + narrowly-scoped sidecar permission
  src/main.rs             NEW   thin entrypoint
  src/lib.rs              NEW   ★ main script template (A) ★

web/
  src/api.js              EDIT  internals → invoke + Channel; SAME public interface
  package.json            EDIT  add @tauri-apps/api
  vite.config.js          EDIT  base:'./', strictPort, clearScreen:false
```

**Blast radius on React is small:** `api.js` keeps its function names and `{onStart,onProgress,onComplete,onError}` callback shape, so the *streaming* views (`Dashboard`, `SaveAnalyzer`, `TrayOrganizer`, ModManager's scan path) don't change. Components that call the non-streaming HTTP endpoints (`FilePicker`, `ModManager` config/thumbnail, `DuplicateModal`, `Layout`) need small edits — see §10.

**Project layout:** `src-tauri/` sits at repo root (sibling of `web/` and `src/`). Run `npm install && npm run tauri dev` from the repo root.

## 5. `main` script template — `src-tauri/src/lib.rs` (approach A)

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

/// Build the sidecar argv for a given analysis kind. Args are passed as an
/// array (no shell), so paths with spaces/unicode are safe — no injection.
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
    // binaries/simanalysis-bridge-<target-triple> (see tauri.conf.json externalBin).
    let sidecar = app
        .shell()
        .sidecar("simanalysis-bridge")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(args);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("failed to spawn sidecar: {e}"))?;

    // Register so cancel_analysis can kill this task.
    app.state::<ChildRegistry>()
        .0
        .lock()
        .unwrap()
        .insert(task_id.clone(), child);

    // Stream output without blocking the command's return.
    let reader_app = app.clone();
    tauri::async_runtime::spawn(async move {
        let mut buf: Vec<u8> = Vec::new();
        let mut saw_result = false;

        while let Some(event) = rx.recv().await {
            match event {
                // stdout arrives as byte chunks; we frame NDJSON ourselves.
                CommandEvent::Stdout(bytes) => {
                    buf.extend_from_slice(&bytes);
                    while let Some(nl) = buf.iter().position(|&b| b == b'\n') {
                        let line: Vec<u8> = buf.drain(..=nl).collect();
                        if forward_line(&on_event, &line[..line.len() - 1]) {
                            saw_result = true;
                        }
                    }
                }
                // Bridge logs/tracebacks. Surface for debugging; never parsed as data.
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
                    // Flush a trailing line that lacked a newline.
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

        // Cleanup (child is already dead if we got here naturally).
        reader_app
            .state::<ChildRegistry>()
            .0
            .lock()
            .unwrap()
            .remove(&task_id);
    });

    Ok(())
}

/// Parse one NDJSON line and forward it to the frontend.
/// Returns true if the line was a `result` event.
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
            // Malformed line: log + skip rather than killing the stream.
            eprintln!("dropping non-JSON stdout line: {e}: {text}");
            false
        }
    }
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
        .manage(ChildRegistry::default())
        .invoke_handler(tauri::generate_handler![
            start_analysis,
            cancel_analysis,
            health
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### `src-tauri/src/main.rs`

```rust
// Prevents an extra console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    simanalysis_desktop_lib::run()
}
```

### `src-tauri/Cargo.toml`

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
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

### `src-tauri/build.rs`

```rust
fn main() {
    tauri_build::build()
}
```

### `src-tauri/tauri.conf.json`

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

### `src-tauri/capabilities/default.json`

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Core capability for the main window.",
  "windows": ["main"],
  "permissions": [
    "core:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [
        { "name": "binaries/simanalysis-bridge", "sidecar": true, "args": true }
      ]
    }
  ]
}
```

> Security note: this scope permits executing **only** our sidecar (with args) — nothing else. In approach A the *frontend* JS never calls `shell`; the scope is here as defense-in-depth and to satisfy the plugin scope check. To tighten further, replace `"args": true` with a validated arg list once the command surface is frozen.

## 6. Python sidecar templates

### `src/simanalysis/serialization.py` (extracted from `web/api.py`)

```python
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

Then `web/api.py` WS handlers replace their inline dict-building with e.g. `serialization.mod_result_to_dict(analyzer, result)`.

### `src/simanalysis/bridge/protocol.py`

```python
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

### `src/simanalysis/bridge/commands.py`

```python
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

### `src/simanalysis/bridge/__init__.py`

```python
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

### `run_bridge.py` (PyInstaller entry)

```python
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

### `simanalysis-bridge.spec` (PyInstaller, onefile)

```python
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
    # VERIFY against the analyzers' real imports before trusting these.
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

### `scripts/build-sidecar.sh`

```bash
#!/usr/bin/env bash
# Build the stdio bridge as a single binary and place it where Tauri expects it.
set -euo pipefail

TRIPLE="$(rustc -Vv | sed -n 's/^host: //p')"
pyinstaller --clean --noconfirm simanalysis-bridge.spec

mkdir -p src-tauri/binaries
SRC="dist/simanalysis-bridge"
DEST="src-tauri/binaries/simanalysis-bridge-${TRIPLE}"
[ -f "${SRC}.exe" ] && SRC="${SRC}.exe" && DEST="${DEST}.exe"

cp "${SRC}" "${DEST}"
chmod +x "${DEST}" 2>/dev/null || true
echo "Sidecar ready: ${DEST}"
```

## 7. Frontend adapter — `web/src/api.js` (rewritten internals, same public API)

```js
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

### `web/vite.config.js` (additions)

```js
// Tauri-friendly tweaks (merge into the existing config):
export default defineConfig({
  // ...existing plugins...
  base: './',            // assets load from the bundled file:// root
  clearScreen: false,    // don't hide Rust/Vite logs during `tauri dev`
  server: { port: 5173, strictPort: true },
});
```

### Root `package.json` (new)

```json
{
  "name": "simanalysis-desktop",
  "private": true,
  "scripts": { "tauri": "tauri" },
  "devDependencies": { "@tauri-apps/cli": "^2" }
}
```

`web/package.json`: add `"@tauri-apps/api": "^2"` to `dependencies`.

## 8. Data flow (process-per-task)

1. A React view calls `api.scanMods(path, cb)`.
2. Adapter mints `taskId`, wires a `Channel`, calls `invoke('start_analysis', {taskId, kind, path, options, onEvent})`.
3. Rust builds argv, `app.shell().sidecar("simanalysis-bridge").args(...).spawn()`, registers the child under `taskId`, and spawns a reader task.
4. Sidecar: `setup()` (stdout hygiene) → `start` → analyzer runs with `progress_callback` → throttled `progress` lines → `result` → `done`, then exits 0.
5. Reader frames stdout bytes into NDJSON lines → `on_event.send(value)` → the `Channel.onmessage` routes to `cb.onProgress/onComplete/onError`.
6. On `Terminated`, reader flushes any partial line, synthesizes a `CRASHED` error if exit≠0 with no prior result, and removes the child from the registry.
7. Cancel: `api…cancel()` → `invoke('cancel_analysis', {taskId})` → `child.kill()`; Python hits `BrokenPipeError` → exits 0.

## 9. Error handling & testing

**Errors**
- Invalid path / missing save → `error{code:"INVALID_INPUT"}`, exit 2.
- Python crash → traceback to stderr (captured to the `tauri dev` console / future log file), `error{code:"INTERNAL"}`, exit 1.
- Non-zero exit with no `result` seen → Rust synthesizes `error{code:"CRASHED"}`.
- Missing / mis-tripled binary → `spawn()` returns `Err` → `start_analysis` rejects → adapter calls `onError`.

**Testing**
- **pytest (bridge):** run `main(["scan-mods", tmp_mods_dir])` with stdout captured; assert (a) every stdout line is valid JSON, (b) sequence is `start → progress* → result → done`, (c) nothing but JSON on stdout, (d) exit codes for the bad-path / crash cases. Fits the existing pytest suite (219 tests).
- **Contract test:** a shared JSON-schema for the event envelope, asserted by both the pytest bridge test and a Rust unit test, so Python/Rust/TS can't drift.
- **Rust unit test:** feed the line-framer chunked byte slices that split mid-object and across `\n`; assert correct reassembly + that malformed lines are skipped.
- **Adapter:** mock `invoke`/`Channel`; assert `onProgress/onComplete/onError` routing.
- **Manual E2E (dev build):** `npm run tauri dev`, pick the Mods folder, watch live progress; cancel mid-scan and confirm the child dies.

## 10. Auxiliary (non-streaming) surface to port

The cutover is more than the three streaming commands. `web/api.py` also exposes **request/response** endpoints the React app calls directly via `fetch`; on the stdio path (no server) these go dead unless ported. They don't stream, so they become thin typed Tauri commands or native plugins — **not** part of the NDJSON bridge (which stays focused on real-time analysis, the user's emphasis).

| Endpoint (today) | Used by | Recommended desktop replacement | Phase |
|---|---|---|---|
| `GET /api/system/browse` | `FilePicker.jsx` | **Native dialog** `@tauri-apps/plugin-dialog` `open({directory:true})` — deletes the custom browser; UX upgrade. | 4 (MVP) |
| `GET/POST /api/config` | `ModManager.jsx` (last scan path) | `@tauri-apps/plugin-store`, or small `get_config`/`set_config` commands writing `~/.simanalysis/config.json` (reuse `ConfigService`). | 4 (MVP) |
| `GET /api/mods/thumbnail` | `ModManager.jsx` `<img>` | `get_thumbnail(path)` command reusing `ThumbnailService`; serve via a custom `thumb://` asset protocol (best for long lists) or base64 data URL (simpler MVP). | 4 (MVP) |
| `DELETE /api/mods/file` | `DuplicateModal.jsx` | `delete_mod_file(path)` command — move-to-trash (`trash` crate) + keep the audit log; same suffix validation as today. | 4 (MVP) |
| `GET /api/updates` | `Layout.jsx` banner | Defer (Tauri Updater later); stub `check_updates` → `{update_available:false}`. | 6 (deferred) |

These are independent of the streaming design above and can be ported view-by-view during the frontend cutover. The native file dialog in particular lets `FilePicker.jsx` shrink substantially.

## 11. Phased roadmap

1. **Backend bridge** — `serialization.py` (+ refactor `web/api.py` to use it), `bridge/` package, `run_bridge.py`; pytest for the NDJSON contract. *No Tauri yet — fully testable from the terminal:* `python run_bridge.py scan-mods <dir> | cat`.
2. **Sidecar build** — `simanalysis-bridge.spec` + `scripts/build-sidecar.sh`; verify the onefile streams NDJSON and excludes don't break analyzer imports.
3. **Tauri shell** — scaffold `src-tauri/` (or `npm create tauri-app` then graft), drop in `lib.rs`/`main.rs`/config/capabilities; `tauri dev` loading the Vite server.
4. **Frontend cutover** — swap `api.js` internals, add `@tauri-apps/api`, vite tweaks; port the auxiliary surface (§10: dialog / config / thumbnail / delete); verify each view (Dashboard/ModManager/SaveAnalyzer/TrayOrganizer) end-to-end.
5. **Polish** — cancellation UX, error toasts, stderr → log file (`~/.simanalysis/bridge.log`), app icon.
6. **Deferred (out of scope now):** code-signing + notarization (macOS Developer ID, Windows cert), auto-update, multi-arch (universal mac / x64 + arm). Windows console-window suppression is handled by the release `windows_subsystem` attr + Tauri's no-window spawn.

## 12. Verify-during-implementation (pin to the installed crate versions)

These Tauri v2 details are version-sensitive — confirm against the pinned `tauri` / `tauri-plugin-shell` before relying on them:

1. **Sidecar name resolution** — `app.shell().sidecar("simanalysis-bridge")` vs the `externalBin` entry `"binaries/simanalysis-bridge"`; confirm Tauri appends `-<target-triple>` and which string the Rust API expects.
2. **`CommandEvent::Stdout` framing** — confirm whether it delivers raw chunks or pre-split lines. The buffer handles chunks (the common case) and a trailing newline-less line; adjust only if the plugin pre-splits *and* strips newlines.
3. **Rust-side scope** — confirm whether `.sidecar().spawn()` from Rust is gated by the capability scope; the scoped permission in `capabilities/default.json` covers both answers.
4. **`Channel<Value>`** import path (`tauri::ipc::Channel`) and JS `Channel` from `@tauri-apps/api/core`.

## Appendix — Repo facts this design relies on

- Bare **mirror** clone at `…/Simanalysis.git` (`mirror=true`); the only worktree (`/private/tmp/Simanalysis-main`) is prunable/gone. This spec is written to disk here but **not committed** (committing into a mirror would diverge it). To land it: clone a normal working copy, `git checkout -b feat/tauri-desktop`, copy this file under `docs/`, and proceed there.
- Entry point today: `[project.scripts] simanalysis = "simanalysis.cli:main"` (click). New sidecar adds `simanalysis-bridge = "simanalysis.bridge:main"`.
- Frontend deps already include `framer-motion`, `recharts`, `react-router-dom`, `lucide-react`, `sonner`, `axios` (axios now unused on the desktop path).
