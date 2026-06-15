# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Replaced fabricated Sims 4 resource type constants with a verified S4TK-backed registry.
- Changed package tuning extraction to scan all verified tuning resource classes and keep STBL binary string tables out of XML parsing.
- Corrected critical resource conflict types and names for SimData, Object Definitions, CAS Parts, and Object Catalogs.
- Updated DBPF parser/model fixtures and documentation examples so tests no longer validate against false resource IDs.
- Replaced stale hand-maintained requirements files with pyproject-backed install shims so unused packages are no longer advertised as runtime dependencies.
- Closed inventory and cleanup SQLite connections deterministically so Python 3.14/pytest no longer reports unraisable unclosed-database warnings.
- Replaced placeholder Dashboard space usage and hardcoded file-distribution estimates with values derived from the current mod scan payload.

### Added
- Added the Phase 0 real-file corpus contract, `real`/`synthetic` pytest markers, committed package/script/save/tray/log fixtures, and a local-only corpus builder that copies explicitly chosen real fixtures into a git-ignored test root with golden sidecars.
- Added a conservative `Resource.cfg` parser and package load-order simulator that annotates resource conflicts with simulated winner, participant order, and confidence metadata.
- Added a conservative read-only STBL v5 parser and scanner integration that extracts keyed UTF-8 strings from Sims 4 string tables with explicit parsed/unsupported/malformed status.
- Added a conservative read-only SimData metadata parser and scanner integration that extracts table, schema, and column metadata without claiming row/value decoding.
- Added compact parser/resource truth to mod analysis JSON across CLI reports, the desktop bridge, HTTP scan, and WebSocket scan responses, including resource type names, per-mod resource counts, STBL/SimData parse-status counts, parser warnings, and conflict details.
- Added `docs/STATUS.md` and replaced stale generated root status reports with current Phase 0 status summaries while preserving older status/review/setup/spec snapshots under `docs/archive/status/`.
- Added a read-only SQLite inventory ledger plus bridge/Tauri/web API `inventory-scan`, `inventory-history`, and `inventory-file-events` plumbing that records scans, file identity, DBPF package parse status, resource keys, snapshots, event-log entries, changed-since-last-scan counts, scan history, per-file change events, and JSON-serializable snapshot exports.
- Added the read-only `simanalysis ledger scan|history|events` CLI surface with text and JSON output over the same inventory ledger.
- Added a read-only Mods cleanup planner plus bridge/Tauri/web API `cleanup-plan` plumbing that consumes the inventory database and emits review-only findings for exact duplicates, inactive archives, nested `Resource.cfg`, support files, and misplaced Tray files without moving Sims files.
- Added Operating Table v1 backend plumbing for manifest-first cleanup staging, apply, restore, and status commands, preserving explicit selection, Sims process guards, path/hash preflight, and restore-from-manifest behavior.
- Added the manifest-first `simanalysis ops plan|commit|restore|undo` CLI surface; commits require explicit action IDs or `--all-actions` and still use Operating Table guards and manifests.
- Added the read-only `simanalysis doctor` CLI surface over the shared Doctor payload, combining script crash and UI exception autopsy with text and JSON output.
- Added evidence-labeled Doctor verdicts and symptom playbooks to the shared `simanalysis doctor` payload, including manifest-bisection and partial-evidence next-step guidance.
- Added the manifest-based `simanalysis bisect start|status|next|record-verdict|restore` CLI surface over the existing Treatment/Auto-Bisect engine.
- Added the read-only `simanalysis bisect handoff` CLI surface that renders a Markdown field handoff from a saved bisection manifest with session state, candidates, steps, warnings, blockers, and recovery commands.
- Added the read-only `simanalysis-bridge treatment-handoff` sidecar command plus Tauri argument support so the desktop layer can request the same Markdown bisection handoff from a saved manifest.
- Added a read-only desktop Inventory Ledger route over `inventory-scan`, `inventory-history`, and `inventory-file-events`, with scan summary tiles, filtered snapshot rows, recent scans, latest file events, and scan warnings.
- Added visual Cleanup Operating Table controls for exported cleanup plans, explicit action selection, manifest staging, status refresh, and confirm-gated apply/restore over the existing bridge commands.
- Added desktop Doctor verdict and playbook panels sourced from the shared Doctor payload, preserving existing crash/UI findings while exposing the recommended next-step contract.
- Added Doctor evidence preservation in saved bisection manifests plus a
  BuildBuy03B-style replay test proving Doctor JSON can start a session, journal
  a move, record a verdict, restore the tree, and render a rollback handoff with
  the original verdict/playbook context.
