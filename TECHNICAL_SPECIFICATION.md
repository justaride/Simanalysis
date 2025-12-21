# Simanalysis Technical Specification v2.1
**Derrick - The PhD in Simology and Complexity Theory**

## Document Control
- **Version:** 2.1.0
- **Date:** 2025-12-09
- **Status:** Production Ready
- **Authors:** SuperClaude (Architecture), justaride (Vision)

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Design](#architecture-design)
3. [Module Specifications](#module-specifications)
4. [Data Models](#data-models)
5. [API Reference](#api-reference)
6. [Testing Strategy](#testing-strategy)
7. [Deployment Plan](#deployment-plan)
8. [External Dependencies](#external-dependencies)

---

## 1. Project Overview

### 1.1 Mission Statement
Simanalysis provides surgical precision analysis of The Sims 4 mod ecosystem, detecting conflicts, mapping dependencies, and profiling performance impacts with AI-enhanced insights.

### 1.2 Core Objectives
- Parse Sims 4 package files (.package, .ts4script)
- Detect tuning conflicts and resource overlaps
- Map mod dependencies and requirements
- Profile performance impact
- Generate actionable reports
- Provide AI-powered resolution suggestions

### 1.3 Target Users
- Mod creators (conflict debugging)
- Power users (large mod collections 500+)
- Technical support (troubleshooting)
- Mod managers (compatibility testing)

### 1.4 Success Metrics
- Parse 1000+ mods in <5 minutes
- Detect 95%+ of common conflicts
- <5% false positive rate
- Generate reports in 3 formats (JSON/HTML/MD)

---

## 2. Architecture Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Interfaces                        │
├─────────────────┬──────────────────┬────────────────────┤
│   CLI Interface │   Terminal TUI    │    Web Interface   │
│ (cli.py)        │ (tui.py)          │ (web/src/)         │
│                 │ (interactive_tui) │ React + Vite       │
└────────┬────────┴────────┬─────────┴──────────┬─────────┘
         │                 │                     │
         └────────────────┬┴─────────────────────┘
                          │ REST API
┌─────────────────────────▼───────────────────────────────┐
│               Core Analyzer Engine                       │
│            (simanalysis/analyzer.py)                    │
│  - Orchestrates analysis workflow                       │
│  - Aggregates results                                   │
│  - Manages parallel processing                          │
└──┬──────────┬──────────┬───────────┬──────────┬────────┘
   │          │          │           │          │
   ▼          ▼          ▼           ▼          ▼
┌──────┐ ┌───────┐ ┌──────────┐ ┌───────┐ ┌───────────┐
│Parser│ │Detec- │ │Analyzer  │ │Report │ │AI Engine  │
│Layer │ │tors   │ │Modules   │ │Gener. │ │(Optional) │
└──────┘ └───────┘ └──────────┘ └───────┘ └───────────┘
```

### 2.1.1 Web Interface Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  React Web Application                   │
│                     (web/src/)                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────────────────────────┐  │
│  │   Sidebar   │  │          Main Content            │  │
│  │ (Collaps.)  │  │  ┌────────────────────────────┐  │  │
│  │             │  │  │   Views (Dashboard, Mods,  │  │  │
│  │  - Dashboard│  │  │   Conflicts, Tray, Saves)  │  │  │
│  │  - Mods     │  │  └────────────────────────────┘  │  │
│  │  - Tray     │  │                                   │  │
│  │  - Saves    │  │  Components:                      │  │
│  │  - Conflicts│  │  - WelcomeHero (onboarding)      │  │
│  │  - Settings │  │  - Glass cards (stat display)    │  │
│  └─────────────┘  │  - Charts (Recharts)             │  │
│                    │  - Virtualized lists             │  │
│                    └──────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  State: AppContext │ Styling: TailwindCSS + Custom CSS  │
│  Animations: Framer Motion │ HTTP: Axios to /api/*      │
└─────────────────────────────────────────────────────────┘
```

### 2.1.2 Build Configuration

The web application uses Vite with optimized chunking for production builds:

**Bundle Strategy:**
```
dist/
├── vendor.js      (~174 KB)  # React, React-DOM, React-Router
├── charts.js      (~351 KB)  # Recharts (lazy-loaded)
├── animations.js  (~118 KB)  # Framer Motion
├── ui.js          (~0.4 KB)  # Headless UI, clsx, tailwind-merge
├── Dashboard.js   (~14 KB)   # Lazy route chunk
├── ModManager.js  (~14 KB)   # Lazy route chunk
├── Conflicts.js   (~12 KB)   # Lazy route chunk
└── [other routes] (~3-9 KB)  # Lazy route chunks
```

**Key Optimizations:**
- Route-based code splitting via `React.lazy()`
- Manual chunks for vendor libraries (better caching)
- Heavy dependencies (recharts, framer-motion) in separate chunks
- Initial page load: ~277 KB (91 KB gzipped)

### 2.2 Directory Structure

```
Simanalysis/
├── .github/
│   └── workflows/
│       ├── tests.yml              # CI/CD pipeline
│       └── release.yml            # Release automation
│
├── .codex/
│   ├── config.json                # Claude Code configuration
│   └── prompts.md                 # AI analysis prompts
│
├── src/
│   └── simanalysis/
│       ├── __init__.py            # Package initialization
│       ├── __version__.py         # Version metadata
│       ├── cli.py                 # Command-line interface
│       ├── analyzer.py            # Core analysis engine
│       ├── models.py              # Data models
│       │
│       ├── parsers/               # File parsing layer
│       │   ├── __init__.py
│       │   ├── dbpf.py           # DBPF package parser
│       │   ├── tuning.py         # XML tuning parser
│       │   ├── script.py         # TS4Script parser
│       │   └── resource.py       # Resource type definitions
│       │
│       ├── detectors/             # Conflict detection
│       │   ├── __init__.py
│       │   ├── tuning_conflicts.py    # Tuning ID conflicts
│       │   ├── resource_conflicts.py  # Resource key conflicts
│       │   ├── script_conflicts.py    # Python script conflicts
│       │   └── base.py                # Base detector interface
│       │
│       ├── analyzers/             # Analysis modules
│       │   ├── __init__.py
│       │   ├── dependencies.py    # Dependency mapping
│       │   ├── performance.py     # Performance profiling
│       │   └── compatibility.py   # Version compatibility
│       │
│       ├── reports/               # Report generation
│       │   ├── __init__.py
│       │   ├── json_report.py    # JSON output
│       │   ├── html_report.py    # HTML report
│       │   ├── markdown_report.py # Markdown report
│       │   └── templates/        # Report templates
│       │       ├── report.html
│       │       └── report.md
│       │
│       ├── ai/                    # AI integration (optional)
│       │   ├── __init__.py
│       │   ├── claude_analyzer.py # Claude API integration
│       │   └── prompts.py        # AI prompt templates
│       │
│       └── utils/                 # Utilities
│           ├── __init__.py
│           ├── file_utils.py     # File operations
│           ├── hash_utils.py     # Hashing functions
│           └── logger.py         # Logging configuration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest configuration
│   ├── fixtures/                 # Test data
│   │   ├── sample_mods/
│   │   └── mock_packages/
│   │
│   ├── unit/                     # Unit tests
│   │   ├── test_dbpf_parser.py
│   │   ├── test_tuning_parser.py
│   │   ├── test_script_parser.py
│   │   ├── test_detectors.py
│   │   └── test_analyzers.py
│   │
│   └── integration/              # Integration tests
│       ├── test_full_analysis.py
│       └── test_cli.py
│
├── docs/
│   ├── index.md                  # Documentation home
│   ├── getting_started.md        # Quick start guide
│   ├── api_reference.md          # API documentation
│   ├── file_formats.md           # DBPF/Tuning format docs
│   ├── conflict_types.md         # Conflict detection guide
│   └── examples/                 # Usage examples
│       ├── basic_analysis.py
│       └── advanced_filtering.py
│
├── scripts/                      # Development scripts
│   ├── setup_dev.sh             # Dev environment setup
│   ├── run_tests.sh             # Test runner
│   └── build_docs.sh            # Documentation builder
│
├── .gitignore
├── .pre-commit-config.yaml       # Pre-commit hooks
├── pyproject.toml                # Project configuration
├── ruff.toml                     # Ruff linter config
├── mypy.ini                      # Type checking config
├── pytest.ini                    # Pytest configuration
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # Development dependencies
├── LICENSE                       # MIT License
├── README.md                     # Project README
├── CONTRIBUTING.md               # Contribution guidelines
├── CHANGELOG.md                  # Version history
└── TECHNICAL_SPECIFICATION.md    # This document
```

### 2.3 Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| Language | Python 3.9+ | Sims community standard, rich ecosystem |
| Parsing | Custom DBPF + lxml | Performance + XML handling |
| CLI | Click + Rich | Beautiful terminal UI |
| Testing | pytest + pytest-cov | Industry standard |
| Linting | Ruff + MyPy | Fast, comprehensive checking |
| Documentation | MkDocs | Clean, searchable docs |
| AI Integration | Anthropic SDK | Claude integration |
| Graphs | NetworkX | Dependency visualization |

---

## 3. Module Specifications

### 3.1 Core Parsers

#### 3.1.1 DBPF Parser (`parsers/dbpf.py`)

**Purpose:** Parse Sims 4 .package files (DBPF v2.0 format)

**Classes:**
```python
class DBPFHeader:
    """DBPF file header (96 bytes)"""
    magic: bytes              # "DBPF" signature
    major_version: int        # Usually 2
    minor_version: int        # Usually 0
    user_version: int         # Usually 0
    index_count: int          # Number of resources
    index_offset: int         # Offset to index table
    index_size: int           # Size of index table

class DBPFResource:
    """Individual resource entry"""
    type: int                 # Resource type (4 bytes)
    group: int                # Resource group (4 bytes)
    instance: int             # Resource instance (8 bytes)
    offset: int               # File offset
    size: int                 # Resource size
    compressed_size: int      # Compressed size (if compressed)

class DBPFReader:
    """Main DBPF parser"""

    def __init__(self, package_path: Path)
    def read_header(self) -> DBPFHeader
    def read_index(self) -> List[DBPFResource]
    def get_resource(self, resource: DBPFResource) -> bytes
    def get_resources_by_type(self, type_id: int) -> List[DBPFResource]
    def extract_all(self, output_dir: Path) -> None
```

**Key Features:**
- Memory-efficient streaming for large packages
- Support for compressed resources (zlib)
- Resource filtering by type/group/instance
- Thread-safe for parallel processing

**Resource Type Constants:**
```python
RESOURCE_TYPE_XML_TUNING = 0x545238C9
RESOURCE_TYPE_SIMDATA = 0x0333406C
RESOURCE_TYPE_SCRIPT = 0xD382BF57
RESOURCE_TYPE_STRING = 0x220557DA
```

#### 3.1.2 Tuning Parser (`parsers/tuning.py`)

**Purpose:** Parse XML tuning modifications

**Classes:**
```python
@dataclass
class TuningData:
    """Parsed tuning file data"""
    instance_id: int
    tuning_name: str
    tuning_class: str
    module: str
    modified_attributes: Dict[str, Any]
    references: Set[int]      # Referenced tuning IDs
    pack_requirements: Set[str]

class TuningParser:
    """XML tuning parser"""

    def parse(self, xml_data: bytes) -> TuningData
    def get_instance_id(self, xml_root: Element) -> int
    def extract_modifications(self, xml_root: Element) -> Dict
    def find_references(self, xml_root: Element) -> Set[int]
    def detect_pack_requirements(self, xml_root: Element) -> Set[str]
```

**Pack Detection:**
```python
# EP = Expansion Pack, GP = Game Pack, SP = Stuff Pack
PACK_PREFIXES = {
    "EP01": "Get to Work",
    "EP02": "Get Together",
    "EP03": "City Living",
    # ... etc
}
```

#### 3.1.3 Script Parser (`parsers/script.py`)

**Purpose:** Analyze .ts4script files (zip archives containing Python)

**Classes:**
```python
@dataclass
class ScriptMetadata:
    """Script mod metadata"""
    name: str
    version: str
    author: str
    requires: List[str]       # Required mods/libraries
    python_version: str       # Target Python version

@dataclass
class ScriptModule:
    """Individual Python module in script"""
    name: str
    path: str
    imports: Set[str]
    hooks: List[str]          # Detected game hooks
    complexity: int           # Cyclomatic complexity

class ScriptAnalyzer:
    """TS4Script analyzer"""

    def __init__(self, script_path: Path)
    def extract_metadata(self) -> ScriptMetadata
    def list_modules(self) -> List[ScriptModule]
    def analyze_module(self, module_path: str) -> ScriptModule
    def detect_hooks(self, ast_tree: ast.AST) -> List[str]
    def calculate_complexity(self, ast_tree: ast.AST) -> int
```

**Common Hook Patterns:**
```python
HOOK_PATTERNS = [
    "inject_to",           # Function injection
    "wrap_function",       # Function wrapping
    "override",            # Direct override
    "event.register",      # Event registration
]
```

### 3.2 Conflict Detectors

#### 3.2.1 Base Detector (`detectors/base.py`)

```python
class ConflictDetector(ABC):
    """Abstract base for conflict detectors"""

    @abstractmethod
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """Detect conflicts in mod collection"""
        pass

    def calculate_severity(self, conflict_data: Dict) -> str:
        """Calculate conflict severity"""
        # Returns: CRITICAL, HIGH, MEDIUM, LOW
```

**Severity Criteria:**
```python
CRITICAL:  # Game-breaking
  - Duplicate core tuning IDs
  - Script namespace collisions
  - Incompatible library versions

HIGH:      # Likely broken
  - Duplicate animation/CAS resources
  - Conflicting script hooks
  - Missing hard dependencies

MEDIUM:    # Potentially problematic
  - Duplicate object tunings
  - Soft dependency issues
  - Performance concerns

LOW:       # Cosmetic/informational
  - Duplicate strings
  - Redundant tunings
  - Version warnings
```

#### 3.2.2 Tuning Conflict Detector (`detectors/tuning_conflicts.py`)

```python
class TuningConflictDetector(ConflictDetector):
    """Detect tuning ID conflicts"""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        # Build tuning ID index
        # Find duplicates
        # Classify by tuning type
        # Calculate severity

    def classify_tuning_type(self, tuning_id: int) -> str:
        """Determine tuning category (Sim, Object, Interaction, etc.)"""
```

#### 3.2.3 Resource Conflict Detector (`detectors/resource_conflicts.py`)

```python
class ResourceConflictDetector(ConflictDetector):
    """Detect resource key conflicts"""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        # Index by (Type, Group, Instance) tuple
        # Find exact duplicates
        # Detect overwrites

    def is_intentional_override(self, resource: DBPFResource) -> bool:
        """Detect if override is intentional (default replacement)"""
```

#### 3.2.4 Script Conflict Detector (`detectors/script_conflicts.py`)

```python
class ScriptConflictDetector(ConflictDetector):
    """Detect Python script conflicts"""

    def detect(self, scripts: List[ScriptMod]) -> List[ModConflict]:
        # Check injection points
        # Verify library versions
        # Detect namespace collisions

    def check_injection_compatibility(self, hooks: List[Hook]) -> bool:
        """Verify multiple injections can coexist"""
```

### 3.3 Analyzers

#### 3.3.1 Dependency Mapper (`analyzers/dependencies.py`)

```python
class DependencyMapper:
    """Map mod dependencies and requirements"""

    def build_graph(self, mods: List[Mod]) -> DependencyGraph:
        """Create dependency graph"""

    def find_missing(self, mods: List[Mod]) -> List[str]:
        """Detect missing required mods"""

    def find_circular(self, graph: DependencyGraph) -> List[List[str]]:
        """Detect circular dependencies"""

    def get_load_order(self, graph: DependencyGraph) -> List[str]:
        """Calculate optimal load order (topological sort)"""
```

#### 3.3.2 Performance Profiler (`analyzers/performance.py`)

```python
class PerformanceProfiler:
    """Estimate performance impact"""

    def calculate_load_impact(self, mod: Mod) -> LoadImpact:
        """Estimate game load time impact"""

    def estimate_memory_usage(self, mods: List[Mod]) -> MemoryEstimate:
        """Estimate memory consumption"""

    def calculate_complexity_score(self, mods: List[Mod]) -> float:
        """Overall mod collection complexity (0-100)"""
```

**Performance Metrics:**
```python
@dataclass
class LoadImpact:
    file_count: int           # Number of files to load
    total_size: int           # Total bytes
    script_count: int         # Active scripts
    tuning_count: int         # Tuning modifications
    estimated_load_time: float # Seconds (rough estimate)

@dataclass
class MemoryEstimate:
    base_memory: int          # Base mod memory (MB)
    script_memory: int        # Script overhead (MB)
    texture_memory: int       # Texture/mesh memory (MB)
    total_estimate: int       # Total (MB)
```

### 3.4 Report Generators

#### 3.4.1 JSON Report (`reports/json_report.py`)

```python
class JSONReportGenerator:
    """Generate structured JSON output"""

    def generate(self, results: AnalysisResult) -> str:
        # Serialize to JSON
        # Include metadata
        # Add timestamps

    def save(self, results: AnalysisResult, output_path: Path):
        """Save JSON to file"""
```

**JSON Schema:**
```json
{
  "analysis": {
    "timestamp": "2025-10-21T12:00:00Z",
    "version": "2.0.0",
    "mod_directory": "/path/to/mods",
    "total_mods": 450,
    "analysis_duration": 12.5
  },
  "conflicts": [
    {
      "id": "conflict_001",
      "severity": "HIGH",
      "type": "TUNING_OVERLAP",
      "affected_mods": ["mod_a.package", "mod_b.package"],
      "description": "Tuning ID 0x12345678 modified by multiple mods",
      "resolution": "Keep only one mod or use compatibility patch"
    }
  ],
  "dependencies": {
    "mod_a.package": ["required_lib.ts4script"],
    "mod_b.package": []
  },
  "performance": {
    "load_impact_score": 65.5,
    "memory_estimate_mb": 250,
    "complexity_score": 72.3
  },
  "recommendations": [
    "Remove duplicate mod: duplicate_mod.package",
    "Update outdated mod: old_mod.package"
  ]
}
```

#### 3.4.2 HTML Report (`reports/html_report.py`)

```python
class HTMLReportGenerator:
    """Generate interactive HTML report"""

    def __init__(self, template_dir: Path):
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir)
        )

    def generate(self, results: AnalysisResult) -> str:
        template = self.env.get_template("report.html")
        return template.render(
            analysis=results,
            severity_colors=SEVERITY_COLORS,
            generated_at=datetime.now()
        )
```

**Features:**
- Severity color coding
- Sortable conflict table
- Expandable details
- Dependency graph visualization
- Performance gauges
- Dark/light theme toggle

#### 3.4.3 Markdown Report (`reports/markdown_report.py`)

```python
class MarkdownReportGenerator:
    """Generate GitHub-friendly Markdown report"""

    def generate(self, results: AnalysisResult) -> str:
        # Create markdown structure
        # Add tables
        # Include code blocks
        # Link to relevant mods
```

---

## 4. Data Models

### 4.1 Core Models (`models.py`)

```python
@dataclass
class Mod:
    """Represents a single mod"""
    name: str
    path: Path
    type: ModType                  # PACKAGE, SCRIPT, HYBRID
    size: int
    hash: str                      # SHA256

    # Parsed data
    resources: List[DBPFResource]
    tunings: List[TuningData]
    scripts: List[ScriptModule]

    # Metadata
    version: Optional[str]
    author: Optional[str]
    requires: List[str]
    pack_requirements: Set[str]

@dataclass
class ModConflict:
    """Represents a detected conflict"""
    id: str                        # Unique conflict ID
    severity: Severity
    type: ConflictType
    affected_mods: List[str]
    description: str
    resolution: Optional[str]
    details: Dict[str, Any]        # Type-specific details

@dataclass
class AnalysisResult:
    """Complete analysis results"""
    metadata: AnalysisMetadata
    mods: List[Mod]
    conflicts: List[ModConflict]
    dependencies: Dict[str, List[str]]
    performance: PerformanceMetrics
    recommendations: List[str]
    warnings: List[str]

class ModType(Enum):
    PACKAGE = "package"
    SCRIPT = "script"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"

class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class ConflictType(Enum):
    TUNING_OVERLAP = "TUNING_OVERLAP"
    RESOURCE_DUPLICATE = "RESOURCE_DUPLICATE"
    SCRIPT_INJECTION = "SCRIPT_INJECTION"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    NAMESPACE_COLLISION = "NAMESPACE_COLLISION"
```

---

## 5. API Reference

### 5.1 Public API

```python
from simanalysis import ModAnalyzer

# Basic usage
analyzer = ModAnalyzer(mod_directory="/path/to/mods")
results = analyzer.analyze()

# Advanced usage
analyzer = ModAnalyzer(
    mod_directory="/path/to/mods",
    deep_scan=True,
    parallel=True,
    max_workers=4
)

# Selective analysis
results = analyzer.analyze(
    detect_conflicts=True,
    map_dependencies=True,
    profile_performance=True,
    ai_suggestions=False  # Requires API key
)

# Filter results
critical_conflicts = results.get_conflicts(severity=Severity.CRITICAL)
script_conflicts = results.get_conflicts(type=ConflictType.SCRIPT_INJECTION)

# Generate reports
from simanalysis.reports import HTMLReportGenerator

generator = HTMLReportGenerator()
html = generator.generate(results)
generator.save(results, "report.html")
```

### 5.2 CLI API

```bash
# Basic analysis
simanalysis analyze --mods-dir ~/Mods

# Deep scan with HTML report
simanalysis analyze --mods-dir ~/Mods --deep-scan --output report.html

# Conflict-only mode
simanalysis conflicts --mods-dir ~/Mods --severity CRITICAL

# Dependency graph
simanalysis deps --mods-dir ~/Mods --visualize --output deps.png

# Performance profile
simanalysis perf --mods-dir ~/Mods

# AI-powered analysis (requires ANTHROPIC_API_KEY)
simanalysis analyze --mods-dir ~/Mods --ai-suggestions

# Watch mode (reanalyze on changes)
simanalysis watch --mods-dir ~/Mods --auto-report
```

---

## 6. Testing Strategy

### 6.1 Test Coverage Goals
- **Unit tests:** 90%+ coverage
- **Integration tests:** All critical paths
- **Performance tests:** Load time benchmarks
- **Regression tests:** Known conflict scenarios

### 6.2 Test Structure

```python
# Unit test example
def test_dbpf_header_parsing():
    """Test DBPF header parsing"""
    reader = DBPFReader("tests/fixtures/sample.package")
    header = reader.read_header()

    assert header.magic == b"DBPF"
    assert header.major_version == 2
    assert header.index_count > 0

# Integration test example
def test_full_conflict_detection():
    """Test end-to-end conflict detection"""
    analyzer = ModAnalyzer("tests/fixtures/conflicting_mods")
    results = analyzer.analyze()

    assert len(results.conflicts) == 2
    assert results.conflicts[0].severity == Severity.HIGH
```

### 6.3 Test Fixtures

```
tests/fixtures/
├── sample_mods/
│   ├── simple_mod.package          # Minimal valid package
│   ├── script_mod.ts4script        # Sample script mod
│   ├── conflicting_mod_a.package   # Conflicts with B
│   └── conflicting_mod_b.package   # Conflicts with A
│
└── mock_packages/
    ├── valid_tuning.xml
    ├── invalid_tuning.xml
    └── sample_dbpf_header.bin
```

---

## 7. Deployment Plan

### 7.1 Distribution Methods

**PyPI Package:**
```bash
pip install simanalysis
```

**GitHub Releases:**
- Source distribution
- Wheel package
- Standalone executables (PyInstaller)

**Docker Container:**
```bash
docker pull ghcr.io/justaride/simanalysis:latest
docker run -v ~/Mods:/mods simanalysis analyze --mods-dir /mods
```

### 7.2 Version Strategy

**Semantic Versioning:**
- `2.0.0` - Initial release with full feature set
- `2.1.0` - AI integration
- `2.2.0` - GUI version
- `3.0.0` - Breaking API changes

### 7.3 Continuous Integration

**GitHub Actions Workflow:**
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy .
      - run: pytest --cov=simanalysis --cov-report=xml
      - uses: codecov/codecov-action@v3
```

---

## 8. External Dependencies

### 8.1 Required Resources

**For Development:**
- ✅ Python 3.9+ environment
- ✅ DBPF format documentation
- ✅ XML tuning structure docs
- ⚠️ Sample mod files (100+ varied mods)
- ⚠️ Known conflict test cases

**For Testing:**
- 🔴 Real Sims 4 mod collection
- 🔴 Verified conflict scenarios
- 🟡 Performance baseline data
- 🟡 Community mod database

**For Production:**
- ✅ PyPI account (for publishing)
- ✅ GitHub repository
- 🟡 Anthropic API key (for AI features)
- 🟡 Documentation hosting (Read the Docs)

### 8.2 Community Resources

**Essential Links:**
- [Sims 4 Studio](https://sims4studio.com/) - Mod creation tool
- [Mod The Sims](https://modthesims.info/) - Mod repository
- [Sims 4 Modding Wiki](https://sims-4-modding.fandom.com/)
- [Scumbumbo's Tutorials](https://scumbumbomods.com/) (archived)

**Discord Servers:**
- Sims 4 Modding Community
- Frankk's Modding Discord
- TwistedMexi's Development Server

### 8.3 Development Timeline

**Sprint 1 (Week 1): Core Parsers** - Can start immediately
**Sprint 2 (Week 2): Conflict Detection** - Can start immediately
**Sprint 3 (Week 3): Analysis Features** - Can start immediately
**Sprint 4 (Week 4): Testing & Polish** - Requires real mod files
**Sprint 5 (Week 5): Documentation** - Can start anytime
**Sprint 6 (Week 6): Release Prep** - After testing complete

---

## 9. Open Questions

### 9.1 Technical Decisions Needed
- [ ] Use s4py library or custom DBPF implementation?
- [ ] Parallel processing: multiprocessing or threading?
- [ ] Cache analysis results? (SQLite database?)
- [ ] Support for older DBPF versions (Sims 2/3)?

### 9.2 Feature Prioritization
- [ ] Web dashboard vs CLI-only v1.0?
- [ ] Include AI features in v1.0 or v1.1?
- [ ] Auto-update mod metadata from web?
- [ ] Integration with mod manager tools?

### 9.3 Community Engagement
- [ ] Beta testing program structure?
- [ ] How to collect mod test data ethically?
- [ ] Contribution guidelines for domain experts?
- [ ] Licensing for AI-generated suggestions?

---

## 10. Conclusion

This technical specification provides a complete blueprint for implementing Simanalysis v2.0. The architecture is modular, testable, and extensible.

**Next Steps:**
1. Review and approve architecture
2. Set up project structure
3. Implement Sprint 1 (Core Parsers)
4. Gather test mod collection
5. Begin iterative development

**Estimated Completion:** 6 weeks for v1.0 release

---

*Document Version: 2.0.0*
*Last Updated: 2025-10-21*
*Next Review: Sprint 1 Completion*
