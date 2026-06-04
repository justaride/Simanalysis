# Local Inventory v1 Validation

**Date:** 2026-06-04
**Branch:** `codex/local-inventory-v1`
**Base:** `github/main` at `3a38398`

## Commit Range

```text
fix: harden inventory scan safety
docs: validate local inventory v1
fix: stabilize inventory summary state
feat: add local inventory desktop view
feat: map inventory scan through tauri
feat: expose inventory bridge command
feat: add local inventory service
docs: plan local inventory v1
docs: design local inventory v1
```

## Automated Checks

```bash
uv run pytest tests/unit/test_inventory.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py tests/unit/scanners/test_mod_scanner.py -q
```

Result: PASS, `65 passed in 1.18s`.

```bash
cargo test --manifest-path src-tauri/Cargo.toml builds_inventory_scan_args
```

Result: PASS, `2 passed`.

Note: Tauri local unit tests required the existing ignored sidecar shim convention:

```bash
src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin
```

The shim is under an ignored path and was not committed.

```bash
uv run python -m ruff check src/simanalysis/inventory.py src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_inventory.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
```

Result: PASS, `All checks passed!`.

```bash
npm --prefix web run lint
```

Result: PASS.

```bash
npm --prefix web run build
```

Result: PASS. Vite built the new `Inventory` route chunk successfully.

## Synthetic Bridge Smoke

Created a temporary Sims 4 folder outside the repo:

```text
/var/folders/xd/46bhtcsj3zs5c5rg5_70_gn00000gn/T/tmp.2FZXSK5JRq/The Sims 4
```

Fixture:

```text
Mods/Core.ts4script
```

Command:

```bash
uv run simanalysis-bridge inventory-scan "/var/folders/xd/46bhtcsj3zs5c5rg5_70_gn00000gn/T/tmp.2FZXSK5JRq/The Sims 4" --db-path "/var/folders/xd/46bhtcsj3zs5c5rg5_70_gn00000gn/T/tmp.2FZXSK5JRq/inventory.sqlite3" --export "/var/folders/xd/46bhtcsj3zs5c5rg5_70_gn00000gn/T/tmp.2FZXSK5JRq/snapshot.json"
```

Result: PASS.

Observed NDJSON sequence:

```text
start -> result -> done
```

Observed summary:

```json
{
  "file_count": 1,
  "package_count": 0,
  "script_count": 1,
  "archive_count": 0,
  "added_count": 1,
  "resource_count": 0
}
```

The explicit JSON export existed and contained `files[0].rel_path = "Mods/Core.ts4script"`.

## Review Fix Validation

During local review, two persistence/safety risks were tightened:

- unchanged files are counted in the scan summary without writing one `file_events` row per unchanged file
- symlinked files are skipped with a warning, preventing the inventory scanner from following links outside the selected Sims 4 root

These behaviors are covered by `tests/unit/test_inventory.py`.

## Real Folder Smoke

Command:

```bash
uv run simanalysis-bridge inventory-scan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --db-path "/tmp/simanalysis-real-inventory.sqlite3" --export "/tmp/simanalysis-real-inventory.json" > "/tmp/simanalysis-real-inventory.ndjson"
```

Result: BOUNDED STOP, not a pass.

Reason: The scan was still running after roughly four minutes at high CPU. It had emitted only the `start` event. I stopped only the validation `uv` process and its child `simanalysis-bridge` process with SIGTERM.

Observed partial files:

```text
/tmp/simanalysis-real-inventory.ndjson: 57 B
/tmp/simanalysis-real-inventory.sqlite3: 160 MB
```

SQLite counts after termination:

```text
files: 0
packages: 0
resources: 0
```

Interpretation: the transaction had not committed before termination. No result JSON was produced. This confirms the scan was read-only against the Sims folder, but also shows that full real-folder first-scan performance needs follow-up work before this should be considered production-ready for very large local folders.

## Browser/UI Check

Started Vite on `http://127.0.0.1:5186/` and opened:

```text
http://127.0.0.1:5186/inventory
```

Result: PASS with caveat.

Observed in the accessibility snapshot:

- sidebar item `Inventory`
- heading `Inventory`
- `Sims 4 Folder` input
- `Snapshot Export` input
- `Scan` button
- disabled `Cancel` button in idle state
- summary sections for files, size, packages, scripts, archives, resources
- change counts
- package parse health
- snapshot paths

Screenshot saved locally:

```text
/tmp/simanalysis-inventory-ui.png
```

Caveat: the plain Vite browser logs an existing non-Tauri context error:

```text
Failed to check for updates: TypeError: Cannot read properties of undefined (reading 'invoke')
```

This appears when running the Tauri-backed app in a normal browser. The Inventory route itself rendered and loaded all assets.

## Read-Only Statement

The completed synthetic validation wrote only to temporary DB/export paths outside the Sims folder. The real-folder smoke was invoked with DB/export paths under `/tmp` and was stopped before a committed result. No cleanup, quarantine, delete, move, cache, save, tray, or package mutation action was implemented in this slice.

## Follow-Up

Before Local Inventory v1 should be treated as production-ready for very large real Sims folders, add an incremental or bounded first-scan mode. The current deterministic first scan computes SHA-256 and attempts package resource indexing up front, which is correct for the data model but too heavy for the observed real folder smoke.
