# Dependency Analysis

Learn how to analyze mod dependencies, optimize load order, and avoid conflicts.

## What is Dependency Analysis?

Dependency analysis identifies which mods depend on other mods or game packs. This helps you:

- **Understand relationships:** See which mods require other mods
- **Optimize load order:** Ensure mods load in the correct sequence
- **Detect missing dependencies:** Find required mods that aren't installed
- **Prevent crashes:** Identify circular dependencies that cause issues

## Quick Start

### Basic Analysis

```bash
simanalysis dependencies ~/Mods
```

This will show:
- Total mods and dependency relationships
- Circular dependency warnings
- Most depended-on mods

### Verbose Analysis

```bash
simanalysis dependencies ~/Mods --verbose
```

Shows detailed information including:
- All mods with dependencies
- Load order analysis
- Missing dependencies
- ASCII visualization

### Show Load Order

```bash
simanalysis dependencies ~/Mods --show-load-order
```

Displays:
- Recommended load order
- Current order issues
- Severity ratings (HIGH, MEDIUM, LOW)

### Export Graph

```bash
simanalysis dependencies ~/Mods --output graph.dot
```

Exports dependency graph for visualization with Graphviz:

```bash
# Convert to PNG
dot -Tpng graph.dot -o graph.png

# Convert to SVG
dot -Tsvg graph.dot -o graph.svg
```

## Understanding Dependencies

### Types of Dependencies

#### 1. Pack Dependencies

Mods may require specific expansion packs, game packs, or stuff packs:

```
CustomCareer.package
  → Get to Work (EP01)
  → Discover University (EP08)
```

**Why it matters:** Without the required packs, the mod won't work properly.

#### 2. Mod Dependencies

Some mods build on functionality from other mods:

```
MCCCAddOn.package
  → MC Command Center
```

**Why it matters:** The dependent mod will crash or malfunction without the base mod.

#### 3. Injection Dependencies

Script mods may inject code into other mods:

```
MCCCEnhancer.ts4script
  → MC Command Center (injects into mccc.main)
```

**Why it matters:** Injection mods require the target mod to be present and loaded first.

### Circular Dependencies

A circular dependency occurs when mods depend on each other in a loop:

```
ModA → ModB → ModC → ModA
```

**Problems:**
- Impossible to determine correct load order
- Can cause infinite loops during loading
- May crash the game

**Solution:**
- Remove one of the conflicting mods
- Contact mod creators to resolve the issue
- Use alternative mods that don't conflict

## Load Order

### What is Load Order?

Load order determines the sequence in which mods are loaded. In The Sims 4:
- Files are loaded **alphabetically** by name
- Dependencies must load **before** the mods that need them
- Later-loading mods can override earlier ones

### Why It Matters

```
❌ Wrong Order:
1. CustomCareer.package (requires MCCC, loaded first)
2. MC_Command_Center.package (loaded second)
→ CustomCareer can't find MCCC → Error

✅ Correct Order:
1. MC_Command_Center.package (loaded first)
2. CustomCareer.package (loads after MCCC exists)
→ Works perfectly
```

### Optimizing Load Order

#### Method 1: Rename Files (Recommended)

Add prefixes to control load order:

```bash
# Before
ModA.package
ModB.package (depends on ModA)
ModC.package (depends on ModB)

# After (with prefixes)
01_ModA.package
02_ModB.package
03_ModC.package
```

**Naming conventions:**
- `00_` - Core dependencies (MCCC, Basemental, etc.)
- `01_-09_` - Add-ons and extensions
- `10_-99_` - Regular mods
- `zz_` - Overrides (should load last)

#### Method 2: Use Subdirectories

Organize mods into folders:

```
Mods/
├── 00_Core/
│   ├── MC_Command_Center.package
│   └── UI_Cheats.package
├── 01_AddOns/
│   ├── MCCC_Custom_Commands.package
│   └── Basemental_Addon.package
└── 02_Mods/
    └── Other_Mods.package
```

**Note:** The Sims 4 loads subdirectories alphabetically too.

### Load Order Issues

#### Severity Levels

**HIGH (Position difference > 20)**
```
⚠️  Critical order problem
Example: MCCC should load at position 1 but is at position 25
Action: Rename immediately
```

**MEDIUM (Position difference 6-20)**
```
⚠️  Noticeable order problem
Example: Dependency should load 12 positions earlier
Action: Rename when convenient
```

**LOW (Position difference ≤ 5)**
```
ℹ️  Minor order suboptimal
Example: Mod is 3 positions from ideal
Action: Optional optimization
```

## Common Scenarios

### Scenario 1: Installing a New Mod

```bash
# Check dependencies before installing
simanalysis dependencies ~/Mods --show-missing --verbose
```

**Workflow:**
1. Download new mod
2. Check what it requires
3. Install missing dependencies first
4. Add new mod
5. Verify load order

**Example:**
```
New mod: AdvancedCareer.package
Dependencies detected:
  → MC Command Center (not installed)
  → Get to Work (installed ✓)

Action: Install MCCC before AdvancedCareer
```

### Scenario 2: Removing a Mod

```bash
# Check impact before removing
simanalysis dependencies ~/Mods --verbose
```

**Workflow:**
1. Identify mod to remove
2. Check what depends on it
3. Decide whether to proceed
4. Remove dependent mods too, if needed

**Example:**
```
Removing: MC_Command_Center.package
Impact:
  Will break: 5 mods
  Affected:
    - MCCC_Custom_Commands.package
    - Career_Expansion.package
    - Enhanced_Traits.package
    - Custom_Aspirations.package
    - Better_Sims.package

Recommendation: ⚠️ CAUTION: 5 mods depend on this. Removing will break them!
```

