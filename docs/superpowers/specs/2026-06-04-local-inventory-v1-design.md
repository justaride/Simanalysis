# Local Inventory v1 - design

**Status:** Design approved; ready for implementation planning
**Date:** 2026-06-04
**Roadmap:** First implementation slice from the updated Simanalysis masterplan after PR #16. This builds the read-only inventory and snapshot foundation that later backup, quarantine, profile, patch-day, and conflict workflows will rely on.

## Goal

Add a persistent Local Inventory system for a Sims 4 user folder.

The user selects the Sims 4 folder, runs an inventory scan, and Simanalysis records a local SQLite-backed snapshot of what exists without changing the Sims folder. The scan should report file counts, package/script/archive counts, total size, package parse status, resource counts, and changes since the prior scan.

## Why now

The masterplan depends on trustworthy local state before any larger repair or automation feature. Existing scan commands can analyze mods in memory, but they do not persist a complete file inventory, scan history, snapshots, or change events.

Local Inventory v1 creates the durable read-only base for:

- backup and rollback planning
- duplicate and misplaced file detection
- resource conflict graphing
- profile activation previews
- patch-day status
- future cache doctor and update staging

## Product Decisions

- The feature is read-only against the Sims 4 folder.
- The feature may write to Simanalysis-owned app data under `~/.simanalysis`.
- The feature may write a JSON snapshot only when the user or caller supplies an export path.
- The default database path is `~/.simanalysis/inventory.sqlite3`.
- The scanner indexes the selected Sims 4 root, not just `Mods`.
- DBPF resource parsing is limited to `.package` files that are under mod-like folders.
- Saves and Tray files are inventoried as files only in v1.
- This does not replace `scan-mods`; it adds a new inventory command and UI.
- Unknown or corrupt packages are recorded with parse errors, not treated as fatal scan failures.
- The UI is a thin summary surface over the bridge command.

## Scan Boundary

The user supplies the Sims 4 root folder, normally:

- Windows: `%USERPROFILE%\Documents\Electronic Arts\The Sims 4`
- macOS: `~/Documents/Electronic Arts/The Sims 4`

V1 traverses all regular files under that root, excluding app-owned generated folders only when they sit inside the selected root:

- `.simanalysis`
- `.modguardian`
- `_Simanalysis_Treatment`

The scanner records files from:

- `Mods`
- `Saves`
- `Tray`
- `Screenshots`
- `Recorded Videos`
- root files such as `Options.ini`, `localthumbcache.package`, and `GameVersion.txt`

DBPF parsing runs only for `.package` files under these relative paths:

- `Mods/`
- `_Disabled/`
- `_Disabled_Mods/`
- `_Quarantine/`
- `_Simanalysis_Quarantine/`

Root-level `localthumbcache.package` is inventoried but not parsed as a mod package in v1.

## Stored Data

Local Inventory v1 stores:

- roots
- scans
- snapshots
- file facts
- package parse metadata
- package resources
- file change events

The schema is intentionally small and migratable.

Suggested tables:

- `schema_meta`
- `roots`
- `scans`
- `snapshots`
- `files`
- `packages`
- `resources`
- `file_events`

File rows must include:

- absolute path
- relative path
- filename
- extension
- size bytes
- mtime nanoseconds
- SHA-256
- first seen scan
- last seen scan
- status

Package rows must include:

- file id
- parse status
- parse error
- resource count
- compression flag

Resource rows must include:

- file id
- type id
- group id
- instance id
- normalized resource key
- compressed size
- uncompressed size
- compression type when known

## Change Detection

Each scan compares the current file facts with the previous active rows for the same root.

V1 classification:

- `added`: current relative path was not active last scan and its hash does not match a removed prior row.
- `removed`: prior active relative path is missing and has not been matched as moved.
- `modified`: same relative path exists but SHA-256 changed.
- `moved`: current relative path is new, prior path is missing, and SHA-256 matches.
- `unchanged`: same relative path exists and SHA-256 is unchanged.

The scanner may use size and mtime as fast pre-checks, but V1 should compute SHA-256 for deterministic results and tests.

## Bridge Command

Add a new bridge command:

```bash
simanalysis-bridge inventory-scan <sims4_dir> [--db-path PATH] [--export PATH]
```

The command should emit normal bridge events:

- `start`
- optional `progress`
- `result`
- `done`

The result payload should include:

```json
{
  "database_path": "/Users/example/.simanalysis/inventory.sqlite3",
  "export_path": null,
  "scan_id": 1,
  "snapshot_id": 1,
  "summary": {
    "root_path": "/Users/example/Documents/Electronic Arts/The Sims 4",
    "file_count": 12,
    "package_count": 2,
    "script_count": 1,
    "archive_count": 1,
    "unknown_extension_count": 0,
    "total_size_bytes": 12345,
    "added_count": 12,
    "removed_count": 0,
    "modified_count": 0,
    "moved_count": 0,
    "unchanged_count": 0,
    "package_parse_ok_count": 1,
    "package_parse_error_count": 1,
    "resource_count": 7
  },
  "warnings": []
}
```

