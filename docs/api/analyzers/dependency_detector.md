# Dependency Detector

Automatically detect mod dependencies from tuning, scripts, and metadata.

## Overview

The Dependency Detector analyzes mods to identify their dependencies by examining:
- Pack requirements in tuning XML
- Script imports (popular mods like MCCC, Basemental, etc.)
- Injection decorators in script mods
- README/metadata files

## Quick Example

```python
from pathlib import Path
from simanalysis.analyzers.dependency_detector import DependencyDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze mods
analyzer = ModAnalyzer(parse_tunings=True, parse_scripts=True)
result = analyzer.analyze_directory(Path("./mods"))

# Detect dependencies
detector = DependencyDetector()
all_deps = detector.detect_all_dependencies(result.mods)

# Display results
for mod_name, deps in all_deps.items():
    print(f"{mod_name}:")
    for dep in deps:
        print(f"  → {dep}")
```

## API Reference

::: simanalysis.analyzers.dependency_detector
    options:
      show_root_heading: true
      show_source: true
      members:
        - DependencyDetector
      group_by_category: true

## Detection Methods

### 1. Pack Requirements

Detects expansion packs, game packs, and stuff packs required by mods:

```python
detector = DependencyDetector()

# Mod with pack requirements
deps = detector.detect_dependencies(mod)
# ['Get to Work', 'Cats & Dogs', 'Seasons']
```

**Supported Packs:**
- 14+ Expansion Packs (EP01-EP14)
- 12+ Game Packs (GP01-GP12)
- 19+ Stuff Packs (SP01-SP19)

**Example tuning XML:**
```xml
<T n="pack_requirements">EP01,GP04,SP13</T>
```

### 2. Script Dependencies

Detects dependencies from Python imports in script mods:

```python
detector = DependencyDetector()

# Script mod with imports
deps = detector.detect_dependencies(script_mod)
# ['MC Command Center', 'Wonderful Whims']
```

**Supported Mods:**
- MC Command Center (MCCC)
- Basemental Drugs
- Wonderful Whims / WickedWhims
- UI Cheats Extension
- Better Exceptions
- Slice of Life
- Extreme Violence
- And more...

**Example Python code:**
```python
import mccc_module
from basemental import drugs
from wonderfulwhims.core import Manager
```

### 3. Injection Dependencies

Detects dependencies from code injection patterns:

```python
detector = DependencyDetector()
deps = detector.detect_dependencies(mod)
# ['MC Command Center']  # From @inject_to(mccc.main)
```

**Detected patterns:**
```python
@inject_to(mccc.main, 'execute')
def my_function():
    pass

@inject(target_class=wickedwhims.core.Manager)
def patched_method():
    pass
```

### 4. README Dependencies

Detects dependencies declared in README files:

```python
detector = DependencyDetector()
deps = detector.detect_dependencies(mod)
# ['MC Command Center', 'UI Cheats Extension']
```

**Detected patterns:**
- `Requires: MC Command Center v2024.1+`
- `Dependencies: Wonderful Whims, Basemental Drugs`
- `Depends on: UI Cheats Extension and Better Exceptions`
- `Needs: MCCC`

**Features:**
- Strips version numbers automatically
- Handles comma and "and" separators
- Case-insensitive matching

## Usage Examples

### Example 1: Single Mod Analysis

```python
from simanalysis.analyzers.dependency_detector import DependencyDetector

detector = DependencyDetector()

# Analyze one mod
deps = detector.detect_dependencies(my_mod)

if deps:
    print(f"{my_mod.name} requires:")
    for dep in deps:
        print(f"  - {dep}")
else:
    print(f"{my_mod.name} has no dependencies")
```

### Example 2: Batch Analysis

```python
detector = DependencyDetector()

# Analyze all mods at once
all_deps = detector.detect_all_dependencies(mods)

# Show only mods with dependencies
for mod_name, deps in sorted(all_deps.items()):
    print(f"\n{mod_name}:")
    for dep in deps:
        print(f"  → {dep}")

print(f"\nTotal: {len(all_deps)} mods have dependencies")
```

### Example 3: Filter by Dependency Type

```python
detector = DependencyDetector()

def categorize_dependencies(mod):
    """Categorize dependencies by type."""
    pack_deps = detector._detect_pack_requirements(mod)
    script_deps = detector._detect_script_dependencies(mod)

    return {
        "packs": list(pack_deps),
        "mods": list(script_deps),
    }

# Usage
categories = categorize_dependencies(my_mod)
print(f"Pack requirements: {categories['packs']}")
print(f"Mod dependencies: {categories['mods']}")
```

