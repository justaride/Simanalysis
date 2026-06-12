# Simanalysis Current Implementation Status

**Last consolidated:** 2026-06-11
**Status source:** Phase 0 truth pass on branch `codex/phase0-real-fixtures`

This file replaces the old generated status report that called the project
production-ready. That report is archived at
`docs/archive/status/IMPLEMENTATION_STATUS_2025-12-21.md`.

## Source Of Truth

- Product direction and long-range roadmap: `IMPLEMENTATION_ROADMAP.md`
- Current verified implementation status: this file and `docs/STATUS.md`
- DBPF/parser-specific status: `DBPF_IMPLEMENTATION_STATUS.md`
- Historical/generated reports: `docs/archive/status/`

## Phase 0 Truth Pass

### T0.1 Verified Resource Type Registry

Implemented on this branch:

- Added `src/simanalysis/formats/types.py`, sourced from S4TK
  `@s4tk/models` `0.6.14` at commit
  `4345132fab79a92516095d22d9458b0db334dce5`.
- Replaced fabricated Sims 4 resource constants in code, tests, and examples.
- Changed package tuning extraction to scan verified tuning resource classes.
- Stopped treating STBL binary string tables as XML tuning.

### T0.2 Real Fixture Corpus

Implemented on this branch:

- Added `real` and `synthetic` pytest markers.
- Added `tests/fixtures/real/corpus-manifest.json` as the real-file test
  contract.
- Added committed, redistributable fixtures for:
  - S4TK-generated DBPF tuning package
  - sanitized BetterExceptions-style `lastException` log
  - deterministic `.ts4script` ZIP archive
  - minimal save-like DBPF file
  - minimal Tray item group
- Added a local-only corpus builder for non-redistributable real-world files.
- Wired CI to run `pytest -m real --no-cov` before the full coverage suite.

## Ledger / Local Truth Progress

Implemented on this branch after the Phase 0 truth pass:

- Added `src/simanalysis/inventory.py`, a read-only SQLite inventory ledger.
- The ledger initializes durable tables for scans, files, packages, resources,
  snapshots, snapshot file rows, per-file change events, and event log entries.
- Inventory scans record file identity, SHA-256, size, mtime, extension,
  package parse status, package parse errors, and DBPF resource keys without
  moving or deleting Sims files.
- Symlinked paths are skipped with warnings so inventory scans do not follow
  links out of the selected Sims folder.
- Repeat scans compare against the latest snapshot and report added, removed,
  moved, modified, and unchanged counts.
- Latest scan file events can be queried with source/destination context for
  moved files plus explicit removed-source rows.
- Latest snapshots can be exported as JSON-serializable dictionaries for
  support and regression fixtures.
- Recent scan summaries can be queried newest-first through the inventory
  history helper and bridge command.
- The desktop bridge and Tauri sidecar argument builder now expose
  `inventory-scan`, `inventory-history`, and `inventory-file-events` with
  optional `--db` routing.
- The web API layer has non-visual wrappers for `scanInventory` and
  `inventoryHistory` plus `inventoryFileEvents`; the visual Inventory route is
  still pending design approval.

## Cleanup Planner Progress

Implemented on this branch after the inventory ledger:

- Added `src/simanalysis/cleanup.py`, a read-only planner that consumes the
  latest inventory snapshot.
- The planner is scoped to `Mods` files and reports exact duplicates, inactive
  archives, nested `Resource.cfg`, support files, and misplaced Tray files.
- Plans include proposed future destinations but do not create
  `_Simanalysis_Cleanup`, move files, or write Sims-folder manifests.
- The desktop bridge and Tauri/web API plumbing expose `cleanup-plan`; the
  visual cleanup route remains future work.

## Current Product Reality

Simanalysis has a substantial local Sims Doctor foundation, including the Tauri
desktop shell, Python sidecar bridge, package/script scanning, conflict
detection, crash/UI autopsy flows, Treatment/Auto-Bisect, and Live Monitoring
surfaces from earlier shipped slices.

It should not currently be described as generally production-ready. Several
roadmap foundations are still incomplete, including the visual inventory route,
visual cleanup route, profile-aware state, Patch Day Shield, general reversible
action engine, Cache Doctor, update staging, and broader real-world corpus
coverage.

## Current Verification Gates

The Phase 0 branch is expected to pass:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
COVERAGE_FILE=/tmp/simanalysis-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-full.coverage .venv/bin/python -m pytest -q
```

Tauri/web gates remain relevant before publishing UI-affecting changes.

## Next Work

The visual Inventory route and visual Cleanup route remain pending design
approval. The next non-visual slice should stay ledger-backed and reversible:
turn review-only findings into an explicit journaled operating-table plan
before any file moves are allowed.

The draft design for that slice is
`docs/superpowers/specs/2026-06-12-operating-table-v1-design.md`. That
mutating-engine design is approved; the implementation plan is
`docs/superpowers/plans/2026-06-12-operating-table-v1.md`, and the next step is
TDD execution.
