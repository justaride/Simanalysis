# CLAUDE.md - AI Assistant Guide for Simanalysis

**Last Updated:** 2025-11-22
**Project Version:** 2.0.0
**Status:** Production-Ready

---

## 🎯 Project Overview

**Simanalysis** (aka "Derrick - The PhD in Simology") is a professional-grade static analysis tool for The Sims 4 mods. It performs **proactive conflict detection** before game launch, analyzing `.package` and `.ts4script` files to identify tuning conflicts, resource duplicates, script injection conflicts, and dependency issues.

### Key Characteristics
- **Language:** Python 3.9+ (supports 3.9-3.12)
- **License:** MIT
- **Lines of Code:** ~2,602 (core), ~205 tests
- **Test Coverage:** 55-94% by module (94% on models.py)
- **Maturity:** Production-ready, v2.0.0 released
- **Architecture:** Modular pipeline (parsers → detectors → analyzers → reports)

### Project Philosophy
- **Quality over features:** Strict type checking, comprehensive testing, linting
- **User-friendly:** Multiple UIs (CLI, Rich TUI, Textual interactive)
- **Extensible:** Abstract base classes, plugin-ready architecture
- **Well-documented:** Extensive inline docs, external documentation

---

## 📁 Codebase Structure

### Directory Layout
```
Simanalysis/
├── src/simanalysis/              # Main source code
│   ├── __init__.py               # Public API exports
│   ├── __version__.py            # Version metadata
│   ├── cli.py                    # Click CLI (462 lines)
│   ├── tui.py                    # Rich TUI (485 lines)
│   ├── interactive_tui.py        # Textual app (532 lines)
│   ├── models.py                 # Data models (268 lines, 94% coverage)
│   ├── exceptions.py             # Exception hierarchy (49 lines)
│   │
│   ├── parsers/                  # File format parsers
│   │   ├── dbpf.py              # DBPF binary parser (303 lines)
│   │   ├── tuning.py            # XML tuning parser (307 lines)
│   │   └── script.py            # Python AST analyzer (374 lines)
│   │
│   ├── detectors/               # Conflict detection
│   │   ├── base.py              # Abstract detector (298 lines)
│   │   ├── tuning_conflicts.py  # Tuning ID conflicts (228 lines)
│   │   └── resource_conflicts.py # Resource duplicates (303 lines)
│   │
│   ├── analyzers/               # Analysis pipeline
│   │   └── mod_analyzer.py      # Main orchestrator (425 lines)
│   │
│   ├── scanners/                # Directory scanning
│   │   └── mod_scanner.py       # Recursive mod finder (340 lines)
│   │
│   ├── ai/                      # AI integration (placeholder)
│   │   └── __init__.py
│   │
│   └── utils/                   # Utilities (placeholder)
│       └── __init__.py
│
├── tests/                       # Test suite (205 tests)
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/                    # Unit tests
│   │   ├── parsers/
│   │   ├── detectors/
│   │   ├── analyzers/
│   │   └── scanners/
│   ├── integration/             # Integration tests
│   ├── performance/             # Benchmarks
│   └── fixtures/                # Test data
│       └── sample_mods/
│
├── docs/                        # Documentation
│   └── DBPF_FORMAT.md          # DBPF file format spec
│
├── .github/workflows/           # CI/CD
│   ├── tests.yml               # Multi-platform testing
│   └── release.yml             # Release automation
│
├── .codex/                      # Claude Code integration
│   ├── config.json
│   └── prompts.md
│
├── pyproject.toml               # Main configuration (all tools)
├── pytest.ini                   # Pytest configuration
├── .pre-commit-config.yaml      # Git hooks
├── .gitignore
│
└── Documentation files          # Extensive project docs
    ├── README.md
    ├── TECHNICAL_SPECIFICATION.md
    ├── CONTRIBUTING.md
    ├── IMPLEMENTATION_STATUS.md
    ├── IMPLEMENTATION_ROADMAP.md
    ├── REQUIREMENTS_VERIFICATION.md
    └── ... (14 total documentation files)
```

---

## 🏗️ Architecture

### Pipeline Flow
```
User Input (CLI/TUI)
    ↓
ModScanner (scanners/mod_scanner.py)
  - Recursive directory traversal
  - File discovery (.package, .ts4script)
  - SHA256 hash calculation
    ↓
Parsers (parsers/)
  - DBPFReader: Binary DBPF format
  - TuningParser: XML tuning files
  - ScriptAnalyzer: Python AST analysis
    ↓
Detectors (detectors/)
  - TuningConflictDetector
  - ResourceConflictDetector
  - (Future: ScriptConflictDetector, DependencyDetector)
    ↓
ModAnalyzer (analyzers/mod_analyzer.py)
  - Orchestrates pipeline
  - Aggregates results
  - Calculates performance metrics
  - Generates recommendations
    ↓
Report Generation
  - Text format
  - JSON format
  - (Future: HTML, Markdown)
    ↓
Output (Console/File)
```

