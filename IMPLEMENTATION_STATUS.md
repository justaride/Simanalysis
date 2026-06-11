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

## Current Product Reality

Simanalysis has a substantial local Sims Doctor foundation, including the Tauri
desktop shell, Python sidecar bridge, package/script scanning, conflict
detection, crash/UI autopsy flows, Treatment/Auto-Bisect, and Live Monitoring
surfaces from earlier shipped slices.

It should not currently be described as generally production-ready. Several
roadmap foundations are still incomplete, including persistent inventory,
profile-aware state, Patch Day Shield, general reversible action engine,
Cache Doctor, update staging, and broader real-world corpus coverage.

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

The next plan step after this status consolidation is to continue from the
June 11 workplan toward the Ledger/local-memory layer: persistent scan history,
file identity, snapshots, and event logging, still read-only at first.
