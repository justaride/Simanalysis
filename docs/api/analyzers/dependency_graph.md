# Dependency Graph

Analyze and visualize mod dependency relationships using NetworkX.

## Overview

The Dependency Graph analyzer builds a directed graph of mod dependencies, detects circular dependencies, calculates optimal load order, and provides impact analysis for mod removal.

## Quick Example

```python
from pathlib import Path
from simanalysis.analyzers.dependency_graph import DependencyGraph
from simanalysis.analyzers.dependency_detector import DependencyDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Analyze mods
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Detect dependencies
detector = DependencyDetector()
all_deps = detector.detect_all_dependencies(result.mods)

# Build dependency graph
graph = DependencyGraph()
for mod in result.mods:
    deps = all_deps.get(mod.name, [])
    graph.add_mod(mod, dependencies=deps)

# Analyze
print(f"Has cycles: {graph.has_cycles()}")
print(f"Optimal load order: {graph.topological_sort()}")
```

## API Reference

::: simanalysis.analyzers.dependency_graph
    options:
      show_root_heading: true
      show_source: true
      members:
        - DependencyGraph
      group_by_category: true

## Core Features

### 1. Cycle Detection

Detect circular dependencies that prevent proper loading:

```python
graph = DependencyGraph()

# Add mods with circular dependency: A → B → C → A
graph.add_mod(mod_a, dependencies=["ModB.package"])
graph.add_mod(mod_b, dependencies=["ModC.package"])
graph.add_mod(mod_c, dependencies=["ModA.package"])

# Detect cycles
if graph.has_cycles():
    cycles = graph.detect_cycles()
    for cycle in cycles:
        print(f"Cycle detected: {' → '.join(cycle)}")
```

**Output:**
```
Cycle detected: ModA.package → ModB.package → ModC.package → ModA.package
```

### 2. Topological Sort (Load Order)

Generate optimal load order ensuring dependencies load before dependents:

```python
# Linear chain: A depends on B, B depends on C
graph = DependencyGraph()
graph.add_mod(mod_a, dependencies=["ModB.package"])
graph.add_mod(mod_b, dependencies=["ModC.package"])
graph.add_mod(mod_c, dependencies=None)

# Get optimal order
optimal_order = graph.topological_sort()
print(f"Load order: {optimal_order}")
# ['ModC.package', 'ModB.package', 'ModA.package']
```

**Rules:**
- Mods with no dependencies load first
- Dependencies always load before dependents
- Returns `None` if circular dependencies exist

### 3. Impact Analysis

Determine what breaks when removing a mod:

```python
# Analyze impact of removing ModC
impact = graph.impact_of_removal("ModC.package")

print(f"Mod: {impact['mod']}")
print(f"Will break: {impact['will_break']} mods")
print(f"Affected: {impact['affected_mods']}")
print(f"Recommendation: {impact['recommendation']}")
```

**Output:**
```
Mod: ModC.package
Will break: 2 mods
Affected: ['ModB.package', 'ModA.package']
Recommendation: ⚠️  CAUTION: 2 mods depend on this. Removing will break them!
```

### 4. Dependency Queries

Find dependencies and dependents of any mod:

```python
# Find all dependencies (transitive)
deps = graph.find_dependencies("ModA.package")
print(f"ModA depends on: {deps}")
# {'ModB.package', 'ModC.package'}

# Find all dependents (transitive)
dependents = graph.find_dependents("ModC.package")
print(f"Mods that depend on ModC: {dependents}")
# {'ModB.package', 'ModA.package'}
```

### 5. Load Order Issues

Detect issues in current load order:

```python
# Current load order
current_order = ["ModA.package", "ModB.package", "ModC.package"]

# Get issues
issues = graph.get_load_order_issues(current_order)

for issue in issues:
    print(f"[{issue['severity']}] {issue['mod']}")
    print(f"  {issue['reason']}")
    print(f"  Current: {issue['current_position']}, Should be: {issue['should_be_at']}")
```

**Output:**
```
[LOW] ModA.package
  Loads before its dependencies
  Current: 1, Should be: 3

[LOW] ModC.package
  Loads after its dependents
  Current: 3, Should be: 1
```

**Severity Levels:**
- **LOW**: Position difference ≤ 5
- **MEDIUM**: Position difference > 5 and ≤ 20
- **HIGH**: Position difference > 20

### 6. Missing Dependencies

Find dependencies that aren't installed:

```python
installed = {"ModA.package", "ModB.package"}  # Only A and B installed

missing = graph.find_missing_dependencies(installed)

for mod_name, dep_name in missing:
    print(f"{mod_name} requires {dep_name} (missing)")
```

**Output:**
```
ModB.package requires ModC.package (missing)
ModA.package requires ModC.package (missing)
```

### 7. Graph Statistics

Get comprehensive statistics:

```python
stats = graph.get_statistics()

print(f"Total mods: {stats['total_mods']}")
print(f"Dependencies: {stats['total_dependencies']}")
print(f"Has cycles: {stats['has_cycles']}")
print(f"Cycle count: {stats['cycle_count']}")
print(f"Isolated mods: {stats['isolated_mods']}")

# Most depended on mod
if stats['most_depended_on']:
    most_dep = stats['most_depended_on']
    print(f"Most depended on: {most_dep['mod']} ({most_dep['dependent_count']} mods)")
```

### 8. Visualization

#### ASCII Output

```python
print(graph.to_ascii())
```

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║                      DEPENDENCY GRAPH                          ║
╚════════════════════════════════════════════════════════════════╝

Total Mods: 3
Dependencies: 2
Circular Dependencies: No

Mods (sorted by dependency count):
  • ModC.package (depended on by 2 mods)
  • ModB.package (depends on 1 mod, depended on by 1 mod)
  • ModA.package (depends on 1 mod)

