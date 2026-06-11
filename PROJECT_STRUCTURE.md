# Simanalysis Project Structure Guide

This document explains the organization and purpose of each directory and file in the Simanalysis project.

## Quick Reference

```
Simanalysis/
├── 📁 .github/          CI/CD workflows
├── 📁 .codex/           Claude Code integration
├── 📁 src/              Source code
├── 📁 tests/            Test suite
├── 📁 docs/             Documentation
├── 📁 scripts/          Development utilities
└── 📄 Configuration files
```

---

## Root Directory Files

### Build & Package Configuration
| File | Purpose | Edit Frequency |
|------|---------|----------------|
| `pyproject.toml` | Main project configuration, dependencies, build settings | Often |
| `requirements.txt` | Runtime dependencies (auto-generated from pyproject.toml) | Rarely |
| `requirements-dev.txt` | Development dependencies | Sometimes |
| `setup.py` | Legacy setup file (if needed for compatibility) | Rarely |

### Code Quality
| File | Purpose | Edit Frequency |
|------|---------|----------------|
| `.pre-commit-config.yaml` | Pre-commit hook configuration | Rarely |
| `ruff.toml` | Ruff linter/formatter settings | Rarely |
| `mypy.ini` | MyPy type checker configuration | Rarely |
| `pytest.ini` | Pytest test runner configuration | Sometimes |

### Documentation
| File | Purpose | Edit Frequency |
|------|---------|----------------|
| `README.md` | Project overview and quick start | Often |
| `docs/archive/status/TECHNICAL_SPECIFICATION_2025-12-21.md` | Historical technical design snapshot | Rarely |
| `CONTRIBUTING.md` | Contribution guidelines | Rarely |
| `CHANGELOG.md` | Version history | Every release |
| `LICENSE` | MIT License | Never |

### Version Control
| File | Purpose | Edit Frequency |
|------|---------|----------------|
| `.gitignore` | Files to exclude from Git | Rarely |
| `.gitattributes` | Git attributes (line endings, etc.) | Rarely |

---

## Source Code (`src/simanalysis/`)

### Core Modules

```
src/simanalysis/
├── __init__.py              Package initialization, public API
├── __version__.py           Version metadata
├── cli.py                   Command-line interface (Click-based)
├── analyzer.py              Main analysis orchestrator
├── models.py                Data models and types
└── exceptions.py            Custom exceptions
```

**When to edit:**
- `__init__.py`: When adding new public exports
- `__version__.py`: Every release (version bump)
- `cli.py`: When adding CLI commands/options
- `analyzer.py`: Core logic changes
- `models.py`: Adding/modifying data structures

### Parsers (`src/simanalysis/parsers/`)

Low-level file format parsing.

```
parsers/
├── __init__.py              Parser exports
├── dbpf.py                  DBPF package format parser
├── tuning.py                XML tuning file parser
├── script.py                TS4Script (zip + Python) parser
├── resource.py              Resource type definitions
└── constants.py             Format constants and magic numbers
```

**Responsibilities:**
- Read binary/XML data
- Extract structured information
- Handle format variations
- Provide clean abstractions

**Dependencies:** Minimal (lxml for XML, stdlib for most)

### Detectors (`src/simanalysis/detectors/`)

Conflict detection algorithms.

```
detectors/
├── __init__.py              Detector exports
├── base.py                  Abstract base detector
├── tuning_conflicts.py      Tuning ID conflict detection
├── resource_conflicts.py    Resource key duplicate detection
├── script_conflicts.py      Python script injection conflicts
└── dependency_conflicts.py  Missing/circular dependencies
```

**Responsibilities:**
- Analyze parsed mod data
- Identify conflicts
- Calculate severity
- Generate recommendations

**Dependencies:** Parsers, Models

### Analyzers (`src/simanalysis/analyzers/`)

Higher-level analysis features.

```
analyzers/
├── __init__.py              Analyzer exports
├── dependencies.py          Dependency graph mapping
├── performance.py           Performance impact estimation
├── compatibility.py         Version/pack compatibility
└── statistics.py            Collection statistics
```