### Key Design Patterns

**Abstract Base Classes:**
- `ConflictDetector` (detectors/base.py) - All detectors inherit from this
- Enforces `detect()` method interface
- Provides severity calculation utilities

**Dataclasses:**
- All models in `models.py` use `@dataclass`
- Type hints on all fields
- Immutable where possible (no setters)

**Exception Hierarchy:**
```
SimanalysisError (base)
├── ParsingError
│   ├── DBPFError
│   ├── TuningError
│   └── ScriptError
├── ConflictDetectionError
├── AnalysisError
└── ReportGenerationError
```

**Public API:**
```python
from simanalysis import ModAnalyzer
from simanalysis.analyzers import ModAnalyzer  # Alternative

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("~/Mods"))
```

---

## 🔧 Development Workflows

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Verify setup
pytest
ruff check src/
mypy src/simanalysis
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=simanalysis --cov-report=html

# Run specific test file
pytest tests/unit/parsers/test_dbpf_parser.py

# Run specific test class
pytest tests/unit/test_models.py::TestDBPFHeader

# Run tests matching pattern
pytest -k "test_conflict"

# Run only fast tests (skip @pytest.mark.slow)
pytest -m "not slow"

# Run in parallel (requires pytest-xdist)
pytest -n auto

# Run with verbose output
pytest -v

# Run and show local variables on failure
pytest --showlocals
```

### Code Quality Checks

```bash
# Lint code (check for issues)
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Type checking
mypy src/simanalysis

# Run all pre-commit hooks
pre-commit run --all-files

# Security scanning (included in pre-commit)
bandit -r src/simanalysis
```

### Running the CLI

```bash
# Basic analysis
simanalysis analyze ~/Mods

# Interactive mode (recommended)
simanalysis analyze ~/Mods --interactive

# Rich TUI mode
simanalysis analyze ~/Mods --tui

# Export to JSON
simanalysis analyze ~/Mods --output report.json --format json

# Quick scan (no hashing)
simanalysis analyze ~/Mods --quick

# Verbose output
simanalysis analyze ~/Mods --verbose

# Quick directory scan (no conflict detection)
simanalysis scan ~/Mods

# View saved report
simanalysis view report.json

# Show program info
simanalysis info
```

---

## 📝 Code Conventions

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Classes | PascalCase | `ModAnalyzer`, `DBPFReader`, `TuningConflictDetector` |
| Functions/Methods | snake_case | `analyze_directory()`, `detect_conflicts()` |
| Constants | UPPER_SNAKE_CASE | `HEADER_SIZE`, `CRITICAL_RESOURCE_TYPES` |
| Private methods | _snake_case | `_build_tuning_index()`, `_calculate_hash()` |
| Module files | snake_case | `mod_analyzer.py`, `dbpf.py` |
| Test files | test_*.py | `test_dbpf_parser.py` |

### Import Structure

**Always follow this order:**
```python
# 1. Standard library
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

# 2. Third-party libraries
import click
from lxml import etree
from rich.console import Console

# 3. Local imports (absolute, not relative)
from simanalysis import __version__
from simanalysis.models import Mod, ModConflict, Severity
from simanalysis.exceptions import SimanalysisError, DBPFError
from simanalysis.parsers.dbpf import DBPFReader
```

**Avoid relative imports** except in tests:
```python
# ✅ Good (absolute)
from simanalysis.models import Mod

# ❌ Bad (relative - avoid in src/)
from ..models import Mod

# ✅ OK in tests
from ..models import Mod
```

### Type Hints

**All public functions MUST have type hints:**
```python
# ✅ Good
def analyze_directory(
    self,
    directory: Path,
    recursive: bool = True,
    extensions: Optional[Set[str]] = None,
) -> AnalysisResult:
    """Analyze all mods in a directory."""
    ...

# ❌ Bad (no type hints - will fail MyPy)
def analyze_directory(self, directory, recursive=True, extensions=None):
    ...
```

**Use proper type hints for collections:**
```python
from typing import Dict, List, Optional, Set

# ✅ Good
mods: List[Mod] = []
conflicts: Dict[str, ModConflict] = {}
resource_types: Set[int] = set()
version: Optional[str] = None

