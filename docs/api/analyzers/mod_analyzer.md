# Mod Analyzer

High-level API for analyzing mod collections and detecting conflicts.

## Overview

The Mod Analyzer provides a complete analysis pipeline that:
- Scans directories for mod files
- Parses each mod (packages and scripts)
- Detects conflicts between mods
- Returns comprehensive analysis results

## Quick Example

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze mods directory
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

print(f"Total mods: {len(result.mods)}")
print(f"Total conflicts: {len(result.conflicts)}")

# Show high-severity conflicts
for conflict in result.conflicts:
    if conflict.severity in ["HIGH", "CRITICAL"]:
        print(f"[{conflict.severity}] {conflict.description}")
```

## API Reference

::: simanalysis.analyzers.mod_analyzer
    options:
      show_root_heading: true
      show_source: true
      members:
        - ModAnalyzer
        - AnalysisResult
      group_by_category: true

## AnalysisResult Structure

The analyzer returns an `AnalysisResult` object:

| Attribute | Type | Description |
|-----------|------|-------------|
| `mods` | List[Mod] | All analyzed mods |
| `conflicts` | List[ModConflict] | Detected conflicts |
| `scan_directory` | Path | Root directory scanned |
| `total_size` | int | Total size of all mods (bytes) |
| `total_resources` | int | Total DBPF resources |
| `analysis_time` | float | Time taken for analysis (seconds) |

## Usage Examples

### Example 1: Basic Analysis

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Print summary
print(f"=== ANALYSIS SUMMARY ===")
print(f"Mods: {len(result.mods)}")
print(f"Total size: {result.total_size / 1024 / 1024:.1f} MB")
print(f"Resources: {result.total_resources}")
print(f"Conflicts: {len(result.conflicts)}")
print(f"Analysis time: {result.analysis_time:.2f}s")
```

### Example 2: Filter by Mod Type

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Separate by type
packages = [m for m in result.mods if m.mod_type == "package"]
scripts = [m for m in result.mods if m.mod_type == "script"]

print(f"Package mods: {len(packages)}")
print(f"Script mods: {len(scripts)}")

# Analyze packages
total_package_size = sum(m.size for m in packages)
print(f"Total package size: {total_package_size / 1024 / 1024:.1f} MB")
```

### Example 3: Find Conflicted Mods

```python
from pathlib import Path
from collections import Counter
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Count conflicts per mod
conflict_counts = Counter()
for conflict in result.conflicts:
    for mod_path in conflict.affected_mods:
        conflict_counts[mod_path] += 1

# Show most conflicted mods
print("Most conflicted mods:")
for mod_path, count in conflict_counts.most_common(10):
    mod_name = Path(mod_path).name
    print(f"  {mod_name}: {count} conflicts")
```

### Example 4: Export Analysis Results

```python
import json
from pathlib import Path
from datetime import datetime
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def export_analysis(result, output_path: Path):
    """Export analysis results to JSON."""
    data = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "scan_directory": str(result.scan_directory),
            "analysis_time": result.analysis_time,
        },
        "summary": {
            "total_mods": len(result.mods),
            "total_size": result.total_size,
            "total_resources": result.total_resources,
            "total_conflicts": len(result.conflicts),
        },
        "mods": [
            {
                "name": mod.name,
                "path": str(mod.path),
                "size": mod.size,
                "type": mod.mod_type,
                "resources": len(mod.resources) if mod.resources else 0,
            }
            for mod in result.mods
        ],
        "conflicts": [
            {
                "type": conflict.type,
                "severity": conflict.severity,
                "description": conflict.description,
                "affected_mods": [str(p) for p in conflict.affected_mods],
            }
            for conflict in result.conflicts
        ],
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

# Usage
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))
export_analysis(result, Path("report.json"))
```

### Example 5: Compare Two Collections

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def compare_collections(dir1: Path, dir2: Path):
    """Compare two mod collections."""
    analyzer = ModAnalyzer()

    result1 = analyzer.analyze_directory(dir1)
    result2 = analyzer.analyze_directory(dir2)

    # Compare sizes
    print(f"Collection 1: {len(result1.mods)} mods, {len(result1.conflicts)} conflicts")
    print(f"Collection 2: {len(result2.mods)} mods, {len(result2.conflicts)} conflicts")

    # Find mods in common
    names1 = {mod.name for mod in result1.mods}
    names2 = {mod.name for mod in result2.mods}

    common = names1 & names2
    only_1 = names1 - names2
    only_2 = names2 - names1

    print(f"\nCommon mods: {len(common)}")
    print(f"Only in collection 1: {len(only_1)}")
    print(f"Only in collection 2: {len(only_2)}")

# Usage
compare_collections(Path("./mods1"), Path("./mods2"))
```

