# Simanalysis Current Implementation Status

**Last consolidated:** 2026-06-15
**Status source:** Phase 0 truth pass plus subsequent merged True Engine/Ledger/Ops slices

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

## True Engine Progress

Implemented after the Phase 0 truth pass:

- Added a conservative read-only STBL version 5 parser that extracts keyed
  UTF-8 strings and returns explicit `parsed`, `unsupported`, or `malformed`
  status with warnings.
- Wired STBL parsing into package scans as `mod.string_tables` while keeping
  malformed resources non-fatal and visible.
- Added a conservative read-only SimData parser that extracts `DATA` table,
  schema, and column metadata as `mod.sim_data`; row/value decoding remains
  future work.
- Exposed compact resource and parser truth in the public mod-analysis JSON
  surface used by CLI reports, the desktop bridge, HTTP scan, and WebSocket
  scan responses, including resource type names, per-mod counts,
  STBL/SimData parse-status counts, parser warnings, and conflict details.
- Corrected DBPF compressed-resource detection so zlib-compressed resources are
  treated as compressed from the index compression flag, even when compressed
  and decompressed sizes are equal.

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
- The public CLI now exposes read-only `simanalysis ledger scan`, `simanalysis
  ledger history`, and `simanalysis ledger events` commands with human text and
  JSON output over the same inventory database and snapshot/event contracts.
- The web API layer has wrappers for `scanInventory`, `inventoryHistory`, and
  `inventoryFileEvents`; the desktop Inventory route now renders those
  contracts as a read-only ledger surface with scan summary, recent history,
  latest file events, warnings, and filtered snapshot rows.

## Cleanup Planner Progress

Implemented on this branch after the inventory ledger:

- Added `src/simanalysis/cleanup.py`, a read-only planner that consumes the
  latest inventory snapshot.
- The planner is scoped to `Mods` files and reports exact duplicates, inactive
  archives, nested `Resource.cfg`, support files, and misplaced Tray files.
- Plans include proposed future destinations but do not create
  `_Simanalysis_Cleanup`, move files, or write Sims-folder manifests.
- The desktop bridge and Tauri/web API plumbing expose `cleanup-plan`; the
  desktop Cleanup route now renders that plan as a read-only review surface.

## Operating Table Progress

Implemented on this branch after Cleanup Planner v1:

- Added `src/simanalysis/operating_table.py`, a manifest-first cleanup
  operation engine.
- Cleanup actions must be explicitly selected or staged with an explicit
  all-actions flag.
- Apply and restore use the operation manifest, block while The Sims 4 is
  running, reject path escapes/symlinks/collisions, and never delete or
  overwrite files.
- The public CLI now exposes `simanalysis ops plan`, `simanalysis ops commit`,
  `simanalysis ops restore`, and `simanalysis ops undo`; commit stages an
  operation manifest and applies only explicitly selected actions or an
  explicit all-actions selection.
- The desktop bridge and Tauri/web API plumbing expose `cleanup-stage`,
  `cleanup-apply`, `cleanup-restore`, and `cleanup-status`; the desktop Cleanup
  route now adds visual Operating Table controls for external plan JSON export,
  explicit action selection, manifest staging, status refresh, and
  confirm-gated apply/restore.

## Patch Day Shield Progress

Implemented after the Doctor ledger-history work:

- Added `src/simanalysis/patch_day.py`, a read-only Patch Day state helper that
  reads `GameVersion.txt` from the selected Sims 4 user folder and compares it
  with an app-owned baseline JSON file.
- Added `simanalysis patch-day status` to report whether the current game
  version is unrecorded, unchanged, changed, or missing, with JSON/text output
  and no Sims-folder mutation.
- Added `simanalysis patch-day record` to record the current game version as an
  explicit baseline in Simanalysis state; it writes only the selected state
  file and refuses to record when `GameVersion.txt` is absent.
- When a version change is detected, Patch Day Shield v0 labels script mods, UI
  mods, gameplay tuning, and Build/Buy/CAS as `unknown_after_patch`, recommends
  a vanilla test plus save-copy test, and keeps `automatic_reenable` false.
