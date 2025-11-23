# Resource Conflicts Detector

Detect conflicts in DBPF resources where multiple mods use identical resource hashes.

## Overview

The Resource Conflict Detector identifies when two or more mods contain resources (textures, meshes, etc.) with the same hash value. This indicates that one resource will overwrite the other, potentially causing visual or functional issues.

## Quick Example

```python
from pathlib import Path
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze mods
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Detect resource conflicts
detector = ResourceConflictDetector()
conflicts = detector.detect(result.mods)

print(f"Found {len(conflicts)} resource conflicts")
for conflict in conflicts:
    print(f"  Hash {conflict.resource_hash}: {len(conflict.affected_mods)} mods")
```

## API Reference

::: simanalysis.detectors.resource_conflicts
    options:
      show_root_heading: true
      show_source: true
      members:
        - ResourceConflictDetector
      group_by_category: true

## Conflict Detection Logic

1. **Resource Indexing**: Maps resource hash → [mods containing it]
2. **Collision Detection**: Finds hashes present in multiple mods
3. **Type Analysis**: Checks resource types for severity
4. **Conflict Creation**: Generates detailed conflict reports

## Severity Levels

| Severity | Condition | Example |
|----------|-----------|---------|
| HIGH | Critical resources | UI elements, core textures |
| MEDIUM | Common resources | Clothing, objects |
| LOW | Minor resources | Recolors, variations |

## Usage Examples

### Example 1: Find Resource Collisions

```python
from pathlib import Path
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

detector = ResourceConflictDetector()
conflicts = detector.detect(result.mods)

for conflict in conflicts:
    print(f"\n[{conflict.severity}] Resource collision")
    print(f"  Hash: {conflict.resource_hash}")
    print(f"  Type: {conflict.resource_type}")
    print("  Affected mods:")
    for mod_path in conflict.affected_mods:
        print(f"    - {Path(mod_path).name}")
```

### Example 2: Group by Resource Type

```python
from collections import defaultdict

detector = ResourceConflictDetector()
conflicts = detector.detect(result.mods)

by_type = defaultdict(list)
for conflict in conflicts:
    by_type[conflict.resource_type].append(conflict)

print("Conflicts by resource type:")
for res_type, group in sorted(by_type.items()):
    print(f"  Type {res_type:08X}: {len(group)} conflicts")
```

## See Also

- [Base Detector](base.md) - Detector interface
- [Tuning Conflicts](tuning_conflicts.md) - Tuning conflict detection
- [DBPF Parser](../parsers/dbpf.md) - Resource parsing
- [Understanding Conflicts](../../user-guide/understanding-conflicts.md) - Conflict guide

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
