# API Overview

Complete Python API reference for Simanalysis.

## Introduction

Simanalysis provides a comprehensive Python API for programmatic mod analysis. The API is organized into several modules:

- **Parsers**: Low-level file format parsers (DBPF, XML, Python)
- **Analyzers**: High-level mod analysis
- **Detectors**: Conflict detection algorithms
- **Scanners**: File discovery and enumeration
- **Models**: Data structures and types
- **Exceptions**: Error handling

## Quick Start

### Basic Usage

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze a directory
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

print(f"Found {len(result.mods)} mods")
print(f"Found {len(result.conflicts)} conflicts")
```

### Parse a Single Mod

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader

# Read package file
reader = DBPFReader(Path("mod.package"))
header = reader.read_header()
resources = reader.read_index()

print(f"Version: {header.major_version}.{header.minor_version}")
print(f"Resources: {len(resources)}")
```

## Module Organization

### simanalysis.parsers

Low-level parsers for mod file formats:

- **DBPFReader**: Parse .package files (DBPF format)
- **TuningParser**: Parse XML tuning resources
- **ScriptAnalyzer**: Analyze .ts4script files

**Use when:**
- You need direct access to file contents
- Building custom analysis tools
- Extracting specific resources

**Example:**
```python
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.tuning import TuningParser

# Read package
reader = DBPFReader(Path("mod.package"))
resources = reader.read_index()

# Parse tuning XML
for resource in resources:
    if resource.type == 0x545503B2:  # XML tuning
        data = reader.get_resource(resource)
        parser = TuningParser()
        tuning = parser.parse(data)
        print(f"Instance: {tuning.instance_id}")
```

### simanalysis.analyzers

High-level analysis of mod collections:

- **ModAnalyzer**: Main analyzer for mod directories
- **AnalysisResult**: Analysis results container

**Use when:**
- Analyzing entire mod collections
- Need conflict detection
- Want comprehensive reports

**Example:**
```python
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Access results
for mod in result.mods:
    print(f"{mod.name}: {mod.size} bytes")

for conflict in result.conflicts:
    print(f"[{conflict.severity}] {conflict.description}")
```

### simanalysis.detectors

Conflict detection algorithms:

- **ConflictDetector**: Base detector class
- **TuningConflictDetector**: Detect tuning overlaps
- **ResourceConflictDetector**: Detect resource collisions

**Use when:**
- Implementing custom conflict detection
- Need specific conflict types
- Building analysis pipelines

**Example:**
```python
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector

detector = TuningConflictDetector()
conflicts = detector.detect(mods_list)

for conflict in conflicts:
    print(f"Conflict: {conflict.instance_id}")
```

### simanalysis.scanners

File discovery and enumeration:

- **ModScanner**: Discover mod files in directories
- **FilePattern**: File matching patterns

**Use when:**
- Custom file discovery logic
- Need to filter files by type
- Building directory traversal

**Example:**
```python
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()
mods = scanner.scan(Path("./mods"), recursive=True)

print(f"Found {len(mods)} mod files")
```

### simanalysis.models

Data structures and types:

- **Mod**: Represents a mod file
- **ModConflict**: Represents a conflict
- **DBPFHeader**: DBPF file header
- **DBPFResource**: DBPF resource entry
- **TuningInfo**: Tuning metadata

**Use when:**
- Working with analysis results
- Building custom data structures
- Type annotations

**Example:**
```python
from simanalysis.models import Mod, ModConflict

def filter_high_severity(conflicts: list[ModConflict]) -> list[ModConflict]:
    return [c for c in conflicts if c.severity == "HIGH"]
```

### simanalysis.exceptions

Error handling:

- **SimanalysisError**: Base exception
- **DBPFError**: DBPF parsing errors
- **TuningError**: Tuning parsing errors
- **AnalysisError**: Analysis errors

**Use when:**
- Error handling in applications
- Custom exception handling
- Debugging issues

**Example:**
```python
from simanalysis.exceptions import DBPFError

try:
    reader = DBPFReader(Path("invalid.package"))
    header = reader.read_header()
except DBPFError as e:
    print(f"Invalid package file: {e}")
```

## Common Patterns

### Pattern 1: Analyze and Export

```python
import json
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Export to JSON
data = {
    "mods": [
        {
            "name": m.name,
            "size": m.size,
            "type": m.mod_type,
        }
        for m in result.mods
    ],
    "conflicts": [
        {
            "severity": c.severity,
            "description": c.description,
        }
        for c in result.conflicts
    ],
}

with open("report.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Pattern 2: Custom Conflict Detection

```python
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict

class CustomDetector(ConflictDetector):
    def detect(self, mods: list[Mod]) -> list[ModConflict]:
        conflicts = []
        # Custom detection logic
        return conflicts