**Responsibilities:**
- Aggregate data across mods
- Build relationships (dependency graphs)
- Calculate metrics
- Provide insights

**Dependencies:** Parsers, Detectors, Models, NetworkX

### Reports (`src/simanalysis/reports/`)

Output generation in various formats.

```
reports/
├── __init__.py              Report exports
├── base.py                  Abstract report generator
├── json_report.py           JSON output
├── html_report.py           HTML report with styling
├── markdown_report.py       Markdown (GitHub-friendly)
└── templates/               Report templates
    ├── report.html          HTML template (Jinja2)
    ├── report.md            Markdown template
    └── styles.css           CSS for HTML reports
```

**Responsibilities:**
- Format analysis results
- Generate readable output
- Support multiple formats
- Templating

**Dependencies:** Jinja2, Models

### AI Integration (`src/simanalysis/ai/`) [Optional]

AI-powered analysis features.

```
ai/
├── __init__.py              AI exports
├── claude_analyzer.py       Claude API integration
├── prompts.py               AI prompt templates
└── cache.py                 Response caching
```

**Responsibilities:**
- Call Claude API
- Generate conflict resolution suggestions
- Enhance reports with AI insights
- Cache responses

**Dependencies:** Anthropic SDK, Models

**Note:** This module is optional and requires API key.

### Utilities (`src/simanalysis/utils/`)

Shared utility functions.

```
utils/
├── __init__.py              Utility exports
├── file_utils.py            File operations
├── hash_utils.py            Hashing functions
├── logger.py                Logging configuration
├── progress.py              Progress bars (Rich/tqdm)
└── validation.py            Input validation
```

**Responsibilities:**
- Common operations
- Logging setup
- Helper functions
- Validation logic

**Dependencies:** Various (Rich, tqdm, etc.)

---

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py              Pytest configuration and fixtures
│
├── unit/                    Unit tests (isolated)
│   ├── parsers/
│   │   ├── test_dbpf_parser.py
│   │   ├── test_tuning_parser.py
│   │   └── test_script_parser.py
│   ├── detectors/
│   │   ├── test_tuning_conflicts.py
│   │   ├── test_resource_conflicts.py
│   │   └── test_script_conflicts.py
│   ├── analyzers/
│   │   ├── test_dependencies.py
│   │   └── test_performance.py
│   └── reports/
│       ├── test_json_report.py
│       └── test_html_report.py
│
├── integration/             Integration tests (full workflows)
│   ├── test_full_analysis.py
│   ├── test_cli.py
│   └── test_real_mods.py    (requires actual mods)
│
└── fixtures/                Test data
    ├── sample_mods/         Sample mod files
    │   ├── simple.package
    │   ├── script.ts4script
    │   └── conflicting_a.package
    ├── mock_data/           Mock objects
    └── expected_outputs/    Expected results
```

**Test Organization:**
- **Unit tests:** Test individual functions/classes
- **Integration tests:** Test complete workflows
- **Fixtures:** Shared test data

**Coverage Goals:**
- Parsers: 95%+
- Detectors: 90%+
- Analyzers: 85%+
- Overall: 90%+

---

## Documentation (`docs/`)

```
docs/
├── index.md                 Documentation home
├── getting_started.md       Quick start guide
├── installation.md          Installation instructions
├── usage/
│   ├── basic_analysis.md    Basic usage
│   ├── advanced_usage.md    Advanced features
│   └── cli_reference.md     CLI command reference
├── api_reference/
│   ├── parsers.md           Parser API docs
│   ├── detectors.md         Detector API docs
│   ├── analyzers.md         Analyzer API docs
│   └── models.md            Data models
├── development/
│   ├── architecture.md      System architecture
│   ├── file_formats.md      DBPF/Tuning format specs
│   ├── conflict_types.md    Conflict detection guide
│   └── contributing.md      How to contribute
├── examples/
│   ├── basic_example.py     Simple usage example
│   ├── filtering.py         Advanced filtering
│   └── custom_reports.py    Custom report generation
└── mkdocs.yml               MkDocs configuration
```

**Documentation Types:**
- **User docs:** How to use Simanalysis
- **API docs:** Function/class references
- **Developer docs:** Architecture and internals
- **Examples:** Code samples

---

## Scripts (`scripts/`)

Development utility scripts.

```
scripts/
├── setup_dev.sh             Setup development environment
├── run_tests.sh             Run test suite
├── build_docs.sh            Build documentation
├── lint.sh                  Run linters
├── format.sh                Format code
├── release.sh               Prepare release
└── analyze_local_mods.py    Test with local Sims 4 mods
```

**Usage:**
```bash
# Setup development environment
./scripts/setup_dev.sh