- Added a read-only Doctor timeline to JSON and text output, combining parsed
  script and UI exception evidence in deterministic chronological order.
- Added explicit read-only inventory ledger context to `simanalysis doctor`
  through `--inventory-db`, surfacing recent scan history and latest file
  events in JSON/text output without scanning or mutating files.
- Added `inventoryDb` plumbing for desktop Doctor scans through the web API,
  Tauri sidecar arguments, and `simanalysis-bridge doctor-scan --inventory-db`.
- Added desktop Doctor timeline and Inventory Ledger panels that render
  evidence already present in the shared Doctor payload without starting a new
  inventory scan or mutating Sims files.
- Added read-only Patch Day Shield v0 CLI commands,
  `simanalysis patch-day status|record`, which compare `GameVersion.txt`
  against an app-owned baseline state, label post-patch script/UI/gameplay/CAS
  risk classes as `unknown_after_patch`, and never automatically re-enable or
  move Sims files.
- Added desktop Patch Day Shield v0 plumbing and UI through
  `patch-day-status|record` bridge/Tauri commands and a Patch Day route for
  checking game-version baseline status, reviewing risk classes, and recording
  an explicit baseline without changing Mods, saves, or Tray files.
- Added Profile Manager Light v0 in desktop Settings, storing an active Sims 4
  root in app config, deriving Mods/Tray/saves/cache paths, remembering known
  profiles, and keeping the scope app-state-only with no Sims-folder mutation.
- Added profile-aware desktop input defaults for Mod Manager, Inventory,
  Cleanup, Doctor, Treatment, Live Monitor, Patch Day, Tray Organizer, and Save
  Analyzer without starting scans or changing Sims files on load.
- Added read-only Cache Doctor v0 CLI/backend through `simanalysis cache
  status`, reporting known cache targets and symlink warnings without deleting
  or moving files.
- Added desktop Cache Doctor v0 through `cache-status` bridge/Tauri plumbing,
  a Cache Doctor route, and profile-aware Sims 4 folder defaults over the same
  read-only cache status payload.
- Added read-only Save Protector v0 CLI/backend through `simanalysis
  save-protector status`, grouping save/backups and surfacing AppleDouble,
  iCloud-placeholder, symlink, and case-collision signals without editing saves.
- Added desktop Save Protector v0 through `save-protector-status` bridge/Tauri
  plumbing, a Save Protector route, and profile-aware Sims 4 folder defaults
  over the same read-only save status payload.
- Added read-only Tray Protector v0 CLI/backend through `simanalysis tray
  status`, grouping Tray files and surfacing sidecar-only, AppleDouble,
  iCloud-placeholder, symlink, and case-collision signals without editing Tray.
- Added desktop Tray Protector v0 through `tray-protector-status`
  bridge/Tauri plumbing, a Tray Protector route, and profile-aware Sims 4
  folder defaults over the same read-only Tray status payload.
- Added read-only Update Desk staging status through `simanalysis updates
  status`, classifying staged archives, packages, scripts, source sidecars,
  corrupt ZIPs, archive path-escape risks, iCloud placeholders, AppleDouble
  files, symlinks, and case collisions without extracting archives or changing
  Mods.
