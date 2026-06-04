# World Model v1, Fix Plan v1, Safe Cache Fix, Master Plan, and Catalog Baseline validation

Date: 2026-06-04
Branch: `codex/world-model-v1`

## Scope

World Model v1 adds a read-only Sims 4 inventory layer:

- active top-level `Mods` units
- `_Disabled*` roots
- `_Quarantine*` roots
- archive/import roots
- Tray, save, crash-log, and cache evidence counts
- bridge commands: `world-scan` and `world-status`
- desktop route: `/world`

Fix Plan v1 adds a planning layer:

- bridge commands: `fix-plan` and `fix-status`
- desktop route: `/fixes`
- review-only actions for active duplicate files, deep script installs, and disabled shadow copies
- one applyable cache cleanup candidate that moves known cache artifacts into a manifest-backed `_Simanalysis_Fixes/_CacheCleanup_*` backup
- bridge commands: `fix-apply`, `fix-restore`, and `fix-session-status`
- desktop affordance for cache cleanup apply and manifest restore

No duplicate/package/script/shadow-copy move, quarantine, delete, Treatment manifest, or `_Simanalysis_World` write is part of this slice. Live Sims folder mutation was not executed during validation.

Master Plan adds a read-only intelligence lane:

- bridge commands: `master-plan` and `master-status`
- desktop route: `/master-plan`
- local update/catalog tracking gaps from active script mods without version signals
- performance pressure actions from large units, script count, package count, and active unit count
- creator profiles inferred from unit and file names
- no network mod-update lookup or live Sims mutation

Catalog Baseline adds local snapshot and change detection:

- bridge commands: `master-baseline-save`, `master-baseline-diff`, and `master-baseline-status`
- Tauri command routing for baseline save, diff, and status
- desktop controls on `/master-plan` for Save Baseline, Compare, and Refresh
- baseline manifests are Simanalysis-owned JSON files under `_Simanalysis_MasterPlan`
- no duplicate/package/script/shadow-copy move, quarantine, delete, or live mod mutation
- no live baseline save was executed during validation

## Verification

- `.venv/bin/python -m pytest -q` -> 393 passed
- `.venv/bin/ruff check .` -> passed
- `.venv/bin/mypy src/simanalysis` -> passed across 47 source files
- `node --test web/src/views/masterPlanModel.test.js web/src/views/fixPlanModel.test.js web/src/views/worldModel.test.js web/src/views/liveMonitorModel.test.js` -> 21 passed
- `npm run lint` in `web/` -> passed
- `npm run build` in `web/` -> passed
- `scripts/build-sidecar.sh` -> passed and staged `src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin`
- `cargo check` in `src-tauri/` -> passed
- `git diff --check` -> passed
- packaged sidecar temp smoke: `fix-apply`, `fix-session-status`, and `fix-restore` moved and restored `/tmp/.../The Sims 4/localthumbcache.package`
- packaged sidecar temp smoke: `master-plan` produced one catalog entry and inferred creator `Creator`
- packaged sidecar temp smoke: `master-baseline-save`, `master-baseline-status`, and `master-baseline-diff` reported `added: 1`, `changed: 1`, `removed: 1`, `unchanged: 0` from a temp Sims fixture

## Live Read-Only Smoke

Command:

```bash
src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin master-status "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Result summary:

```json
{
  "active_units": 1285,
  "catalog_entries": 1285,
  "creator_profiles": 210,
  "performance_actions": 4,
  "update_candidates": 4,
  "warnings": 0
}
```

Command:

```bash
src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin world-status "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Result summary:

```json
{
  "active_units": 1285,
  "disabled_units": 12,
  "quarantined_units": 12,
  "archived_units": 2,
  "package_files": 44413,
  "script_files": 242,
  "tray_files": 11821,
  "save_files": 31,
  "log_files": 11,
  "cache_files": 1,
  "warnings": 0
}
```

Command:

```bash
src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin fix-status "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Result summary:

```json
{
  "actions": 18888,
  "high": 19,
  "medium": 18868,
  "low": 1,
  "warnings": 0,
  "blockers": 0
}
```

Command:

```bash
src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin master-baseline-status "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Result summary:

```json
{
  "baseline_exists": false,
  "baseline_path": null,
  "summary": {
    "added": 0,
    "removed": 0,
    "changed": 0,
    "unchanged": 0,
    "warnings": 0
  },
  "blockers": ["No master baseline found"]
}
```

This was status-only. It did not create `_Simanalysis_MasterPlan` in the live Sims folder.

Browser QA:

- opened `http://127.0.0.1:5174/world`
- confirmed `World` heading, `Scan World` button, path input, and empty state rendered
- confirmed no current-server console errors
- opened `http://127.0.0.1:5174/fixes`
- confirmed `Fixes` heading, `Plan Fixes` button, path input, manifest-backed cache cleanup notice, and empty state rendered
- confirmed no current-server console errors
- opened `http://127.0.0.1:5174/master-plan`
- confirmed `Master Plan` heading, `Build Plan` button, path input, read-only notice, and empty state rendered
- confirmed `Catalog Baseline` section rendered with Added, Changed, Removed, Unchanged counters and Save Baseline, Compare, Refresh controls
- confirmed no current-server console errors
- screenshot capture through the browser backend timed out during QA, so visual evidence is DOM and console based for this pass
