# Local Inventory v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, read-only Sims 4 Local Inventory scanner with SQLite snapshots, a bridge command, Tauri command mapping, and a thin desktop summary page.

**Architecture:** Add a new backend service in `src/simanalysis/inventory.py` that owns SQLite schema creation, read-only traversal, package parse metadata, resource persistence, change detection, and optional JSON export. Expose it through `simanalysis-bridge inventory-scan`, wire that command through Tauri, and render a compact React view that calls the same bridge transport used by existing desktop pages.

**Tech Stack:** Python stdlib `sqlite3`, `hashlib`, `json`, existing `DBPFReader`; existing NDJSON bridge; Tauri Rust command runner; React/Vite/lucide for the thin UI.

---

## File Structure

- Create `src/simanalysis/inventory.py`: inventory dataclasses, SQLite schema, scan service, JSON export.
- Modify `src/simanalysis/bridge/__init__.py`: argparse support for `inventory-scan`.
- Modify `src/simanalysis/bridge/commands.py`: dispatch function that calls `inventory.run_inventory_scan`.
- Modify `src-tauri/src/lib.rs`: `AnalysisOptions` gets `db_path` and `export_path`; `build_args` handles `inventory-scan`; tests cover args.
- Modify `web/src/api.js`: `api.scanInventory(sims4Path, options, callbacks)`.
- Create `web/src/views/Inventory.jsx`: desktop summary page.
- Modify `web/src/App.jsx`: lazy route for `/inventory`.
- Modify `web/src/components/Sidebar.jsx`: `Inventory` sidebar item.
- Create `tests/unit/test_inventory.py`: service behavior and SQLite/export tests.
- Modify `tests/unit/test_bridge_main.py`: parser dispatch test.
- Modify `tests/unit/test_bridge_commands.py`: bridge command event sequence test.
- Add `docs/superpowers/2026-06-04-local-inventory-v1-validation.md` after implementation validation.

## Task 1: Inventory Service TDD

**Files:**
- Create: `tests/unit/test_inventory.py`
- Create: `src/simanalysis/inventory.py`

- [ ] **Step 1: Write failing tests for first scan, unchanged scan, add/remove/modify/move, corrupt package, JSON export, and ignored app folders**

Add `tests/unit/test_inventory.py` with tests that use only synthetic folders. Include helpers:

```python
from __future__ import annotations

import json
import struct
from pathlib import Path

from simanalysis.inventory import run_inventory_scan


def write_package(path: Path, payload: bytes = b"resource data") -> None:
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 0)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", 36)
    header[64:68] = struct.pack("<I", 96)

    resource_offset = 96 + 36
    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0x034AEECB)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0x12345678)
    index += struct.pack("<I", resource_offset)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(header) + bytes(index) + payload)
```

Tests to add:

```python
def test_first_inventory_scan_records_files_and_package_resources(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    write_package(mods / "Hair.package")
    (mods / "Core.ts4script").write_bytes(b"script")
    (mods / "Archive.zip").write_bytes(b"zip")
    (sims / "Options.ini").write_text("mods=1", encoding="utf-8")
    db = tmp_path / "inventory.sqlite3"

    result = run_inventory_scan(sims, db_path=db)

    assert result["database_path"] == str(db)
    assert result["summary"]["file_count"] == 4
    assert result["summary"]["package_count"] == 1
    assert result["summary"]["script_count"] == 1
    assert result["summary"]["archive_count"] == 1
    assert result["summary"]["added_count"] == 4
    assert result["summary"]["resource_count"] == 1
    assert result["summary"]["package_parse_ok_count"] == 1
    assert result["warnings"] == []
```

```python
def test_second_identical_inventory_scan_reports_unchanged(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    db = tmp_path / "inventory.sqlite3"

    run_inventory_scan(sims, db_path=db)
    result = run_inventory_scan(sims, db_path=db)

    assert result["summary"]["file_count"] == 1
    assert result["summary"]["added_count"] == 0
    assert result["summary"]["modified_count"] == 0
    assert result["summary"]["removed_count"] == 0
    assert result["summary"]["moved_count"] == 0
    assert result["summary"]["unchanged_count"] == 1
```