# ❌ Bad (no type hints)
mods = []
conflicts = {}
```

### Docstring Style

**Use Google-style docstrings:**
```python
def parse_tuning_file(xml_data: bytes) -> TuningData:
    """
    Parse XML tuning file data.

    Args:
        xml_data: Raw XML data as bytes

    Returns:
        TuningData object containing parsed information

    Raises:
        TuningError: If XML is invalid or missing required fields

    Example:
        >>> with open("tuning.xml", "rb") as f:
        ...     data = parse_tuning_file(f.read())
        >>> print(data.instance_id)
        12345678
    """
    ...
```

**Required sections:**
- Brief description (one line)
- `Args:` - All parameters
- `Returns:` - Return value description
- `Raises:` - Possible exceptions
- `Example:` - Usage example (optional but encouraged)

### Code Style Rules

**Configuration (pyproject.toml):**
- Line length: **100 characters max**
- Indentation: **4 spaces** (no tabs)
- Quotes: **Double quotes** (`"`) - enforced by Ruff
- Formatter: **Ruff** (Black-compatible)

**Common patterns:**
```python
# ✅ Good - descriptive variable names
for mod_conflict in detected_conflicts:
    severity = conflict.severity

# ❌ Bad - cryptic names
for c in dc:
    s = c.sev

# ✅ Good - early return
def validate_header(header: DBPFHeader) -> bool:
    if header.magic != b"DBPF":
        return False
    if header.major_version != 2:
        return False
    return True

# ✅ Good - list comprehension for simple filtering
critical_conflicts = [c for c in conflicts if c.severity == Severity.CRITICAL]

# ✅ Good - explicit None check
if value is None:
    return default

# ❌ Bad - truthy check on possibly-empty
if not value:  # Could be None, 0, [], "", False
    return default
```

---

## 🧪 Testing Patterns

### Test Organization

Tests mirror the source structure:
```
tests/unit/parsers/test_dbpf_parser.py
→ tests src/simanalysis/parsers/dbpf.py

tests/unit/detectors/test_tuning_conflicts.py
→ tests src/simanalysis/detectors/tuning_conflicts.py
```

### Test Fixtures (conftest.py)

**Available fixtures:**
```python
@pytest.fixture
def fixtures_dir() -> Path:
    """Path to test fixtures directory."""

@pytest.fixture
def sample_mods_dir(fixtures_dir: Path) -> Path:
    """Path to sample mods."""

@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Temporary directory for test outputs."""
```

**Real fixture files:**
- `tests/fixtures/sample_mods/simple_mod.package`
- `tests/fixtures/sample_mods/large_mod.package`
- `tests/fixtures/sample_mods/conflicting_mod_a.package`
- `tests/fixtures/sample_mods/conflicting_mod_b.package`
- `tests/fixtures/sample_mods/script_mod.ts4script`

### Test Markers

**Available markers (pytest.ini):**
```python
@pytest.mark.slow          # Long-running tests
@pytest.mark.integration   # Integration tests
@pytest.mark.requires_mods # Needs real mod files
@pytest.mark.unit          # Unit tests (default)
@pytest.mark.parser        # Parser module tests
@pytest.mark.detector      # Detector module tests
@pytest.mark.analyzer      # Analyzer module tests
@pytest.mark.benchmark     # Performance tests
```

**Usage:**
```python
@pytest.mark.slow
def test_analyze_1000_mods():
    """Test analyzing large mod collection."""
    ...

@pytest.mark.requires_mods
def test_with_real_mods(sample_mods_dir: Path):
    """Test with actual Sims 4 mod files."""
    ...
```

### Test Naming Patterns

**Class-based tests:**
```python
class TestDBPFHeader:
    """Tests for DBPFHeader model."""

    def test_valid_header(self) -> None:
        """Test creating valid DBPF header."""
        ...

    def test_invalid_magic(self) -> None:
        """Test magic validation."""
        ...

    def test_invalid_version(self) -> None:
        """Test version validation."""
        ...
```

**Function-based tests:**
```python
def test_dbpf_reader_parses_valid_header() -> None:
    """Test that DBPFReader correctly parses a valid DBPF header."""
    ...

def test_dbpf_reader_raises_on_invalid_magic() -> None:
    """Test that DBPFReader raises DBPFError on invalid magic."""
    ...
```

### Test Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| models.py | 95%+ | 94% ✅ |
| Parsers | 80%+ | 11-60% ⚠️ |
| Detectors | 75%+ | 39-80% ⚠️ |
| Analyzers | 70%+ | 71% ✅ |
| Overall | 75%+ | ~60% ⚠️ |

**Note:** Some modules (tuning.py, script.py) have low coverage due to complex parsing logic requiring more test fixtures.

