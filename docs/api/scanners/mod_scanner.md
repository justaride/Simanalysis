# Mod Scanner

File discovery and enumeration for mod collections.

## Overview

The Mod Scanner discovers mod files in directories, supporting:
- Recursive directory traversal
- File type filtering
- Pattern matching
- Hidden file exclusion

## Quick Example

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

# Scan for mods
scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"))

print(f"Found {len(mod_files)} mod files")
for mod_file in mod_files[:5]:
    print(f"  - {mod_file.name}")
```

## API Reference

::: simanalysis.scanners.mod_scanner
    options:
      show_root_heading: true
      show_source: true
      members:
        - ModScanner
      group_by_category: true

## Usage Examples

### Example 1: Recursive Scan

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()

# Scan recursively (default)
mod_files = scanner.scan(Path("./mods"), recursive=True)
print(f"Found {len(mod_files)} mods in all subdirectories")

# Non-recursive (current directory only)
mod_files = scanner.scan(Path("./mods"), recursive=False)
print(f"Found {len(mod_files)} mods in root directory")
```

### Example 2: Filter by Extension

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()

# Only .package files
packages = scanner.scan(
    Path("./mods"),
    extensions=[".package"]
)
print(f"Package files: {len(packages)}")

# Only .ts4script files
scripts = scanner.scan(
    Path("./mods"),
    extensions=[".ts4script"]
)
print(f"Script files: {len(scripts)}")

# Both (default)
all_mods = scanner.scan(
    Path("./mods"),
    extensions=[".package", ".ts4script"]
)
print(f"All mods: {len(all_mods)}")
```

### Example 3: Organize by Directory

```python
from pathlib import Path
from collections import defaultdict
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"))

# Group by parent directory
by_directory = defaultdict(list)
for mod_file in mod_files:
    parent = mod_file.parent.name
    by_directory[parent].append(mod_file.name)

# Print organization
print("Mods by directory:")
for directory, files in sorted(by_directory.items()):
    print(f"\n{directory}/ ({len(files)} mods)")
    for filename in sorted(files)[:5]:
        print(f"  - {filename}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")
```

### Example 4: Find Large Mods

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"))

# Find mods over 10 MB
large_mods = [
    f for f in mod_files
    if f.stat().st_size > 10 * 1024 * 1024
]

# Sort by size
large_mods.sort(key=lambda f: f.stat().st_size, reverse=True)

print(f"Found {len(large_mods)} mods over 10 MB:")
for mod_file in large_mods[:10]:
    size_mb = mod_file.stat().st_size / 1024 / 1024
    print(f"  {mod_file.name}: {size_mb:.1f} MB")
```

### Example 5: Check for Duplicates

```python
from pathlib import Path
from collections import defaultdict
from simanalysis.scanners.mod_scanner import ModScanner

scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"))

# Group by name (case-insensitive)
by_name = defaultdict(list)
for mod_file in mod_files:
    name = mod_file.name.lower()
    by_name[name].append(mod_file)

# Find duplicates
duplicates = {name: files for name, files in by_name.items() if len(files) > 1}

if duplicates:
    print(f"Found {len(duplicates)} duplicate mod names:")
    for name, files in duplicates.items():
        print(f"\n  {name}:")
        for file in files:
            print(f"    - {file.parent}/{file.name}")
else:
    print("No duplicate mod names found")
```

### Example 6: Scan Multiple Directories

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

def scan_multiple(directories: list[Path]) -> dict:
    """Scan multiple directories and collect results."""
    scanner = ModScanner()
    results = {}

    for directory in directories:
        if directory.exists():
            mod_files = scanner.scan(directory)
            results[directory.name] = mod_files
        else:
            print(f"Warning: {directory} does not exist")

    return results

# Usage
directories = [
    Path("./mods/gameplay"),
    Path("./mods/cas"),
    Path("./mods/build_buy"),
]

results = scan_multiple(directories)

for dir_name, files in results.items():
    total_size = sum(f.stat().st_size for f in files)
    print(f"{dir_name}: {len(files)} mods, {total_size / 1024 / 1024:.1f} MB")
```

## Scanning Options

### Recursive Scanning

```python
# Include all subdirectories (default)
mod_files = scanner.scan(Path("./mods"), recursive=True)

# Only current directory
mod_files = scanner.scan(Path("./mods"), recursive=False)
```

### Extension Filtering

```python
# Default: both .package and .ts4script
mod_files = scanner.scan(Path("./mods"))

# Only specific extensions
mod_files = scanner.scan(
    Path("./mods"),
    extensions=[".package"]
)

# Custom extensions (if needed)
mod_files = scanner.scan(
    Path("./mods"),
    extensions=[".custom"]
)
```

### Hidden Files

Hidden files and directories are automatically excluded:

```python
# Automatically skips:
# - Files starting with .
# - Directories starting with .
# - __MACOSX directories
# - Thumbs.db files
```

## Performance

### Tip 1: Limit Recursion Depth

For better performance with deep directory structures:

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

def scan_limited_depth(root: Path, max_depth: int = 2) -> list[Path]:
    """Scan with limited recursion depth."""
    scanner = ModScanner()
    results = []

    def scan_recursive(path: Path, depth: int):
        if depth > max_depth:
            return

        # Scan current level
        files = scanner.scan(path, recursive=False)
        results.extend(files)

        # Recurse into subdirectories
        for subdir in path.iterdir():
            if subdir.is_dir() and not subdir.name.startswith('.'):
                scan_recursive(subdir, depth + 1)

    scan_recursive(root, 0)
    return results

# Usage
mod_files = scan_limited_depth(Path("./mods"), max_depth=2)
```

