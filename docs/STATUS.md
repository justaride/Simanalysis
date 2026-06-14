# Simanalysis Status Index

**Last consolidated:** 2026-06-15

Use this index to avoid mixing current Phase 0 truth with older generated status
reports.

## Current Status Documents

- `../IMPLEMENTATION_STATUS.md` - current implementation status and Phase 0
  truth-pass summary.
- `../DBPF_IMPLEMENTATION_STATUS.md` - current DBPF/parser status.
- `../IMPLEMENTATION_ROADMAP.md` - product direction and development tracks.
- `../CHANGELOG.md` - release-oriented change log.

Current branch note: the read-only SQLite inventory ledger now records scan
history plus per-file change events in `src/simanalysis/inventory.py`; the
bridge/Tauri/web API exposes `inventory-scan`, `inventory-history`, and
`inventory-file-events`. The read-only Cleanup Planner v1 adds `cleanup-plan`
for Mods-folder review findings. Operating Table v1 adds manifest-first
non-visual cleanup staging, apply, restore, and status plumbing. The True Engine
now has conservative read-only STBL v5 and SimData metadata parsers wired into
package scanning. Visual inventory and cleanup routes remain pending design
approval.

## Historical Status Snapshots

These files are preserved for context only and are not current project truth:

- `archive/status/CODE_REVIEW_RESPONSE_2025-review.md`
- `archive/status/DBPF_ENHANCEMENT_SUMMARY_2025-10-24.md`
- `archive/status/IMPLEMENTATION_STATUS_2025-12-21.md`
- `archive/status/DBPF_IMPLEMENTATION_STATUS_2025-10-24.md`
- `archive/status/REQUIREMENTS_VERIFICATION_2025-10-24.md`
- `archive/status/REVIEW_CLARIFICATION_2025-10-22.md`
- `archive/status/SETUP_SUMMARY_2025-10-21.md`
- `archive/status/SPRINT_1_COMPLETION_SUMMARY_2025-10-21.md`
- `archive/status/TECHNICAL_SPECIFICATION_2025-12-21.md`

## Current Verification Contract

The branch-level Python gates are:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
COVERAGE_FILE=/tmp/simanalysis-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-full.coverage .venv/bin/python -m pytest -q
```

Run web and Tauri checks before publishing changes that touch those surfaces.