```python
def test_inventory_scan_detects_add_remove_modify_and_move(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    mods.mkdir(parents=True)
    (mods / "keep.package").write_bytes(b"keep")
    (mods / "remove.package").write_bytes(b"remove")
    (mods / "modify.package").write_bytes(b"before")
    (mods / "move.package").write_bytes(b"move-me")
    db = tmp_path / "inventory.sqlite3"
    run_inventory_scan(sims, db_path=db)

    (mods / "remove.package").unlink()
    (mods / "modify.package").write_bytes(b"after")
    (mods / "added.package").write_bytes(b"added")
    (mods / "Nested").mkdir()
    (mods / "move.package").rename(mods / "Nested" / "move.package")

    result = run_inventory_scan(sims, db_path=db)

    assert result["summary"]["added_count"] == 1
    assert result["summary"]["removed_count"] == 1
    assert result["summary"]["modified_count"] == 1
    assert result["summary"]["moved_count"] == 1
    assert result["summary"]["unchanged_count"] == 1
```

```python
def test_inventory_scan_records_corrupt_package_without_crashing(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    mods = sims / "Mods"
    mods.mkdir(parents=True)
    (mods / "bad.package").write_bytes(b"not dbpf")

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3")

    assert result["summary"]["package_count"] == 1
    assert result["summary"]["package_parse_error_count"] == 1
    assert result["packages"][0]["parse_status"] == "error"
    assert "DBPF" in result["packages"][0]["parse_error"]
```

```python
def test_inventory_scan_writes_explicit_json_export(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    export = tmp_path / "snapshot.json"

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3", export_path=export)
    payload = json.loads(export.read_text(encoding="utf-8"))

    assert result["export_path"] == str(export)
    assert payload["summary"]["file_count"] == 1
    assert payload["files"][0]["rel_path"] == "Mods/A.ts4script"
```

```python
def test_inventory_scan_skips_app_owned_generated_folders(tmp_path: Path) -> None:
    sims = tmp_path / "The Sims 4"
    (sims / "Mods").mkdir(parents=True)
    (sims / "Mods" / "A.ts4script").write_bytes(b"a")
    (sims / "_Simanalysis_Treatment").mkdir()
    (sims / "_Simanalysis_Treatment" / "generated.package").write_bytes(b"x")

    result = run_inventory_scan(sims, db_path=tmp_path / "inventory.sqlite3")

    assert result["summary"]["file_count"] == 1
    assert [file["rel_path"] for file in result["files"]] == ["Mods/A.ts4script"]
```

- [ ] **Step 2: Run tests to verify they fail because `simanalysis.inventory` is missing**

Run:

```bash
uv run pytest tests/unit/test_inventory.py -q
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'simanalysis.inventory'`.

- [ ] **Step 3: Implement `src/simanalysis/inventory.py` minimally**

Implement:

- `run_inventory_scan(root_path: str | Path, db_path: str | Path | None = None, export_path: str | Path | None = None) -> dict[str, object]`
- SQLite schema initialization
- full file traversal with generated-folder skip
- SHA-256 hashing
- `.package`, `.ts4script`, archive, and unknown extension counts
- DBPF package parsing for mod-like roots
- change detection based on previous active file rows
- JSON export

Use `Path.home() / ".simanalysis" / "inventory.sqlite3"` for the default database path.

- [ ] **Step 4: Run inventory tests until green**

Run:

```bash
uv run pytest tests/unit/test_inventory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit service slice**

```bash
git add src/simanalysis/inventory.py tests/unit/test_inventory.py
git commit -m "feat: add local inventory service"
```

## Task 2: Bridge Command TDD

**Files:**
- Modify: `tests/unit/test_bridge_main.py`
- Modify: `tests/unit/test_bridge_commands.py`
- Modify: `src/simanalysis/bridge/__init__.py`
- Modify: `src/simanalysis/bridge/commands.py`

- [ ] **Step 1: Add failing bridge parser and command tests**

Add to `tests/unit/test_bridge_main.py`:

```python
def test_inventory_scan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_inventory_scan(args, emit):
        called["args"] = args
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "inventory-scan", fake_inventory_scan)

    code, events = _run(
        monkeypatch,
        [
            "inventory-scan",
            str(tmp_path),
            "--db-path",
            str(tmp_path / "inventory.sqlite3"),
            "--export",
            str(tmp_path / "snapshot.json"),
        ],
    )

    assert code == 0
    assert called["args"].path == str(tmp_path)
    assert called["args"].db_path == str(tmp_path / "inventory.sqlite3")
    assert called["args"].export == str(tmp_path / "snapshot.json")
    assert [event["type"] for event in events] == ["result", "done"]