Dependency Relationships:
  ModA.package → ModB.package
  ModB.package → ModC.package
```

#### DOT Export

Export for Graphviz visualization:

```python
graph.export_dot(Path("dependencies.dot"))

# Convert to PNG using Graphviz:
# dot -Tpng dependencies.dot -o dependencies.png
```

## Usage Examples

### Example 1: Complete Dependency Analysis

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.dependency_detector import DependencyDetector
from simanalysis.analyzers.dependency_graph import DependencyGraph

# Step 1: Analyze mods
analyzer = ModAnalyzer(
    parse_tunings=True,
    parse_scripts=True,
)
result = analyzer.analyze_directory(Path("~/Mods"))

print(f"Found {len(result.mods)} mods")

# Step 2: Detect dependencies
detector = DependencyDetector()
all_deps = detector.detect_all_dependencies(result.mods)

print(f"{len(all_deps)} mods have dependencies")

# Step 3: Build graph
graph = DependencyGraph()
for mod in result.mods:
    deps = all_deps.get(mod.name, [])
    graph.add_mod(mod, dependencies=deps)

# Step 4: Analyze
stats = graph.get_statistics()
print(f"Total dependencies: {stats['total_dependencies']}")

if graph.has_cycles():
    print("⚠️  Circular dependencies detected!")
    for cycle in graph.detect_cycles():
        print(f"  {' → '.join(cycle)}")
else:
    print("✅ No circular dependencies")

    # Show optimal load order
    optimal = graph.topological_sort()
    print(f"\nOptimal load order ({len(optimal)} mods):")
    for i, mod_name in enumerate(optimal[:10], 1):
        print(f"  {i}. {mod_name}")
```

### Example 2: Check Before Removing Mod

```python
def safe_to_remove(graph: DependencyGraph, mod_name: str) -> bool:
    """Check if mod can be safely removed."""
    impact = graph.impact_of_removal(mod_name)

    print(f"\nRemoving {mod_name}:")
    print(f"  Will break: {impact['will_break']} mods")

    if impact['will_break'] > 0:
        print(f"  Affected mods:")
        for affected in impact['affected_mods']:
            print(f"    - {affected}")
        print(f"  {impact['recommendation']}")
        return False
    else:
        print(f"  {impact['recommendation']}")
        return True

# Usage
if safe_to_remove(graph, "OptionalMod.package"):
    # Safe to remove
    pass
else:
    print("⚠️  Removal will break other mods!")
```

### Example 3: Detect Load Order Problems

```python
def check_load_order(graph: DependencyGraph, current_order: List[str]):
    """Check current load order for issues."""
    issues = graph.get_load_order_issues(current_order)

    if not issues:
        print("✅ Load order is optimal!")
        return

    print(f"⚠️  Found {len(issues)} load order issues:")

    # Group by severity
    by_severity = {"HIGH": [], "MEDIUM": [], "LOW": []}
    for issue in issues:
        by_severity[issue["severity"]].append(issue)

    for severity in ["HIGH", "MEDIUM", "LOW"]:
        if by_severity[severity]:
            print(f"\n{severity} ({len(by_severity[severity])}):")
            for issue in by_severity[severity][:5]:
                print(f"  {issue['mod']}: {issue['reason']}")

# Usage
mods_in_order = [mod.name for mod in result.mods]
check_load_order(graph, mods_in_order)
```

### Example 4: Find Missing Dependencies

```python
def check_missing_dependencies(graph: DependencyGraph, installed_mods: Set[str]):
    """Check for missing dependencies."""
    missing = graph.find_missing_dependencies(installed_mods)

    if not missing:
        print("✅ All dependencies installed!")
        return

    print(f"⚠️  {len(missing)} missing dependencies:")

    # Group by mod
    by_mod = {}
    for mod_name, dep_name in missing:
        if mod_name not in by_mod:
            by_mod[mod_name] = []
        by_mod[mod_name].append(dep_name)

    for mod_name, deps in sorted(by_mod.items()):
        print(f"\n{mod_name} requires:")
        for dep in deps:
            print(f"  ✗ {dep}")

# Usage
installed = {mod.name for mod in result.mods}
check_missing_dependencies(graph, installed)
```

## Complex Scenarios

### Diamond Dependency

```python
# Structure:
#     A
#    / \
#   B   C
#    \ /
#     D

graph = DependencyGraph()
graph.add_mod(mod_a, dependencies=["ModB.package", "ModC.package"])
graph.add_mod(mod_b, dependencies=["ModD.package"])
graph.add_mod(mod_c, dependencies=["ModD.package"])
graph.add_mod(mod_d, dependencies=None)

# Still valid (no cycles)
assert graph.has_cycles() is False

# D must load first
order = graph.topological_sort()
assert order.index("ModD.package") < order.index("ModB.package")
assert order.index("ModD.package") < order.index("ModC.package")
```

### Large Graph Performance

The dependency graph efficiently handles large mod collections:

```python
# Test with 100 mods
graph = DependencyGraph()

for i in range(100):
    mod = Mod(...)
    deps = [f"Mod{i-1}.package"] if i > 0 else None
    graph.add_mod(mod, dependencies=deps)

# Fast operations even with large graphs
assert graph.graph.number_of_nodes() == 100
order = graph.topological_sort()  # < 1ms
```

## See Also

- [Dependency Detector](dependency_detector.md) - Detect dependencies from mods
- [Mod Analyzer](mod_analyzer.md) - Scan mods directory
- [CLI Usage](../../user-guide/cli-usage.md) - Using dependency commands
- [Understanding Conflicts](../../user-guide/understanding-conflicts.md) - Conflict types

---

**Version**: 3.1.0 | **Last Updated**: 2025-11-23