---

## 🎨 Key Patterns & Best Practices

### Error Handling

**Always use specific exceptions:**
```python
# ✅ Good
from simanalysis.exceptions import DBPFError

if header.magic != b"DBPF":
    raise DBPFError(f"Invalid DBPF magic: {header.magic}")

# ❌ Bad (generic exception)
if header.magic != b"DBPF":
    raise ValueError("Invalid magic")
```

**Catch specific exceptions:**
```python
# ✅ Good
try:
    data = parse_tuning_file(xml_data)
except TuningError as e:
    logger.error(f"Failed to parse tuning: {e}")
    return None

# ❌ Bad (catch-all)
try:
    data = parse_tuning_file(xml_data)
except Exception as e:  # Too broad
    return None
```

### Logging Patterns

**Current implementation uses print statements** (to be replaced with proper logging):
```python
# Current pattern (temporary)
if self.verbose:
    print(f"Analyzing {mod.name}...")

# Future pattern (planned)
logger.info(f"Analyzing {mod.name}")
logger.debug(f"Found {len(resources)} resources")
logger.warning(f"Skipping invalid mod: {path}")
logger.error(f"Failed to parse {path}: {e}")
```

### Resource Management

**Use context managers:**
```python
# ✅ Good
def read_package(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()

# ✅ Good - pathlib
def read_package(path: Path) -> bytes:
    return path.read_bytes()

# ❌ Bad (no auto-close)
def read_package(path: Path) -> bytes:
    f = open(path, "rb")
    return f.read()  # File never closed
```

### Performance Patterns

**Use generators for large datasets:**
```python
# ✅ Good - memory efficient
def find_conflicts(mods: List[Mod]) -> Generator[ModConflict, None, None]:
    for mod_a, mod_b in combinations(mods, 2):
        if has_conflict(mod_a, mod_b):
            yield create_conflict(mod_a, mod_b)

# ⚠️ OK for small datasets
def find_conflicts(mods: List[Mod]) -> List[ModConflict]:
    conflicts = []
    for mod_a, mod_b in combinations(mods, 2):
        if has_conflict(mod_a, mod_b):
            conflicts.append(create_conflict(mod_a, mod_b))
    return conflicts
```

**Use list comprehensions for filtering:**
```python
# ✅ Good - Pythonic
critical = [c for c in conflicts if c.severity == Severity.CRITICAL]

# ✅ Also good - explicit
critical = []
for conflict in conflicts:
    if conflict.severity == Severity.CRITICAL:
        critical.append(conflict)

# ⚠️ Use filter() only if already have predicate function
critical = list(filter(lambda c: c.severity == Severity.CRITICAL, conflicts))
```

---

## 🚀 Common Tasks

### Adding a New Conflict Detector

**1. Create detector file:**
```python
# src/simanalysis/detectors/my_detector.py
from typing import List
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict, Severity, ConflictType

class MyConflictDetector(ConflictDetector):
    """Detects my specific type of conflicts."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Detect conflicts in mod collection.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        conflicts = []
        # Your detection logic here
        return conflicts
```

**2. Add to detectors/__init__.py:**
```python
from simanalysis.detectors.my_detector import MyConflictDetector

__all__ = [..., "MyConflictDetector"]
```

**3. Integrate into analyzer:**
```python
# In analyzers/mod_analyzer.py
from simanalysis.detectors.my_detector import MyConflictDetector

# In analyze() method:
my_detector = MyConflictDetector()
my_conflicts = my_detector.detect(mods)
all_conflicts.extend(my_conflicts)
```

**4. Write tests:**
```python
# tests/unit/detectors/test_my_detector.py
import pytest
from simanalysis.detectors.my_detector import MyConflictDetector
from simanalysis.models import Mod

class TestMyConflictDetector:
    def test_detects_my_conflict(self):
        """Test that detector finds my conflict type."""
        detector = MyConflictDetector()
        mods = [...]  # Create test mods
        conflicts = detector.detect(mods)
        assert len(conflicts) == 1
```

### Adding a New Parser

**1. Create parser file:**
```python
# src/simanalysis/parsers/my_format.py
from pathlib import Path
from typing import Optional
from simanalysis.exceptions import ParsingError

class MyFormatParser:
    """Parser for my custom format."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def parse(self) -> MyData:
        """
        Parse the file.

        Returns:
            Parsed data object

        Raises:
            ParsingError: If file cannot be parsed
        """
        try:
            data = self.file_path.read_bytes()
            return self._parse_data(data)
        except Exception as e:
            raise ParsingError(f"Failed to parse {self.file_path}: {e}") from e
```

