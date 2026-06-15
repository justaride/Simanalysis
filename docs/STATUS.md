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
public CLI exposes `simanalysis ledger scan|history|events`, and the
bridge/Tauri/web API exposes `inventory-scan`, `inventory-history`, and
`inventory-file-events`, now exposed in the desktop Inventory route as a
read-only ledger surface. The read-only Cleanup Planner v1 adds `cleanup-plan`
for Mods-folder review findings, now exposed in the desktop Cleanup route as a
read-only review surface. Operating Table v1 adds manifest-first cleanup
staging, apply, restore, and status plumbing, plus the `simanalysis ops
plan|commit|restore|undo` CLI surface. The desktop Cleanup route now exposes
visual Operating Table controls for external plan JSON export, explicit action
selection, manifest staging, status refresh, and confirm-gated apply/restore.
The shared read-only Doctor payload is
now available through `simanalysis doctor`, combining script crash and UI
exception autopsy without changing Sims files, and the
manifest-based Treatment/Auto-Bisect engine is available through
`simanalysis bisect start|status|next|record-verdict|restore|handoff`, with the
same read-only handoff available to the desktop sidecar as
`simanalysis-bridge treatment-handoff`; the Treatment desktop route can prepare,
copy, and download that Markdown handoff from a saved session without moving
files. The True Engine now has conservative read-only STBL v5 and SimData
metadata parsers wired into package scanning, with
compact parser/resource truth exposed through CLI JSON, the desktop bridge, HTTP
scan, and WebSocket scan responses. The desktop Dashboard now sources total
files, space used, severity summary, and file distribution from the current scan
payload instead of placeholders. The shared Doctor payload now includes
evidence-labeled verdicts and symptom playbooks for active bisection candidates
and partial-evidence review; the desktop Doctor route renders those verdicts and
playbooks above the detailed findings. Saved bisection manifests preserve the
Doctor summary, verdict, and playbook context, and the handoff renderer includes
that context alongside the rollback journal; a BuildBuy03B-style replay test now
proves the Doctor JSON -> bisect -> verdict -> restore -> handoff path. Doctor
JSON/text output now includes a read-only script/UI exception timeline sorted in
deterministic chronological order. `simanalysis doctor --inventory-db` can add
read-only ledger context from an existing SQLite inventory database, including
recent scan history and latest file events, without starting a new scan or
mutating files. The desktop Doctor route now exposes that same ledger database
input through the Tauri bridge and renders the timeline plus ledger history
panels when the shared Doctor payload includes them. Patch Day Shield v0 now
exists as a read-only CLI/backend/desktop surface through
`simanalysis patch-day status|record`, bridge/Tauri
`patch-day-status|record`, and the Patch Day route. It compares
`GameVersion.txt` with app-owned baseline state, marks
script/UI/gameplay/CAS categories as `unknown_after_patch` after a version
change, and records explicit baselines without changing Mods, saves, or Tray
files. The Patch Day desktop route now also reads Profile Manager Light app
config to show the active Sims 4 profile, compare it with the selected Patch
Day folder, recommend a separate safe test profile after detected patches, and
surface a Cache Doctor recommendation without automatic re-enable or profile
mutation. Profile Manager Light v0 now exists in desktop Settings for storing
an active Sims 4 root in app config, deriving Mods/Tray/saves/cache paths, and
remembering known roots without changing Sims files; primary desktop views use
those paths as input defaults without scanning or mutating files on load.
Cache Doctor v0 now exists as a read-only CLI/backend/desktop surface through
`simanalysis cache status`, bridge/Tauri `cache-status`, and the Cache Doctor
route, reporting known cache targets and symlink warnings without deleting or
moving cache files. Cache Doctor reversible cleanup now adds
`simanalysis cache plan|apply|restore`, bridge/Tauri
`cache-plan|cache-apply|cache-restore|cache-operation-status`, and desktop
controls for Plan JSON export, explicit action selection, confirm-gated
quarantine, manifest refresh, and restore. Cache cleanup quarantines supported
targets into `_Simanalysis_CacheDoctor` and refuses game-process, symlink,
stale-evidence, missing-quarantine, and restore-collision hazards instead of
permanently deleting cache files. Save Protector v0 now exists as a read-only
CLI/backend/desktop surface through `simanalysis save-protector status`,
bridge/Tauri `save-protector-status`, and the Save Protector route, grouping
saves/backups and surfacing AppleDouble, iCloud-placeholder, symlink, and
case-collision signals without editing saves. Save Protector desktop launch
guidance now combines read-only save status, active profile evidence, and Patch
Day status to label missing evidence, unknown-after-patch risk, and manual
save-copy testing recommendations without mutating saves. Tray Protector v0 now
exists as a read-only CLI/backend/desktop surface through `simanalysis tray status`,
bridge/Tauri `tray-protector-status`, and the Tray Protector route, grouping
Tray files and surfacing sidecar-only, AppleDouble, iCloud-placeholder,
symlink, and case-collision signals without editing Tray. Tray Protector now
adds calibrated dependency-scope signals with confidence, dependency kind,
anchor state, and evidence for likely CAS, likely Build/Buy, probable
sidecar-without-anchor, and unknown states without claiming guaranteed matches
or certain missing dependencies. Update Desk v0 now exists as a read-only
CLI/backend/desktop surface through `simanalysis updates
status`, bridge/Tauri `update-staging-status`, and the Update Desk route,
classifying staged downloads, source sidecars, corrupt ZIPs, archive path
escapes, symlink-like ZIP entries, iCloud placeholders, AppleDouble files,
symlinks, and case collisions without extracting archives or changing Mods.
`simanalysis updates plan` can generate a read-only staged-download manifest
with loose copy, archive-review/blocker, and ZIP member extraction-staging plan
actions without writing to Mods, and the same payload is available to the
sidecar/Tauri contract as `update-staging-plan`; desktop Update Desk can
preview that plan with explicit Mods path input and snapshot/no-mutation gate
labels. The backend/CLI/bridge contract now also supports manifest-backed
`simanalysis updates commit|undo` and `update-staging-commit|update-staging-undo`
for explicit loose-file copy actions, with game-process, path, symlink,
hash/size, collision, modified-file-on-undo, tampered-plan-gate, partial-copy
undo, and crash-recovery guards. The desktop Update Desk route now exposes Plan
JSON export, explicit planned copy-action selection, confirm-gated loose-file
commit, manifest status refresh, and undo through the same guarded bridge/Tauri
contract; archive install/extraction remains unavailable, and ZIP member rows
are planning evidence only, not commit-eligible actions. Profile-aware file
operations, safe archive update installation, and profile-aware Patch Day
re-enable workflows remain pending follow-on slices.
`docs/public-v3-workplan.md` and
`docs/simanalysis-public-v3-presentation.html` capture the remaining Public v3
roadmap and executive presentation.

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
