# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