```

Add to `tests/unit/test_bridge_commands.py`:

```python
def test_inventory_scan_drives_emitter_in_order(monkeypatch, tmp_path):
    def fake_run_inventory_scan(path, db_path=None, export_path=None):
        assert path == tmp_path
        assert db_path == tmp_path / "inventory.sqlite3"
        assert export_path == tmp_path / "snapshot.json"
        return {"summary": {"file_count": 0}}

    monkeypatch.setattr(commands.inventory, "run_inventory_scan", fake_run_inventory_scan)

    buf = io.StringIO()
    args = argparse.Namespace(
        path=str(tmp_path),
        db_path=str(tmp_path / "inventory.sqlite3"),
        export=str(tmp_path / "snapshot.json"),
    )
    commands.inventory_scan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["command"] == "inventory-scan"
```

- [ ] **Step 2: Run bridge tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_bridge_main.py::test_inventory_scan_command_is_dispatched tests/unit/test_bridge_commands.py::test_inventory_scan_drives_emitter_in_order -q
```

Expected: FAIL because parser/command do not exist.

- [ ] **Step 3: Implement parser and command**

Changes:

- import `inventory` in `src/simanalysis/bridge/commands.py`
- add `inventory_scan(args, emit)`
- add `"inventory-scan": inventory_scan` to `DISPATCH`
- add parser in `src/simanalysis/bridge/__init__.py`

Command body:

```python
def inventory_scan(args: argparse.Namespace, emit: Emitter) -> None:
    root = _require_dir(args.path)
    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else None
    export_path = Path(args.export).expanduser().resolve() if args.export else None
    emit.start("inventory-scan")
    emit.result(inventory.run_inventory_scan(root, db_path=db_path, export_path=export_path))
    emit.done()
```

- [ ] **Step 4: Run focused bridge tests until green**

Run:

```bash
uv run pytest tests/unit/test_bridge_main.py::test_inventory_scan_command_is_dispatched tests/unit/test_bridge_commands.py::test_inventory_scan_drives_emitter_in_order -q
```

Expected: PASS.

- [ ] **Step 5: Commit bridge slice**

```bash
git add src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
git commit -m "feat: expose inventory bridge command"
```

## Task 3: Tauri Command Mapping TDD

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Add failing Rust tests**

Add tests near existing `build_args` tests:

```rust
#[test]
fn builds_inventory_scan_args() {
    let opts = AnalysisOptions::default();
    let args = build_args("inventory-scan", "/Sims/The Sims 4", &opts).unwrap();
    assert_eq!(args, vec!["inventory-scan", "/Sims/The Sims 4"]);
}

#[test]
fn builds_inventory_scan_args_with_db_and_export() {
    let opts = AnalysisOptions {
        db_path: Some("/tmp/inventory.sqlite3".into()),
        export_path: Some("/tmp/snapshot.json".into()),
        ..AnalysisOptions::default()
    };
    let args = build_args("inventory-scan", "/Sims/The Sims 4", &opts).unwrap();
    assert_eq!(
        args,
        vec![
            "inventory-scan",
            "/Sims/The Sims 4",
            "--db-path",
            "/tmp/inventory.sqlite3",
            "--export",
            "/tmp/snapshot.json",
        ]
    );
}
```

- [ ] **Step 2: Run Rust tests and verify failure**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml builds_inventory_scan_args
```

Expected: FAIL because `AnalysisOptions` and `build_args` do not support inventory fields.

- [ ] **Step 3: Implement Tauri mapping**

Add fields to `AnalysisOptions`:

```rust
db_path: Option<String>,
export_path: Option<String>,
```

Add `inventory-scan` branch to `build_args`:

```rust
"inventory-scan" => {
    args.push("inventory-scan".into());
    args.push(path.into());
    if let Some(db_path) = opts.db_path.as_deref() {
        args.push("--db-path".into());
        args.push(db_path.into());
    }
    if let Some(export_path) = opts.export_path.as_deref() {
        args.push("--export".into());
        args.push(export_path.into());
    }
}
```

Update existing test `AnalysisOptions` literals that need the new fields, or use struct update syntax when possible.

- [ ] **Step 4: Run focused Rust tests until green**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml builds_inventory_scan_args
```