# Run tests
./scripts/run_tests.sh

# Build docs
./scripts/build_docs.sh
```

---

## GitHub Workflows (`.github/workflows/`)

```
.github/
└── workflows/
    ├── tests.yml            Run tests on push/PR
    ├── release.yml          Publish to PyPI on release
    ├── docs.yml             Build and deploy docs
    └── security.yml         Security scanning
```

**Triggers:**
- `tests.yml`: Every push, every PR
- `release.yml`: When GitHub release is created
- `docs.yml`: Push to main, manual trigger
- `security.yml`: Weekly schedule

---

## Codex Integration (`.codex/`)

```
.codex/
├── config.json              Claude Code configuration
└── prompts.md               AI analysis prompts
```

**Purpose:** Configure Claude Code for AI-assisted development and analysis.

---

## File Naming Conventions

### Python Files
- **Modules:** `lowercase_with_underscores.py`
- **Classes:** `PascalCase` (in code)
- **Functions:** `lowercase_with_underscores`
- **Constants:** `UPPERCASE_WITH_UNDERSCORES`

### Test Files
- **Unit tests:** `test_<module>.py`
- **Integration tests:** `test_<feature>.py`
- **Fixtures:** Descriptive names

### Documentation
- **User docs:** `lowercase_with_underscores.md`
- **Technical docs:** `UPPERCASE.md` (README, CONTRIBUTING, etc.)

---

## Directory Creation Order (for new development)

1. **Core modules first:**
   ```bash
   src/simanalysis/parsers/
   src/simanalysis/models.py
   ```

2. **Add detectors:**
   ```bash
   src/simanalysis/detectors/
   ```

3. **Add analyzers:**
   ```bash
   src/simanalysis/analyzers/
   ```

4. **Add reports:**
   ```bash
   src/simanalysis/reports/
   ```

5. **Add CLI:**
   ```bash
   src/simanalysis/cli.py
   ```

6. **Add tests alongside:**
   ```bash
   tests/unit/parsers/
   tests/unit/detectors/
   # etc.
   ```

---

## Import Structure

**Preferred import hierarchy:**

```python
# Standard library
import os
from pathlib import Path
from typing import List, Dict

# Third-party
import click
from rich.console import Console
from lxml import etree

# Local - absolute imports
from simanalysis.models import Mod, ModConflict
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.detectors.base import ConflictDetector

# Avoid relative imports in general
# OK in tests: from ..models import Mod
```

---

## Build Artifacts (Generated)

These directories are created during build/test and should be in `.gitignore`:

```
__pycache__/                 Python bytecode
*.pyc                        Compiled Python
.pytest_cache/               Pytest cache
.mypy_cache/                 MyPy cache
.ruff_cache/                 Ruff cache
.coverage                    Coverage data
htmlcov/                     Coverage HTML report
dist/                        Built packages
build/                       Build artifacts
*.egg-info/                  Package metadata
.eggs/                       Eggs directory
```

---

## Quick Navigation

**Need to...**
- Add a new parser? → `src/simanalysis/parsers/`
- Add a conflict detector? → `src/simanalysis/detectors/`
- Add a CLI command? → `src/simanalysis/cli.py`
- Write tests? → `tests/unit/` or `tests/integration/`
- Update docs? → `docs/`
- Configure CI? → `.github/workflows/`
- Add dependencies? → `pyproject.toml`

---

*This structure is designed for maintainability, testability, and scalability as the project grows.*