**2. Add to parsers/__init__.py and models.py (if needed)**

**3. Write comprehensive tests**

### Adding a New CLI Command

**1. Add command to cli.py:**
```python
@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--option", help="My option")
def mycommand(path: str, option: Optional[str]) -> None:
    """
    My new command description.

    Example:
        simanalysis mycommand /path/to/mods --option value
    """
    console.print(f"Running mycommand on {path}")
    # Your logic here
```

**2. Test the command:**
```python
# tests/unit/test_cli.py
from click.testing import CliRunner
from simanalysis.cli import cli

def test_mycommand():
    """Test mycommand CLI."""
    runner = CliRunner()
    result = runner.invoke(cli, ["mycommand", "/tmp"])
    assert result.exit_code == 0
```

### Adding a New Model

**1. Add to models.py:**
```python
@dataclass
class MyModel:
    """My new model."""

    field1: str
    field2: int
    optional_field: Optional[str] = None
    list_field: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate after initialization."""
        if self.field2 < 0:
            raise ValueError("field2 must be non-negative")
```

**2. Export from __init__.py:**
```python
from simanalysis.models import MyModel

__all__ = [..., "MyModel"]
```

**3. Add tests:**
```python
# tests/unit/test_models.py
class TestMyModel:
    def test_valid_model(self):
        """Test creating valid MyModel."""
        model = MyModel(field1="test", field2=42)
        assert model.field1 == "test"

    def test_validation(self):
        """Test validation in __post_init__."""
        with pytest.raises(ValueError):
            MyModel(field1="test", field2=-1)
```

---

## 📚 Important Files Reference

### Critical Configuration Files

| File | Purpose | Edit Frequency |
|------|---------|----------------|
| `pyproject.toml` | All tool configuration, dependencies, metadata | Often |
| `pytest.ini` | Pytest configuration (mostly duplicates pyproject.toml) | Rarely |
| `.pre-commit-config.yaml` | Git hooks (Ruff, MyPy, Bandit) | Rarely |
| `.github/workflows/tests.yml` | CI/CD pipeline | Rarely |

### Core Source Files

| File | Lines | Coverage | Purpose |
|------|-------|----------|---------|
| `models.py` | 268 | 94% | All data models and enums |
| `exceptions.py` | 49 | - | Exception hierarchy |
| `cli.py` | 462 | 72% | Click CLI interface |
| `mod_analyzer.py` | 425 | 71% | Main orchestrator |
| `dbpf.py` | 303 | 60% | DBPF binary parser |
| `tuning.py` | 307 | 11% | XML tuning parser |
| `script.py` | 374 | 9% | Python script analyzer |

### Documentation Files

**User Documentation:**
- `README.md` - Project overview, quickstart, features
- `CONTRIBUTING.md` - Contribution guidelines
- `CHANGELOG.md` - Version history

**Technical Documentation:**
- `TECHNICAL_SPECIFICATION.md` - Complete architecture spec (900+ lines)
- `PROJECT_STRUCTURE.md` - Directory organization guide
- `IMPLEMENTATION_STATUS.md` - Current implementation state
- `IMPLEMENTATION_ROADMAP.md` - Future plans
- `REQUIREMENTS_VERIFICATION.md` - Requirements verification

**Developer Documentation:**
- `DBPF_IMPLEMENTATION_STATUS.md` - DBPF parser details
- `CODE_REVIEW_RESPONSE.md` - Code review history
- `docs/DBPF_FORMAT.md` - DBPF file format specification

---

## 🔍 Understanding Key Modules

### models.py - Data Models

**All models are in one file (268 lines):**

**Enums:**
- `ModType`: PACKAGE, SCRIPT, HYBRID, UNKNOWN
- `Severity`: CRITICAL, HIGH, MEDIUM, LOW
- `ConflictType`: TUNING_OVERLAP, RESOURCE_DUPLICATE, SCRIPT_INJECTION, etc.

**Binary Format Models:**
- `DBPFHeader`: 96-byte DBPF header
- `DBPFResource`: Resource index entry

**Parsed Data Models:**
- `TuningData`: Parsed XML tuning
- `ScriptMetadata`: Script mod metadata
- `ScriptModule`: Individual Python module

**Core Models:**
- `Mod`: Main mod representation (resources, tunings, scripts)
- `ModConflict`: Detected conflict
- `PerformanceMetrics`: Load time, memory, complexity
- `AnalysisMetadata`: Analysis run metadata
- `AnalysisResult`: Complete analysis results

### parsers/dbpf.py - DBPF Parser

**Purpose:** Parse The Sims 4 `.package` files (DBPF 2.0 format)