### Example 6: Analyze with Custom Filters

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.scanners.mod_scanner import ModScanner

# Custom scanning with filters
scanner = ModScanner()
mod_files = scanner.scan(
    Path("./mods"),
    extensions=[".package"],  # Only packages
    recursive=True
)

# Analyze filtered mods
analyzer = ModAnalyzer()
result = analyzer.analyze_files(mod_files)

print(f"Analyzed {len(result.mods)} package files")
```

## Configuration

### Analyzer Options

Configure the analyzer behavior:

```python
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Create analyzer with options
analyzer = ModAnalyzer(
    detect_conflicts=True,  # Enable conflict detection (default)
    parse_scripts=True,     # Analyze .ts4script files (default)
    verbose=False,          # Quiet mode (default)
)
```

### Scanning Options

Control how directories are scanned:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()

# Scan with options
result = analyzer.analyze_directory(
    Path("./mods"),
    recursive=True,  # Include subdirectories (default)
    extensions=[".package", ".ts4script"],  # File types
    follow_symlinks=False,  # Don't follow symbolic links (default)
)
```

## Performance Optimization

### Tip 1: Limit File Types

Analyze only necessary file types:

```python
# Faster - only packages
result = analyzer.analyze_directory(
    Path("./mods"),
    extensions=[".package"]
)

# Slower - all files
result = analyzer.analyze_directory(Path("./mods"))
```

### Tip 2: Non-Recursive Analysis

For large collections, analyze subdirectories separately:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()

# Analyze each category separately
for subdir in Path("./mods").iterdir():
    if subdir.is_dir():
        result = analyzer.analyze_directory(
            subdir,
            recursive=False  # Don't go deeper
        )
        print(f"{subdir.name}: {len(result.mods)} mods, {len(result.conflicts)} conflicts")
```

### Tip 3: Reuse Analyzer

Create analyzer once, use multiple times:

```python
# Good - reuse analyzer
analyzer = ModAnalyzer()
result1 = analyzer.analyze_directory(Path("./mods1"))
result2 = analyzer.analyze_directory(Path("./mods2"))

# Less efficient - create multiple analyzers
result1 = ModAnalyzer().analyze_directory(Path("./mods1"))
result2 = ModAnalyzer().analyze_directory(Path("./mods2"))
```

## Error Handling

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.exceptions import AnalysisError

try:
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(Path("./mods"))

except AnalysisError as e:
    print(f"Analysis error: {e}")

except FileNotFoundError:
    print("Directory not found")

except PermissionError:
    print("Permission denied")

except Exception as e:
    print(f"Unexpected error: {e}")
```

## Progress Tracking

Track analysis progress:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

class ProgressCallback:
    def __init__(self, total):
        self.total = total
        self.current = 0

    def update(self, mod_name):
        self.current += 1
        print(f"[{self.current}/{self.total}] Analyzing {mod_name}")

# Count mods first
from simanalysis.scanners.mod_scanner import ModScanner
scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"))

# Analyze with progress
analyzer = ModAnalyzer()
progress = ProgressCallback(len(mod_files))

# Note: Progress callback support may vary by version
result = analyzer.analyze_files(mod_files)
```

## Advanced Usage

### Custom Conflict Detection

Add custom detectors:

```python
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.detectors.base import ConflictDetector

class MyCustomDetector(ConflictDetector):
    def detect(self, mods):
        # Custom detection logic
        return []

# Create analyzer with custom detector
analyzer = ModAnalyzer()
# Note: Custom detector integration API may vary
```

### Batch Analysis

Analyze multiple directories:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def batch_analyze(directories: list[Path]) -> dict:
    """Analyze multiple directories and aggregate results."""
    analyzer = ModAnalyzer()
    results = {}

    for directory in directories:
        result = analyzer.analyze_directory(directory)
        results[directory.name] = {
            "mods": len(result.mods),
            "conflicts": len(result.conflicts),
            "size": result.total_size,
        }

    return results

# Usage
dirs = [
    Path("./mods/gameplay"),
    Path("./mods/cas"),
    Path("./mods/build_buy"),
]

results = batch_analyze(dirs)
for name, stats in results.items():
    print(f"{name}: {stats['mods']} mods, {stats['conflicts']} conflicts")
```

## See Also

- [Mod Scanner](../scanners/mod_scanner.md) - File discovery
- [Conflict Detectors](../detectors/base.md) - Conflict detection
- [Models](../models.md) - Data structures
- [Examples](../../examples/basic.md) - Usage examples

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