### Example 4: Find Mods Requiring Specific Pack

```python
detector = DependencyDetector()
all_deps = detector.detect_all_dependencies(mods)

def find_mods_requiring_pack(all_deps, pack_name):
    """Find mods that require a specific pack."""
    requiring_mods = []
    for mod_name, deps in all_deps.items():
        if pack_name in deps:
            requiring_mods.append(mod_name)
    return requiring_mods

# Find mods requiring "Get to Work"
get_to_work_mods = find_mods_requiring_pack(all_deps, "Get to Work")
print(f"{len(get_to_work_mods)} mods require Get to Work:")
for mod in get_to_work_mods:
    print(f"  - {mod}")
```

### Example 5: Detect Missing Popular Mods

```python
detector = DependencyDetector()
all_deps = detector.detect_all_dependencies(mods)

# Popular mods that other mods depend on
popular_mods = set()
for deps in all_deps.values():
    for dep in deps:
        if dep in detector.KNOWN_MODS.values():
            popular_mods.add(dep)

# Installed popular mods
installed = {mod.name for mod in mods}

# Find which popular mods are referenced but not installed
missing_popular = popular_mods - installed

if missing_popular:
    print("⚠️  Referenced but not installed:")
    for mod_name in sorted(missing_popular):
        print(f"  - {mod_name}")
```

## Known Mods Database

The detector includes a database of popular mods:

```python
detector = DependencyDetector()

# View all known mods
for key, mod_name in detector.KNOWN_MODS.items():
    print(f"{key}: {mod_name}")
```

**Included Mods:**
- MC Command Center (mccc, mc_cmd_center)
- Basemental Drugs (basemental)
- Wonderful Whims (wonderfulwhims)
- WickedWhims (wickedwhims)
- UI Cheats Extension (ui_cheats)
- Better Exceptions (better_exceptions)
- TwistedMexi's Better BuildBuy (tmex)
- Go to School Mod (go_to_school)
- Slice of Life (slice_of_life)
- Extreme Violence (extreme_violence)
- Life's Tragedies (life_tragedies)

## Pack Database

All expansion packs, game packs, and stuff packs are supported:

```python
detector = DependencyDetector()

# View all packs
for code, pack_name in detector.PACK_NAMES.items():
    print(f"{code}: {pack_name}")
```

**Examples:**
- EP01: Get to Work
- EP04: Cats & Dogs
- EP08: Discover University
- GP04: Vampires
- SP13: Laundry Day Stuff

## Custom Detection

Extend the detector with custom logic:

```python
from simanalysis.analyzers.dependency_detector import DependencyDetector

class CustomDetector(DependencyDetector):
    """Custom detector with additional mods."""

    def __init__(self):
        super().__init__()

        # Add custom mods
        self.KNOWN_MODS.update({
            "my_custom_mod": "My Custom Mod Name",
            "another_mod": "Another Mod",
        })

    def detect_dependencies(self, mod):
        """Override to add custom detection logic."""
        deps = super().detect_dependencies(mod)

        # Add custom logic
        if "special_keyword" in mod.name.lower():
            deps.append("Special Dependency")

        return deps

# Usage
detector = CustomDetector()
deps = detector.detect_dependencies(mod)
```

## Performance

The detector is optimized for batch processing:

```python
import time
from simanalysis.analyzers.dependency_detector import DependencyDetector

detector = DependencyDetector()

start = time.time()
all_deps = detector.detect_all_dependencies(mods)  # 100 mods
duration = time.time() - start

print(f"Analyzed {len(mods)} mods in {duration:.2f}s")
# ~0.1-0.5s for 100 mods
```

## Limitations

**Pack Detection:**
- Only detects packs explicitly declared in tuning XML
- Cannot detect packs required by CAS items or build objects

**Script Detection:**
- Only detects imports from known popular mods
- Cannot detect dependencies from dynamically loaded modules
- Requires mod to be a valid .ts4script file

**Injection Detection:**
- Only detects common injection decorator patterns
- Cannot detect runtime modifications
- Requires valid Python syntax

**README Detection:**
- Only detects dependencies in specific formats
- Cannot parse natural language descriptions
- Requires README file in script mod

## See Also

- [Dependency Graph](dependency_graph.md) - Build dependency graphs
- [Script Analyzer](../parsers/script.md) - Analyze script mods
- [Tuning Parser](../parsers/tuning.md) - Parse tuning XML
- [CLI Usage](../../user-guide/cli-usage.md) - Using dependency commands

---

**Version**: 3.1.0 | **Last Updated**: 2025-11-23