### Scenario 3: Circular Dependency

```bash
simanalysis dependencies ~/Mods
```

**Output:**
```
⚠️  1 cycle(s) detected!
  Cycle 1: ModA.package → ModB.package → ModA.package
```

**Solutions:**
1. **Check mod descriptions:** May be intentional (rare)
2. **Remove one mod:** Break the cycle
3. **Update mods:** Newer versions may fix the issue
4. **Contact creators:** Report the circular dependency

### Scenario 4: Missing Dependencies

```bash
simanalysis dependencies ~/Mods --show-missing
```

**Output:**
```
⚠️  3 missing dependencies detected:
  AdvancedCareer.package → MC Command Center (missing)
  CustomTraits.package → Wonderful Whims (missing)
  EnhancedUI.package → UI Cheats Extension (missing)
```

**Action plan:**
1. Download missing mods
2. Install in correct order
3. Verify with another scan

## Advanced Usage

### Visualize Dependencies

Create visual dependency graph:

```bash
# Export graph
simanalysis dependencies ~/Mods --output dependencies.dot

# Convert to PNG with Graphviz
dot -Tpng dependencies.dot -o dependencies.png

# View image
open dependencies.png  # macOS
xdg-open dependencies.png  # Linux
start dependencies.png  # Windows
```

**Graph features:**
- Nodes represent mods
- Arrows show dependencies (A → B means "A depends on B")
- Clusters show related mods
- Colors indicate mod types

### Batch Checking Multiple Profiles

```bash
# Check main profile
simanalysis dependencies ~/Mods/Profile1 --output profile1.dot

# Check test profile
simanalysis dependencies ~/Mods/Profile2 --output profile2.dot

# Compare graphs visually
dot -Tpng profile1.dot -o profile1.png
dot -Tpng profile2.dot -o profile2.png
```

### Automated Load Order

```python
from pathlib import Path
from simanalysis.analyzers.dependency_graph import DependencyGraph
from simanalysis.analyzers.dependency_detector import DependencyDetector
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def generate_load_order_script(mods_dir):
    """Generate optimal load order and rename script."""
    # Analyze
    analyzer = ModAnalyzer(parse_tunings=True, parse_scripts=True)
    result = analyzer.analyze_directory(mods_dir)

    # Detect dependencies
    detector = DependencyDetector()
    all_deps = detector.detect_all_dependencies(result.mods)

    # Build graph
    graph = DependencyGraph()
    for mod in result.mods:
        deps = all_deps.get(mod.name, [])
        graph.add_mod(mod, dependencies=deps)

    # Get optimal order
    optimal = graph.topological_sort()

    if optimal is None:
        print("Cannot generate order: circular dependencies!")
        return

    # Generate rename commands
    for i, mod_name in enumerate(optimal, 1):
        new_name = f"{i:03d}_{mod_name}"
        print(f'mv "{mod_name}" "{new_name}"')

# Usage
generate_load_order_script(Path("~/Mods"))
```

## Best Practices

### 1. Regular Checks

Run dependency analysis:
- After installing new mods
- After updating existing mods
- Monthly as part of mod maintenance
- Before major game updates

### 2. Keep Dependencies Updated

```bash
# Check for dependency issues after updates
simanalysis dependencies ~/Mods --verbose
```

**Watch for:**
- Missing dependencies after mod updates
- New dependency requirements
- Changed load order needs

### 3. Document Your Setup

Create a dependency report:

```bash
simanalysis dependencies ~/Mods --verbose > my_mod_dependencies.txt
```

**Include in backup:**
- Dependency reports
- Load order documentation
- Mod list with versions

### 4. Test After Changes

```bash
# Before making changes
simanalysis dependencies ~/Mods --output before.dot

# After making changes
simanalysis dependencies ~/Mods --output after.dot

# Compare
diff before.dot after.dot
```

### 5. Use Meaningful Names

```bash
# Good names
00_MCCC_v2024.1.package
01_Basemental_Drugs.package
02_Custom_Career_Addon.package
zz_Override_Traits.package

# Bad names
ModA.package
New_Mod.package
Untitled.package
```

## Troubleshooting

### "Cannot determine optimal load order"

**Cause:** Circular dependencies detected

**Solution:**
1. Run with `--verbose` to see cycles
2. Identify mods in cycle
3. Remove one mod from cycle
4. Re-run analysis

### "Missing dependencies detected"

**Cause:** Required mods not installed

**Solution:**
1. Note which dependencies are missing
2. Download from official sources
3. Install in correct order
4. Verify with `--show-missing`

### "Mod loads in wrong position"

**Cause:** Alphabetical order doesn't match dependency order

**Solution:**
1. Use `--show-load-order` to see optimal order
2. Rename mods with numeric prefixes
3. Verify with another analysis

### "Graph export fails"

**Cause:** pydot or Graphviz not installed

**Solution:**
```bash
# Install pydot
pip install pydot

# Install Graphviz (system package)
# Ubuntu/Debian:
sudo apt-get install graphviz

# macOS:
brew install graphviz

# Windows: Download from graphviz.org
```

## See Also

- [CLI Usage](cli-usage.md) - Complete CLI reference
- [Understanding Conflicts](understanding-conflicts.md) - Conflict types
- [Dependency Graph API](../api/analyzers/dependency_graph.md) - Python API
- [Dependency Detector API](../api/analyzers/dependency_detector.md) - Detection API

---

**Version**: 3.1.0 | **Last Updated**: 2025-11-23