### Tip 2: Parallel Scanning

Scan multiple directories in parallel:

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

def parallel_scan(directories: list[Path]) -> list[Path]:
    """Scan multiple directories in parallel."""
    scanner = ModScanner()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(scanner.scan, directory)
            for directory in directories
        ]

        results = []
        for future in futures:
            results.extend(future.result())

    return results

# Usage
directories = [Path(f"./mods/subdir{i}") for i in range(10)]
mod_files = parallel_scan(directories)
```

### Tip 3: Cache Results

Cache scan results for faster repeated access:

```python
import json
from pathlib import Path
from datetime import datetime
from simanalysis.scanners.mod_scanner import ModScanner

class CachedScanner:
    """Scanner with caching."""

    def __init__(self, cache_file: Path = Path(".scan_cache.json")):
        self.scanner = ModScanner()
        self.cache_file = cache_file

    def scan(self, directory: Path, max_age_hours: int = 24) -> list[Path]:
        """Scan with caching."""
        cache_key = str(directory)

        # Load cache
        cache = self._load_cache()

        # Check cache validity
        if cache_key in cache:
            cached_time = datetime.fromisoformat(cache[cache_key]["timestamp"])
            age = (datetime.now() - cached_time).total_seconds() / 3600

            if age < max_age_hours:
                print(f"Using cached scan results (age: {age:.1f}h)")
                return [Path(p) for p in cache[cache_key]["files"]]

        # Perform fresh scan
        print("Scanning directory...")
        files = self.scanner.scan(directory)

        # Update cache
        cache[cache_key] = {
            "timestamp": datetime.now().isoformat(),
            "files": [str(f) for f in files],
        }
        self._save_cache(cache)

        return files

    def _load_cache(self) -> dict:
        if self.cache_file.exists():
            with open(self.cache_file) as f:
                return json.load(f)
        return {}

    def _save_cache(self, cache: dict):
        with open(self.cache_file, "w") as f:
            json.dump(cache, f, indent=2)

# Usage
scanner = CachedScanner()
mod_files = scanner.scan(Path("./mods"))
```

## File Statistics

### Collect File Statistics

```python
from pathlib import Path
from datetime import datetime
from simanalysis.scanners.mod_scanner import ModScanner

def collect_statistics(directory: Path) -> dict:
    """Collect statistics about mod files."""
    scanner = ModScanner()
    mod_files = scanner.scan(directory)

    # Calculate statistics
    total_size = sum(f.stat().st_size for f in mod_files)
    sizes = [f.stat().st_size for f in mod_files]

    packages = [f for f in mod_files if f.suffix == ".package"]
    scripts = [f for f in mod_files if f.suffix == ".ts4script"]

    # Find newest/oldest
    if mod_files:
        newest = max(mod_files, key=lambda f: f.stat().st_mtime)
        oldest = min(mod_files, key=lambda f: f.stat().st_mtime)
    else:
        newest = oldest = None

    return {
        "total_files": len(mod_files),
        "packages": len(packages),
        "scripts": len(scripts),
        "total_size": total_size,
        "total_size_mb": total_size / 1024 / 1024,
        "average_size": total_size / len(mod_files) if mod_files else 0,
        "largest_file": max(sizes) if sizes else 0,
        "smallest_file": min(sizes) if sizes else 0,
        "newest_file": newest.name if newest else None,
        "oldest_file": oldest.name if oldest else None,
    }

# Usage
stats = collect_statistics(Path("./mods"))
print(f"Total files: {stats['total_files']}")
print(f"Total size: {stats['total_size_mb']:.1f} MB")
print(f"Average size: {stats['average_size'] / 1024:.1f} KB")
```

## Error Handling

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner

try:
    scanner = ModScanner()
    mod_files = scanner.scan(Path("./mods"))

except FileNotFoundError:
    print("Directory not found")

except PermissionError:
    print("Permission denied")

except Exception as e:
    print(f"Unexpected error: {e}")
```

## Integration with Analyzer

The scanner integrates seamlessly with the analyzer:

```python
from pathlib import Path
from simanalysis.scanners.mod_scanner import ModScanner
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Scan for files
scanner = ModScanner()
mod_files = scanner.scan(Path("./mods"), extensions=[".package"])

# Analyze scanned files
analyzer = ModAnalyzer()
result = analyzer.analyze_files(mod_files)

print(f"Analyzed {len(result.mods)} package files")
```

## See Also

- [Mod Analyzer](../analyzers/mod_analyzer.md) - Analysis pipeline
- [Models](../models.md) - Data structures
- [Examples](../../examples/basic.md) - Usage examples

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
