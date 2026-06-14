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

### Added
- Added the Phase 0 real-file corpus contract, `real`/`synthetic` pytest markers, committed package/script/save/tray/log fixtures, and a local-only corpus builder that copies explicitly chosen real fixtures into a git-ignored test root with golden sidecars.
- Added a conservative `Resource.cfg` parser and package load-order simulator that annotates resource conflicts with simulated winner, participant order, and confidence metadata.
- Added `docs/STATUS.md` and replaced stale generated root status reports with current Phase 0 status summaries while preserving older status/review/setup/spec snapshots under `docs/archive/status/`.
- Added a read-only SQLite inventory ledger plus bridge/Tauri/web API `inventory-scan`, `inventory-history`, and `inventory-file-events` plumbing that records scans, file identity, DBPF package parse status, resource keys, snapshots, event-log entries, changed-since-last-scan counts, scan history, per-file change events, and JSON-serializable snapshot exports.
- Added a read-only Mods cleanup planner plus bridge/Tauri/web API `cleanup-plan` plumbing that consumes the inventory database and emits review-only findings for exact duplicates, inactive archives, nested `Resource.cfg`, support files, and misplaced Tray files without moving Sims files.
- Added Operating Table v1 backend plumbing for manifest-first cleanup staging, apply, restore, and status commands, preserving explicit selection, Sims process guards, path/hash preflight, and restore-from-manifest behavior.

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
