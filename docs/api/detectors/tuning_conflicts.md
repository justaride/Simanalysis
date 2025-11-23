# Tuning Conflicts Detector

Detect conflicts in XML tuning files where multiple mods modify the same tuning instance.

## Overview

The Tuning Conflict Detector identifies when two or more mods contain tuning files with identical instance IDs. This indicates that only one mod's version will be used by the game, potentially breaking features from the other mod(s).

## Quick Example

```python
from pathlib import Path
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze mods
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Detect tuning conflicts
detector = TuningConflictDetector()
conflicts = detector.detect(result.mods)

print(f"Found {len(conflicts)} tuning conflicts")
for conflict in conflicts:
    print(f"  Instance {conflict.instance_id}: {len(conflict.affected_mods)} mods")
```

## API Reference

::: simanalysis.detectors.tuning_conflicts
    options:
      show_root_heading: true
      show_source: true
      members:
        - TuningConflictDetector
      group_by_category: true

## Conflict Detection Logic

The detector works as follows:

1. **Index Building**: Creates a map of instance_id → [mods containing it]
2. **Conflict Identification**: Finds instance IDs present in multiple mods
3. **Severity Calculation**: Determines severity based on conflict characteristics
4. **Result Generation**: Creates ModConflict objects with details

## Severity Levels

| Severity | Condition | Example |
|----------|-----------|---------|
| CRITICAL | Core game tunings modified | Sim aging, basic needs |
| HIGH | Multiple essential mods conflict | Two popular overhaul mods |
| MEDIUM | Minor feature conflicts | Similar trait modifications |
| LOW | Compatible modifications | Recolor or value tweaks |

## Usage Examples

### Example 1: Find All Tuning Conflicts

```python
from pathlib import Path
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

detector = TuningConflictDetector()
conflicts = detector.detect(result.mods)

for conflict in conflicts:
    print(f"\n[{conflict.severity}] {conflict.description}")
    print("Affected mods:")
    for mod_path in conflict.affected_mods:
        print(f"  - {Path(mod_path).name}")
```

### Example 2: Filter by Severity

```python
detector = TuningConflictDetector()
conflicts = detector.detect(result.mods)

# Only critical and high
important = [
    c for c in conflicts
    if c.severity in ["CRITICAL", "HIGH"]
]

print(f"Important conflicts: {len(important)}/{len(conflicts)}")
```

### Example 3: Group by Instance ID

```python
from collections import defaultdict

detector = TuningConflictDetector()
conflicts = detector.detect(result.mods)

by_instance = defaultdict(list)
for conflict in conflicts:
    by_instance[conflict.instance_id].append(conflict)

print("Conflicts by instance:")
for instance_id, group in sorted(by_instance.items()):
    print(f"  {instance_id}: {len(group)} conflicts")
```

## See Also

- [Base Detector](base.md) - Detector interface
- [Resource Conflicts](resource_conflicts.md) - Resource conflict detection
- [Tuning Parser](../parsers/tuning.md) - Tuning parsing
- [Understanding Conflicts](../../user-guide/understanding-conflicts.md) - Conflict guide

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