- Added `patch-day-status` and `patch-day-record` to the desktop bridge and
  Tauri sidecar argument layer.
- Added a desktop Patch Day route for choosing a Sims 4 folder, checking
  current baseline status, reviewing post-patch risk classes, and
  confirm-recording a new baseline. Recording updates only Simanalysis state.
- Update staging and profile-aware re-enable workflows remain future slices.

## Profile Manager Light Progress

Implemented after Patch Day Shield v0:

- Replaced the static desktop Settings placeholder with a Profile Manager Light
  surface backed by the existing Tauri app config commands.
- The Settings route now loads `active_sims4_profile`, derives Mods, Tray,
  saves, and cache-root paths from that selected Sims 4 user folder, and stores
  known profile roots for quick selection.
- Saving a profile updates Simanalysis app state only, including
  `last_scan_path` as the active profile's `Mods` folder for compatibility with
  existing scan views.
- The desktop views for Mod Manager, Inventory, Cleanup, Doctor, Treatment,
  Live Monitor, Patch Day, Tray Organizer, and Save Analyzer now use that app
  state as input defaults when no route-specific path is already stored.
- The UI labels the safety boundary explicitly: Profile Manager Light does not
  move, enable, disable, quarantine, delete, or rewrite Sims files.
- Full profile switching, profile-aware Operating Table actions, and
  profile-aware Patch Day re-enable workflows remain future slices.

## Cache Doctor Progress

Implemented after Profile Manager Light v0:

- Added `src/simanalysis/cache_doctor.py`, a read-only Cache Doctor status
  helper for known Sims 4 cache targets.
- Added `simanalysis cache status` with text and JSON output for
  `localthumbcache.package`, `avatarcache.package`, `cache`, `cachestr`,
  `onlinethumbnailcache`, and `cachewebkit` presence, size, item count,
  warnings, and recommendations.
- Symlinked cache targets and symlinked cache-directory entries are skipped
  with explicit warnings.
- Added `simanalysis-bridge cache-status`, Tauri `cache-status` argument
  support, web API plumbing, and a desktop Cache Doctor route over the same
  read-only payload.
- The desktop route uses the Profile Manager Light cache-path default, shows
  status, known cache targets, warnings, and recommendations, and exposes no
  cache deletion control.
- Cache Doctor v0 never deletes, moves, or rewrites cache files; future cache
  cleanup must be staged through an Operating Table manifest after snapshot and
  user approval.
- Cache-clearing operations remain future slices.

## Save Protector Progress

Implemented after Cache Doctor v0:

- Added `src/simanalysis/save_protector.py`, a read-only Save Protector status
  helper for the Sims 4 `saves` directory.
- Added `simanalysis save-protector status` with text and JSON output for
  primary `.save` files, `.save.ver*` backup files, orphan backup groups, total
  size, latest modified time, warnings, signals, and recommendations.
- Save Protector v0 surfaces AppleDouble sidecar files, iCloud placeholder or
  eviction markers, symlinked save entries, non-file entries, and casefold path
  collisions as evidence-labeled signals.
- Added desktop Save Protector v0 through `save-protector-status` bridge/Tauri
  plumbing, a route, read-only view-models, and profile-aware Sims 4 folder
  defaults.
- Save Protector v0 never edits, rewrites, restores, or deletes saves. Tray
  dependency signals and any future save-adjacent operations remain future
  slices.

## Tray Protector Progress

Implemented after desktop Save Protector v0:

- Added `src/simanalysis/tray_protector.py`, a read-only Tray dependency status
  helper for the Sims 4 `Tray` directory.
- Added `simanalysis tray status` with text and JSON output for Tray file
  counts, grouped stems, anchored `.trayitem` groups, sidecar-only groups,
  extension counts, warnings, signals, and recommendations.
- Tray Protector v0 surfaces sidecar files without a `.trayitem` anchor,
  AppleDouble sidecar files, iCloud placeholder or eviction markers, symlinked
  Tray entries, non-file entries, and casefold path collisions as
  evidence-labeled signals.