**Key Constants:**
```python
HEADER_SIZE = 96  # bytes
MAGIC_BYTES = b"DBPF"
MAJOR_VERSION = 2
MINOR_VERSION = 0
INDEX_ENTRY_SIZE = 32  # bytes

# Resource types
RESOURCE_TYPE_XML_TUNING = 0x545238C9
RESOURCE_TYPE_SIMDATA = 0x0333406C
RESOURCE_TYPE_SCRIPT = 0xD382BF57
```

**Main Class:**
```python
class DBPFReader:
    def __init__(self, package_path: Path)
    def read_header(self) -> DBPFHeader
    def read_index(self) -> List[DBPFResource]
    def get_resource_data(self, resource: DBPFResource) -> bytes
    def get_all_resources(self) -> List[DBPFResource]
```

### detectors/base.py - Detector Framework

**Abstract base class for all detectors:**

```python
class ConflictDetector(ABC):
    @abstractmethod
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """Detect conflicts in mod collection."""

    def _is_core_tuning(self, instance_id: int) -> bool:
        """Check if tuning is a core game tuning."""

    def _is_high_risk_hook(self, hook_name: str) -> bool:
        """Check if hook point is high risk."""

    def _calculate_severity(self, conflict_data: Dict) -> Severity:
        """Calculate conflict severity."""
```

**Severity Calculation:**
- CRITICAL: Core tunings, script namespace collisions, game-breaking
- HIGH: Important resources, high-risk hooks, likely broken
- MEDIUM: Non-core conflicts, soft dependencies
- LOW: Cosmetic, informational

### analyzers/mod_analyzer.py - Main Orchestrator

**Core analysis flow:**

```python
class ModAnalyzer:
    def analyze_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[Set[str]] = None,
    ) -> AnalysisResult:
        """
        Complete analysis workflow:
        1. Scan directory for mods
        2. Parse each mod (DBPF, tunings, scripts)
        3. Run conflict detectors
        4. Calculate performance metrics
        5. Generate recommendations
        6. Package results
        """
```

---

## 🎯 Git Workflow for AI Assistants

### Current Branch Strategy

**You are working on:**
```
Branch: claude/claude-md-mia0u4hf6nrph0eh-01KqDHUuYhhjgqVSMzUdR77R
Status: Clean (no uncommitted changes)
```

### Commit Message Format

**Use conventional commits:**
```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting changes (no code change)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding/updating tests
- `chore`: Build/tooling changes

**Examples:**
```
feat(parser): add support for compressed DBPF resources

fix(detector): correct tuning conflict severity calculation

docs(readme): add installation instructions for Windows

test(parsers): add comprehensive DBPF parser tests
```

### Making Commits

**Before committing:**
1. ✅ All tests pass: `pytest`
2. ✅ Code is formatted: `ruff format .`
3. ✅ No linting errors: `ruff check .`
4. ✅ Type checking passes: `mypy src/simanalysis`
5. ✅ Pre-commit hooks pass: `pre-commit run --all-files`

**Commit workflow:**
```bash
# Stage changes
git add <files>

# Run pre-commit hooks manually (optional, runs on commit anyway)
pre-commit run --all-files

# Commit with conventional message
git commit -m "feat(detector): add script injection detector"

# Push to branch
git push -u origin claude/claude-md-mia0u4hf6nrph0eh-01KqDHUuYhhjgqVSMzUdR77R
```

### Creating Pull Requests

**PR title format:**
```
feat: Add script injection conflict detector
fix: Correct DBPF header parsing for compressed resources
```

**PR description template:**
```markdown
## Summary
Brief description of changes

## Changes
- List of specific changes
- Another change

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manually tested

## Related Issues
Fixes #123