- Added desktop Update Desk v0 through `update-staging-status` bridge/Tauri
  plumbing, an Update Desk route, and a staging-folder review surface over the
  same read-only staged-download payload.
- Added read-only Update Desk install-plan generation through `simanalysis
  updates plan`, producing copy/review/blocker actions and optional manifest
  JSON without extracting archives, writing snapshots, or changing Mods.
- Added `update-staging-plan` bridge/Tauri plumbing for the same read-only
  install-plan payload, requiring an explicit Mods path and exposing no desktop
  apply/commit operation.
- Added desktop Update Desk install-plan preview with explicit Mods path input,
  snapshot/no-mutation gate labels, copy/archive/blocker action rows, and no
  install/apply control.
- Added manifest-backed Update Desk commit/undo backend and CLI commands
  through `simanalysis updates commit|undo`; commits require explicit action
  IDs or `--all-actions`, copy only loose staged `.package`/`.ts4script`
  actions that still match plan hash/size evidence, preserve staged downloads,
  and undo only installed files that still match manifest evidence.
- Added `update-staging-commit` and `update-staging-undo` bridge/Tauri
  argument plumbing plus web API option builders for the same guarded
  commit/undo contract, while the desktop Update Desk route still exposes no
  install/apply control.

### Planned
- Full DBPF package parser implementation
- XML tuning conflict detection
- TS4Script analysis
- Dependency mapping
- Performance profiling
- HTML report generation
- AI-powered suggestions (optional)

## [2.0.0] - TBD (In Development)

### Added
- Complete project restructure into proper Python package
- Comprehensive technical specification
- Modern build system with pyproject.toml
- CI/CD pipeline with GitHub Actions
- Pre-commit hooks for code quality
- Type checking with MyPy
- Linting with Ruff
- Testing infrastructure with pytest
- Documentation structure
- Development guidelines (CONTRIBUTING.md)
- Standalone application support via PyInstaller
- Web GUI integration for standalone executable
- `run_standalone.py` entry point for frozen applications
- `BUILD_INSTRUCTIONS.md` for creating standalone executables

### Changed
- Migrated from standalone script to package structure
- Updated Python version requirement to 3.9+
- Improved dependency management

### Removed
- Legacy standalone analyzer.py in favor of package structure

## [1.0.0] - 2025-10-20 (Initial Release)

### Added
- Initial project structure
- Basic ModAnalyzer class skeleton
- Data models (ModConflict, AnalysisResult)
- Codex integration configuration
- Claude Code prompt templates
- Basic README documentation

### Notes
- Initial proof of concept
- Core functionality not yet implemented
- Framework established for future development

---

## Version History Summary

| Version | Date | Status | Description |
|---------|------|--------|-------------|
| 2.0.0 | TBD | In Development | Full implementation |
| 1.0.0 | 2025-10-20 | Released | Initial structure |

---

## Migration Guides

### Upgrading from 1.0.0 to 2.0.0

**Breaking Changes:**
- Package structure changed from `src/analyzer.py` to `src/simanalysis/`
- Import statements need updating:
  ```python
  # Old (1.0.0)
  from analyzer import ModAnalyzer

  # New (2.0.0)
  from simanalysis import ModAnalyzer
  ```

**New Features:**
- CLI tool available via `simanalysis` command
- Multiple report formats (JSON, HTML, Markdown)
- Enhanced conflict detection algorithms
- Dependency mapping
- Performance profiling

**Installation Changes:**
```bash
# Old (1.0.0)
pip install -r requirements.txt

# New (2.0.0)
pip install simanalysis
# Or for development
pip install -e ".[dev]"
```

---

## Contribution Credits

### v2.0.0
- **Architecture & Specification:** SuperClaude AI
- **Vision & Direction:** justaride
- **Community Testing:** TBD

### v1.0.0
- **Initial Creation:** justaride

---

*For detailed commit history, see: https://github.com/justaride/Simanalysis/commits/main*