## JSON Export

When `--export` is supplied, the command writes a JSON snapshot containing:

- database path
- scan id
- snapshot id
- summary
- files
- packages
- package resources
- file events

The export must not include private raw file contents. It may include local paths because this is an explicit local export path, but cloud upload is out of scope.

## Desktop UI

Add a thin Local Inventory page.

The UI should:

- appear in the sidebar as `Inventory`
- let the user enter or choose the Sims 4 folder
- start an inventory scan through the existing Tauri bridge path
- show running, error, and completed states
- display the latest scan summary
- display change counts since prior scan
- display package parse health
- display the database path returned by the backend

The page is a utility surface. It should be dense, calm, and scan-friendly, matching the current desktop app rather than becoming a landing page.

The UI must not offer cleanup, quarantine, delete, profile activation, cache reset, or update actions in this slice.

## Architecture

Backend:

- new inventory service module owns SQLite schema, scanning, snapshots, and export
- bridge command calls the service
- existing scanner and analyzer behavior remains unchanged

Suggested backend files:

- `src/simanalysis/inventory.py`
- `src/simanalysis/bridge/commands.py`
- `src/simanalysis/bridge/__init__.py`

Desktop integration:

- `src-tauri/src/lib.rs`
- `web/src/api.js`
- `web/src/App.jsx`
- `web/src/components/Sidebar.jsx`
- `web/src/views/Inventory.jsx`

Tests:

- `tests/unit/test_inventory.py`
- `tests/unit/test_bridge_commands.py`
- `tests/unit/test_bridge_main.py`
- existing Tauri Rust tests
- web build verification

## Safety Model

Allowed:

- read files under the selected Sims 4 root
- compute SHA-256 hashes
- parse `.package` files read-only through `DBPFReader`
- write Simanalysis-owned SQLite data under `~/.simanalysis` or supplied `--db-path`
- write a JSON export to a supplied `--export` path

Not allowed:

- moving, renaming, deleting, or editing files under the Sims 4 folder
- writing package, save, tray, cache, or options files
- executing `.ts4script` code
- extracting archives into `Mods`
- marking unknown compatibility as safe
- auto-launching The Sims 4

## Error Handling

- Missing Sims 4 folder: bridge command fails cleanly with an error event.
- Missing `Mods` folder: scan still succeeds and reports zero mod packages.
- Permission-denied file: scan records a warning and continues.
- File deleted during scan: scan records a warning and continues.
- Corrupt package: package row gets `parse_status = "error"` and `parse_error`.
- Unsupported DBPF compression: package row may be parse error or partial, but the scan must not crash.
- SQLite failure: command emits an error and does not claim a completed snapshot.

## Testing

Backend tests should cover:

- first scan stores file rows and returns all files as added
- second identical scan returns unchanged counts
- adding a file returns added count
- removing a file returns removed count
- modifying same relative path returns modified count
- moving same file content returns moved count
- corrupt package records parse error without crashing
- valid synthetic package records package/resource metadata
- explicit JSON export writes expected summary and file entries
- scanner skips app-owned generated folders inside the selected Sims root

Bridge tests should cover:

- parser accepts `inventory-scan`
- command emits `start`, `result`, and `done`
- invalid path emits an error through existing bridge behavior

Tauri tests should cover:

- `build_args("inventory-scan", ...)` produces the expected command arguments
- optional database and export paths are passed when supplied

Frontend validation should cover:

- web build passes
- sidebar and route compile
- API method calls `inventory-scan`
- page renders idle, running, completed, and error states without layout breakage

## Validation Plan

1. Run focused inventory unit tests.
2. Run focused bridge parser and bridge command tests.
3. Run focused existing scanner tests to ensure `ModScanner` behavior is unchanged.
4. Run Rust Tauri tests for argument mapping.
5. Run web build.
6. Run a bridge inventory scan against a synthetic Sims 4 folder.
7. Run a read-only bridge inventory scan against the real Sims 4 folder if filesystem access permits.
8. Confirm no files under the scanned Sims 4 folder were modified by comparing mtimes or by using an isolated synthetic folder for mutation-sensitive checks.

## Later Work

- duplicate and misplaced-file planner
- conflict graph over persisted resources
- profile manager integration
- patch-day inventory status
- cache doctor integration
- cloud-safe redacted export format
- incremental hashing based on previous size and mtime
- archive metadata inspection
- script static analyzer persistence