## Checklist
- [ ] Tests pass
- [ ] Code is formatted (Ruff)
- [ ] Type checking passes (MyPy)
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if needed)
```

---

## 💡 Tips for AI Assistants

### Understanding the Codebase

**Start here:**
1. Read `README.md` for project overview
2. Read `TECHNICAL_SPECIFICATION.md` for architecture
3. Examine `models.py` for data structures
4. Review `exceptions.py` for error handling
5. Check `pyproject.toml` for configuration

**When adding features:**
1. Check if similar feature exists
2. Follow existing patterns (see detectors/ for examples)
3. Add tests BEFORE implementation (TDD encouraged)
4. Update documentation
5. Run full test suite

### Common Pitfalls to Avoid

**❌ Don't:**
- Use relative imports in src/ (use absolute: `from simanalysis.models import ...`)
- Forget type hints on public functions (MyPy will fail)
- Use generic exceptions (use specific: `DBPFError`, `TuningError`, etc.)
- Commit without running tests
- Skip docstrings on public functions
- Use tabs (4 spaces only)
- Exceed 100 character line length
- Use single quotes (use double quotes)

**✅ Do:**
- Follow existing code patterns
- Write comprehensive tests (aim for 80%+ coverage on new code)
- Use descriptive variable names
- Add docstrings with Args/Returns/Raises
- Run pre-commit hooks before committing
- Keep functions focused (single responsibility)
- Use type hints everywhere
- Handle errors gracefully

### Performance Considerations

**This project analyzes large mod collections (500+ files):**

1. **Use generators** for large datasets
2. **Avoid loading entire files** into memory if possible
3. **Cache parsed results** when appropriate
4. **Profile before optimizing** (don't guess)
5. **Use binary mode** for file operations (faster)

**Example - memory-efficient scanning:**
```python
# ✅ Good - process files one at a time
def scan_directory(path: Path) -> Generator[Mod, None, None]:
    for file in path.glob("**/*.package"):
        yield parse_mod(file)

# ❌ Bad - loads all into memory
def scan_directory(path: Path) -> List[Mod]:
    files = list(path.glob("**/*.package"))
    return [parse_mod(f) for f in files]
```

### Testing Strategy

**For new features:**
1. **Unit tests**: Test individual functions/methods
2. **Integration tests**: Test complete workflows
3. **Fixtures**: Use `tests/fixtures/sample_mods/` for test data
4. **Markers**: Use `@pytest.mark.slow` for long tests

**Coverage expectations:**
- New parsers: 80%+ coverage
- New detectors: 75%+ coverage
- New models: 90%+ coverage
- Bug fixes: Add regression test

### Documentation Requirements

**Always update when changing:**
- Public API: Update docstrings
- Configuration: Update pyproject.toml comments
- Features: Update README.md
- Breaking changes: Update CHANGELOG.md
- Architecture: Update TECHNICAL_SPECIFICATION.md (if major)

### Working with External Dependencies

**Current dependencies (from pyproject.toml):**
```python
click>=8.1.0          # CLI framework
rich>=13.0.0          # Terminal UI
textual>=0.47.0       # Interactive TUI
lxml>=4.9.0           # XML parsing
pyyaml>=6.0           # YAML support
tqdm>=4.65.0          # Progress bars
networkx>=3.0         # Dependency graphs
jinja2>=3.1.0         # Templates
```

**Adding new dependencies:**
1. Check if really needed (stdlib first)
2. Add to `pyproject.toml` dependencies
3. Update `requirements.txt`: `pip-compile pyproject.toml`
4. Document why it's needed
5. Check license compatibility (MIT-compatible)

---

## 🚨 Known Issues & Limitations

### Test Coverage Gaps

**Low coverage modules:**
- `tuning.py`: 11% (complex XML parsing, needs more fixtures)
- `script.py`: 9% (complex AST analysis, needs more fixtures)
- `tui.py`: 0% (visual component, manual testing)
- `interactive_tui.py`: 0% (visual component, manual testing)

**Action needed:** Create more comprehensive test fixtures in `tests/fixtures/`

### Placeholder Modules

**Not yet implemented:**
- `ai/` - AI integration (reserved for Claude API)
- `utils/` - General utilities (reserved)
- HTML report generation (planned)
- Markdown report generation (planned)
- Dependency graph visualization (planned)

### Future Enhancements

**From IMPLEMENTATION_ROADMAP.md:**
- Web dashboard UI
- Automatic conflict resolution suggestions
- Mod compatibility database
- Integration with mod managers
- Support for older DBPF versions (Sims 2/3)

---

## 📞 Getting Help

### Documentation Resources

**In this repository:**
- `TECHNICAL_SPECIFICATION.md` - Complete architecture (900 lines)
- `docs/DBPF_FORMAT.md` - DBPF binary format spec
- `CONTRIBUTING.md` - Contribution guidelines
- `README.md` - User guide

**External Resources:**
- [Sims 4 Studio](https://sims4studio.com/) - Mod creation tool
- [Sims 4 Modding Wiki](https://sims-4-modding.fandom.com/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Pytest Documentation](https://docs.pytest.org/)

### Issue Reporting

**For bugs or feature requests:**
1. Check existing issues: https://github.com/justaride/Simanalysis/issues
2. Search closed issues for duplicates
3. Create new issue with template:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - System info (OS, Python version)
   - Sample files (if safe to share)

---

## 🎓 Learning the Codebase

### Recommended Reading Order

**Day 1: Project Overview**
1. `README.md` - Understand what the project does
2. `pyproject.toml` - See dependencies and configuration
3. `models.py` - Learn data structures
4. Run `simanalysis --help` - See CLI in action

**Day 2: Architecture**
1. `TECHNICAL_SPECIFICATION.md` - Complete architecture
2. `PROJECT_STRUCTURE.md` - File organization
3. `analyzers/mod_analyzer.py` - Main orchestration flow
4. Run tests: `pytest -v`

**Day 3: Core Modules**
1. `parsers/dbpf.py` - Binary parsing
2. `docs/DBPF_FORMAT.md` - DBPF format spec
3. `detectors/base.py` - Detector framework
4. `tests/unit/parsers/test_dbpf_parser.py` - Test examples

**Day 4: Advanced Topics**
1. `cli.py` - CLI implementation
2. `tui.py` and `interactive_tui.py` - UI implementation
3. `.github/workflows/tests.yml` - CI/CD pipeline
4. `.pre-commit-config.yaml` - Git hooks

### Hands-On Exercises

**Exercise 1: Add a new exception**
1. Add `MyCustomError` to `exceptions.py`
2. Export from `__init__.py`
3. Write test in `tests/unit/test_exceptions.py`
4. Use in a parser/detector

**Exercise 2: Add a simple detector**
1. Create `detectors/duplicate_names.py`
2. Inherit from `ConflictDetector`
3. Implement `detect()` to find mods with duplicate names
4. Write tests
5. Integrate into `mod_analyzer.py`

**Exercise 3: Improve test coverage**
1. Choose a low-coverage module (e.g., `tuning.py`)
2. Create test fixtures in `tests/fixtures/`
3. Write unit tests for uncovered functions
4. Run `pytest --cov` to verify improvement

---

## 📋 Quick Reference

### Essential Commands

```bash
# Development
pip install -e ".[dev]"         # Install dev dependencies
pre-commit install              # Install git hooks
pre-commit run --all-files      # Run all hooks