Expected: PASS.

- [ ] **Step 5: Commit Tauri slice**

```bash
git add src-tauri/src/lib.rs
git commit -m "feat: map inventory scan through tauri"
```

## Task 4: Desktop UI TDD by Build Contract

**Files:**
- Modify: `web/src/api.js`
- Create: `web/src/views/Inventory.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Sidebar.jsx`

- [ ] **Step 1: Add `api.scanInventory` and page route**

Because this repo does not currently have a React unit test runner configured for component tests, use the Vite build as the UI contract. Implement:

```js
scanInventory: (sims4Path, options, callbacks) =>
  runAnalysis('inventory-scan', sims4Path, options || {}, callbacks),
```

Add lazy route:

```jsx
const Inventory = lazy(() => import('./views/Inventory'));
<Route path="/inventory" element={<Inventory />} />
```

Add sidebar item with a lucide icon such as `Database`:

```jsx
{ path: '/inventory', icon: Database, label: 'Inventory' },
```

- [ ] **Step 2: Create `Inventory.jsx`**

Build a dense utility page with:

- path input
- optional export path input
- Start Scan button
- running/error/completed state
- summary cards for files, packages, scripts, archives, resources
- change count strip for added/removed/modified/moved/unchanged
- parse health strip
- database/export path display

Use the existing dark dashboard visual language and lucide icons. Do not add cleanup or mutation actions.

- [ ] **Step 3: Run web build**

Run:

```bash
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 4: Commit UI slice**

```bash
git add web/src/api.js web/src/views/Inventory.jsx web/src/App.jsx web/src/components/Sidebar.jsx
git commit -m "feat: add local inventory desktop view"
```

## Task 5: End-to-End Validation and Docs

**Files:**
- Add: `docs/superpowers/2026-06-04-local-inventory-v1-validation.md`

- [ ] **Step 1: Run full focused backend stack**

Run:

```bash
uv run pytest tests/unit/test_inventory.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py tests/unit/scanners/test_mod_scanner.py -q
```

Expected: PASS.

- [ ] **Step 2: Run Rust command mapping tests**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml builds_inventory_scan_args
```

Expected: PASS.

- [ ] **Step 3: Run web build**

Run:

```bash
npm --prefix web run build
```

Expected: PASS.

- [ ] **Step 4: Run synthetic bridge smoke**

Create a temporary Sims 4 folder outside the repo and run:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/The Sims 4/Mods"
printf 'script' > "$tmpdir/The Sims 4/Mods/Core.ts4script"
uv run simanalysis-bridge inventory-scan "$tmpdir/The Sims 4" --db-path "$tmpdir/inventory.sqlite3" --export "$tmpdir/snapshot.json"
```

Expected: exit code 0, NDJSON includes `start`, `result`, `done`, and `snapshot.json` exists.

- [ ] **Step 5: Run read-only real-folder smoke if accessible**

Run:

```bash
uv run simanalysis-bridge inventory-scan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --db-path "/tmp/simanalysis-real-inventory.sqlite3" --export "/tmp/simanalysis-real-inventory.json"
```

Expected: exit code 0 or a clear filesystem access error. If it succeeds, verify the export exists and do not mutate the Sims folder.

- [ ] **Step 6: Write validation note**

Create `docs/superpowers/2026-06-04-local-inventory-v1-validation.md` with:

- branch name
- commit range
- commands run
- pass/fail outcomes
- synthetic smoke result
- real-folder smoke result or access blocker
- explicit read-only statement

- [ ] **Step 7: Commit validation**

```bash
git add docs/superpowers/2026-06-04-local-inventory-v1-validation.md
git commit -m "docs: validate local inventory v1"
```

## Self-Review Checklist

- Every spec requirement has at least one task.
- The service writes only DB/export files, not Sims folder contents.
- `scan-mods` remains unchanged.
- Corrupt packages are data, not fatal errors.
- Bridge events follow existing start/result/done conventions.
- UI offers only scan and display actions.
- Focused backend, Rust, and web validation commands are listed.