- Added desktop Tray Protector v0 through `tray-protector-status` bridge/Tauri
  plumbing, a Tray Protector route, profile-aware Sims 4 folder defaults, and
  view-model tests over the same read-only Tray status payload.
- Tray Protector v0 never edits, restores, dedupes, or deletes Tray files.
  Any future Tray-adjacent operations remain future slices.

## Update Desk Progress

Implemented after desktop Tray Protector v0:

- Added `src/simanalysis/update_desk.py`, a read-only Update Desk staging
  status helper for external-download staging folders.
- Added `simanalysis updates status` with text and JSON output for staged item
  counts, archive/package/script classification, source-binding sidecars,
  extension counts, warnings, signals, and recommendations.
- Update Desk v0 lists ZIP archives without extraction, labels corrupt ZIPs,
  flags archive member path escapes and symlink-like entries, and marks
  `.rar`/`.7z` archives as listing-unsupported until a later archive engine
  slice.
- Update Desk v0 surfaces AppleDouble sidecar files, iCloud placeholder or
  eviction markers, symlinked staging entries, non-file entries, orphan source
  sidecars, missing or invalid source bindings, and casefold path collisions as
  evidence-labeled signals.
- Added desktop Update Desk v0 through `update-staging-status` bridge/Tauri
  plumbing, an Update Desk route, and a staging-folder review surface for the
  same read-only status payload.
- Added `simanalysis updates plan`, a read-only staged update plan generator
  that maps loose `.package`/`.ts4script` files to copy actions, keeps archives
  in explicit review/blocker actions, hashes staged sources, checks destination
  clashes and case collisions, and can write a plan manifest when `--output` is
  provided.
- Added safe ZIP member planning to `simanalysis updates plan`: readable ZIP
  `.package`/`.ts4script` members now appear as `stage_archive_member` actions
  with member hash/size evidence, an extraction-staging path under the staging
  folder, and final destination clash checks. The plan still does not extract
  archive bytes or make archive-member actions commit-eligible.
- Added `update-staging-plan` bridge/Tauri plumbing for the same read-only plan
  payload, requiring an explicit Mods path and exposing no apply/commit command
  through desktop.
- Added desktop Update Desk install-plan preview over the same bridge contract,
  including explicit Mods path input, snapshot/no-mutation gate labels, and
  copy/archive/blocker action rows with no install/apply control.
- Added manifest-backed Update Desk commit/undo backend through
  `UpdateInstaller`, `simanalysis updates commit|undo`, and
  `update-staging-commit|update-staging-undo` bridge/Tauri argument plumbing.
  Commits require explicit selected actions or `--all-actions`, copy only loose
  staged `.package`/`.ts4script` actions, keep staged downloads in place,
  record action state and installed hash/size evidence in an update manifest,
  block while The Sims 4 is running, reject stale plan evidence, path escapes,
  symlinked sources/destinations, destination collisions, and modified files on
  undo, and can undo a copied file left behind by a crash during `copying`.
- Hardened Update Desk plan/commit/undo invariants: loaded or in-memory plans
  must still declare snapshot-required, read-only, and no-Mods-mutation gates
  before staging/commit; tests now cover tampered plan gates, stale source hash
  and size, bridge-level refusal, partial-copy failure recovery through undo,
  copying-state crash recovery, game-process guard refusal, and modified
  installed-file undo refusal.
- Added desktop Update Desk commit/undo controls over the same guarded
  contract. The route now requires a Plan JSON export path, explicit planned
  copy-action selection, and a confirm gate before committing loose
  `.package`/`.ts4script` actions; it can also refresh the operation manifest
  and undo copied files through `update-staging-operation-status` and
  `update-staging-undo`.
- Update Desk v0 still never extracts archives, installs archive contents,
  overwrites existing Mods files, or deletes staged downloads. Desktop can show
  ZIP member planning rows, but archive-member rows remain review/staging-plan
  evidence and are not selectable for commit.
- Added `docs/public-v3-workplan.md` and
  `docs/simanalysis-public-v3-presentation.html` as the durable Public v3
  roadmap/workplan and executive presentation artifacts.

## Current Product Reality