# Testing
pytest                          # Run all tests
pytest -k "dbpf"               # Run DBPF tests only
pytest --cov                   # Run with coverage
pytest -m "not slow"           # Skip slow tests

# Code Quality
ruff check .                   # Lint
ruff format .                  # Format
mypy src/simanalysis          # Type check

# Running
simanalysis analyze ~/Mods     # Basic analysis
simanalysis analyze ~/Mods -i  # Interactive mode
simanalysis --help             # Show help
```

### File Locations

```bash
# Source
src/simanalysis/models.py              # Data models
src/simanalysis/exceptions.py          # Exceptions
src/simanalysis/cli.py                 # CLI
src/simanalysis/parsers/dbpf.py       # DBPF parser
src/simanalysis/detectors/base.py     # Detector base

# Tests
tests/conftest.py                      # Pytest fixtures
tests/fixtures/sample_mods/            # Test data
tests/unit/                            # Unit tests

# Config
pyproject.toml                         # All configuration
pytest.ini                             # Pytest config
.pre-commit-config.yaml                # Git hooks

# Documentation
README.md                              # User guide
TECHNICAL_SPECIFICATION.md             # Architecture
CONTRIBUTING.md                        # Contribution guide
docs/DBPF_FORMAT.md                   # Format spec
```

### Common Imports

```python
# Core
from simanalysis import __version__
from simanalysis.models import Mod, ModConflict, Severity, ConflictType
from simanalysis.exceptions import SimanalysisError, DBPFError

# Parsers
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.tuning import TuningParser
from simanalysis.parsers.script import ScriptAnalyzer

# Detectors
from simanalysis.detectors.base import ConflictDetector
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector

# Analyzers
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Scanners
from simanalysis.scanners.mod_scanner import ModScanner
```

---

## 🎉 Summary

**Simanalysis is a well-engineered, production-ready Python project** with:
- ✅ Strict type checking (MyPy)
- ✅ Comprehensive testing (205 tests)
- ✅ Automated code quality (Ruff, pre-commit hooks)
- ✅ Multi-platform CI/CD (GitHub Actions)
- ✅ Extensive documentation
- ✅ Clean architecture with clear separation of concerns

**For AI assistants:**
- Follow existing patterns (they're well-established)
- Write tests first (TDD encouraged)
- Use type hints everywhere
- Keep code simple and readable
- Document everything public
- Run all checks before committing

**When in doubt:**
1. Check similar existing code
2. Read the technical specification
3. Review test examples
4. Follow Python best practices (PEP 8, PEP 257)
5. Ask for clarification (via issues/discussions)

---

**Happy coding! 🚀**

*Last updated: 2025-11-22 by Claude (AI Assistant)*