# Use custom detector
detector = CustomDetector()
conflicts = detector.detect(result.mods)
```

### Pattern 3: Filter and Process

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Filter large mods
large_mods = [m for m in result.mods if m.size > 10_000_000]

# Filter high-severity conflicts
high_conflicts = [
    c for c in result.conflicts
    if c.severity in ["HIGH", "CRITICAL"]
]

print(f"Large mods: {len(large_mods)}")
print(f"High-severity conflicts: {len(high_conflicts)}")
```

### Pattern 4: Incremental Analysis

```python
import json
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def analyze_with_cache(mods_dir: Path, cache_file: Path):
    """Analyze with caching for faster re-runs."""
    analyzer = ModAnalyzer()

    # Check cache
    if cache_file.exists():
        with open(cache_file) as f:
            cached = json.load(f)
        print("Using cached analysis")
        return cached

    # Analyze
    result = analyzer.analyze_directory(mods_dir)

    # Cache results
    data = {
        "mods": [{"name": m.name, "size": m.size} for m in result.mods],
        "conflicts": [{"severity": c.severity} for c in result.conflicts],
    }

    with open(cache_file, "w") as f:
        json.dump(data, f)

    return data
```

## API Stability

### Stable APIs

These APIs are stable and safe to use in production:

- `simanalysis.parsers.dbpf.DBPFReader`
- `simanalysis.parsers.tuning.TuningParser`
- `simanalysis.analyzers.mod_analyzer.ModAnalyzer`
- `simanalysis.models.*`
- `simanalysis.exceptions.*`

### Experimental APIs

These APIs may change in future versions:

- Custom detector implementations
- Internal utility functions
- Private methods (prefixed with `_`)

## Type Hints

Simanalysis uses type hints throughout the codebase:

```python
from pathlib import Path
from typing import List
from simanalysis.models import Mod, ModConflict

def filter_conflicts(
    conflicts: List[ModConflict],
    severity: str
) -> List[ModConflict]:
    """Filter conflicts by severity."""
    return [c for c in conflicts if c.severity == severity]
```

Enable type checking with mypy:

```bash
pip install mypy
mypy your_script.py
```

## Performance Tips

### Tip 1: Use Scanners for Discovery

```python
# Efficient
from simanalysis.scanners.mod_scanner import ModScanner
scanner = ModScanner()
files = scanner.scan(Path("./mods"))

# Less efficient
files = list(Path("./mods").glob("**/*.package"))
```

### Tip 2: Reuse Analyzers

```python
# Create once, use many times
analyzer = ModAnalyzer()

result1 = analyzer.analyze_directory(Path("./mods1"))
result2 = analyzer.analyze_directory(Path("./mods2"))
```

### Tip 3: Filter Early

```python
# Filter during scanning
scanner = ModScanner()
packages_only = scanner.scan(
    Path("./mods"),
    extensions=[".package"]
)

# Instead of filtering after
all_files = scanner.scan(Path("./mods"))
packages_only = [f for f in all_files if f.suffix == ".package"]
```

## Error Handling

### Comprehensive Error Handling

```python
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import (
    DBPFError,
    SimanalysisError,
)

try:
    reader = DBPFReader(Path("mod.package"))
    header = reader.read_header()
    resources = reader.read_index()

except DBPFError as e:
    print(f"DBPF error: {e}")
    # Handle specific DBPF issues

except SimanalysisError as e:
    print(f"General error: {e}")
    # Handle other Simanalysis errors

except Exception as e:
    print(f"Unexpected error: {e}")
    # Handle unexpected errors
```

## Module Reference

### Full API Documentation

- [DBPF Parser](parsers/dbpf.md) - Parse .package files
- [Tuning Parser](parsers/tuning.md) - Parse XML tuning
- [Script Parser](parsers/script.md) - Analyze .ts4script files
- [Mod Analyzer](analyzers/mod_analyzer.md) - High-level analysis
- [Mod Scanner](scanners/mod_scanner.md) - File discovery
- [Base Detector](detectors/base.md) - Detector interface
- [Tuning Conflicts](detectors/tuning_conflicts.md) - Tuning conflict detection
- [Resource Conflicts](detectors/resource_conflicts.md) - Resource conflict detection
- [Models](models.md) - Data structures
- [Exceptions](exceptions.md) - Error types

## Examples

See the [Examples](../examples/basic.md) section for practical usage examples.

## Next Steps

- Start with [Basic Examples](../examples/basic.md)
- Explore [Advanced Examples](../examples/advanced.md)
- Check individual module documentation above
- Read the [User Guide](../user-guide/analyzing-mods.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