Simanalysis has a substantial local Sims Doctor foundation, including the Tauri
desktop shell, Python sidecar bridge, package/script scanning, conflict
detection, crash/UI autopsy flows, Treatment/Auto-Bisect, and Live Monitoring
surfaces from earlier shipped slices.
The desktop Dashboard now derives total file count, space used, severity
summary, and file-distribution chart values from the current scan payload
rather than placeholder estimates.

The combined Doctor payload is now shared outside the desktop bridge and exposed
through `simanalysis doctor` for read-only script-crash plus UI-exception
autopsy in text or JSON form. The existing Treatment/Auto-Bisect session engine
is now exposed through `simanalysis bisect start`, `status`, `next`,
`record-verdict`, `restore`, and read-only Markdown `handoff`. The desktop
sidecar/Tauri path can also request the same handoff through
`simanalysis-bridge treatment-handoff`, and the Treatment desktop route can
prepare, copy, and download that Markdown handoff from a saved session without
moving files. Mutating steps remain manifest-based and keep the game-process
guard. The shared Doctor JSON/text payload now includes evidence-labeled
verdict objects plus symptom playbooks for active-candidate bisection and
partial-evidence review, and the desktop Doctor route now renders those
verdict/playbook objects directly above the detailed crash/UI findings. Saved
bisection manifests now preserve that Doctor summary, verdict, and playbook
context, and the read-only handoff renders it with the move journal; the replay
gate covers a BuildBuy03B-style session from Doctor JSON through move, verdict,
restore, and rollback handoff. The Doctor payload and text output now also
include a read-only timeline that combines parsed script and UI exception
reports in deterministic chronological order. `simanalysis doctor` can also
take an explicit `--inventory-db` to include read-only ledger context: recent
inventory scans plus the latest file events, without scanning or mutating the
Sims folder. The desktop Doctor route can pass the same explicit inventory
database through the Tauri sidecar and now renders the Doctor timeline plus
ledger status, latest scan counts, recent file events, and ledger warnings from
the shared payload. Patch Day Shield v0 is available as a read-only CLI and
desktop surface for detecting `GameVersion.txt` baseline changes, classifying
mod categories as unknown after a patch, and recording an explicit baseline in
Simanalysis state without changing Mods, saves, or Tray files. Profile Manager
Light v0 is available in desktop Settings for remembering an active Sims 4 root
and deriving common folder paths from app state only; primary desktop views use
those paths as input defaults without scanning or mutating files on load. Cache
Doctor v0 is available as a read-only CLI/backend and desktop route for
reviewing known cache targets and symlink warnings without deleting or moving
files. Save Protector v0 is available as a read-only CLI/backend for reviewing
save/backups and filesystem trust signals, with a desktop route over the same
payload and no save mutation support. Tray Protector v0 is available as a
read-only CLI/backend and desktop route for reviewing Tray groups and
dependency signals without editing Tray files. Update Desk v0 is available as a
read-only CLI/backend and desktop route for reviewing staged external
downloads, source sidecars, and safe archive-listing signals without extracting
archives. `simanalysis updates plan` can generate a copy/review/blocker
manifest for staged downloads and can represent readable ZIP package/script
members as extraction-staging plan rows without extracting to Mods.
`simanalysis updates commit|undo` can now journal and reverse explicit
loose-file copy actions into Mods. Desktop Update Desk can now export a Plan
JSON, commit explicitly selected loose-file copy actions, refresh the operation
manifest, and undo through the same guarded bridge/Tauri contract; archive
install/extraction remains unavailable.
Deeper ledger-aware crash interpretation remains future Doctor/Bisect work.

It should not currently be described as generally production-ready. Several
roadmap foundations are still incomplete, including profile-aware file
operations, broader reversible workflows beyond cleanup and loose update copy
actions, cache-clearing operations, safe archive update installation,
profile-aware Patch Day re-enable workflows, and broader real-world corpus
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

The read-only visual Inventory route is now present. Operating Table v1 now has
both the journaled backend action engine and a visual Cleanup route for
manifest-first staging, apply, restore, and status. The next cleanup work should
exercise the visual route against temp-tree fixtures and broaden reversible
operations only after the trust gate remains green.
