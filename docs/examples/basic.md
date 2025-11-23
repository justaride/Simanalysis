# Basic Examples

Practical examples for getting started with Simanalysis.

## Prerequisites

Install Simanalysis:

```bash
pip install simanalysis
```

Or use Docker:

```bash
docker pull simanalysis:latest
```

## Command-Line Examples

### Example 1: Analyze Your Mods Folder

The simplest use case:

```bash
simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods
```

**What it does:**
- Scans for all .package and .ts4script files
- Parses each mod file
- Detects conflicts
- Displays report in terminal

**Expected output:**
```
🔍 Scanning for mods...
Found 47 mods in /path/to/Mods

📦 Analyzing packages...
[████████████████████] 47/47 100%

=== MOD ANALYSIS REPORT ===

Total Mods: 47
Total Conflicts: 3
...
```

### Example 2: Export to JSON

Save the report for later:

```bash
simanalysis analyze ./mods --output report.json
```

**View the JSON:**
```bash
cat report.json | jq .
```

**Use case:** Save reports for tracking changes over time.

### Example 3: Quiet Mode

No console output, only export:

```bash
simanalysis analyze ./mods --quiet --output report.json
echo "Analysis complete! Check report.json"
```

**Use case:** Automation scripts where console output is noise.

### Example 4: Analyze Only Packages

Focus on .package files:

```bash
simanalysis analyze ./mods --extensions .package --output packages_report.json
```

**Use case:** Isolate tuning conflicts from script conflicts.

### Example 5: Interactive TUI Mode

Launch the text-based interface:

```bash
simanalysis analyze ./mods --tui
```

**Controls:**
- ↑↓: Navigate
- Enter: View details
- q: Quit
- f: Filter by severity

**Use case:** Explore conflicts interactively before resolving.

### Example 6: Debug Logging

Enable detailed logging for troubleshooting:

```bash
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log
```

**View log:**
```bash
tail -f debug.log
```

**Use case:** Debugging issues with specific mod files.

## Python API Examples

### Example 1: Simple Analysis

Analyze a directory programmatically:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Create analyzer
analyzer = ModAnalyzer()

# Analyze directory
mods_dir = Path.home() / "Documents" / "Electronic Arts" / "The Sims 4" / "Mods"
result = analyzer.analyze_directory(mods_dir)

# Display results
print(f"Found {len(result.mods)} mods")
print(f"Found {len(result.conflicts)} conflicts")

# Show conflicts
for conflict in result.conflicts:
    print(f"  [{conflict.severity}] {conflict.description}")
```

**Output:**
```
Found 47 mods
Found 3 conflicts
  [HIGH] Tuning conflict: Multiple mods modify instance 0x12345678
  [MEDIUM] Resource conflict: Hash collision 0xABCDEF01
  [MEDIUM] Resource conflict: Hash collision 0x12AB34CD
```

### Example 2: Parse a Single Mod

Read and parse one .package file:

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader

# Open package
mod_path = Path("./mods/AwesomeMod.package")
reader = DBPFReader(mod_path)

# Read header
header = reader.read_header()
print(f"DBPF Version: {header.major_version}.{header.minor_version}")
print(f"Resources: {header.index_count}")

# Read index
resources = reader.read_index()
print(f"Loaded {len(resources)} resources")

# Extract first resource
if resources:
    data = reader.get_resource(resources[0])
    print(f"First resource: {len(data)} bytes")
```

**Output:**
```
DBPF Version: 2.1
Resources: 45
Loaded 45 resources
First resource: 4096 bytes
```

### Example 3: Filter Conflicts by Severity

Process only high-severity conflicts:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Filter high severity
high_conflicts = [
    c for c in result.conflicts
    if c.severity in ["HIGH", "CRITICAL"]
]

print(f"Found {len(high_conflicts)} high-severity conflicts:")
for conflict in high_conflicts:
    print(f"\n[{conflict.severity}] {conflict.description}")
    print("Affected mods:")
    for mod_path in conflict.affected_mods:
        print(f"  - {Path(mod_path).name}")
```

**Output:**
```
Found 1 high-severity conflicts:

[HIGH] Tuning conflict: Multiple mods modify instance 0x12345678
Affected mods:
  - AwesomeMod.package
  - BetterMod.package
```

### Example 4: Export to JSON

Save analysis results to JSON:

```python
import json
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Convert to dict for JSON serialization
data = {
    "metadata": {
        "scan_directory": str(result.scan_directory),
        "total_mods": len(result.mods),
    },
    "mods": [
        {
            "name": mod.name,
            "path": str(mod.path),
            "size": mod.size,
            "type": mod.mod_type,
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

# Save to JSON
output_path = Path("report.json")
with open(output_path, "w") as f:
    json.dump(data, f, indent=2)

print(f"Report saved to {output_path}")
```

### Example 5: Get Mod Statistics

Calculate statistics about your mod collection:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()
result = analyzer.analyze_directory(Path("./mods"))

# Calculate statistics
total_size = sum(mod.size for mod in result.mods)
total_resources = sum(len(mod.resources) for mod in result.mods)

package_mods = [m for m in result.mods if m.mod_type == "package"]
script_mods = [m for m in result.mods if m.mod_type == "script"]

print("=== MOD COLLECTION STATISTICS ===")
print(f"Total Mods: {len(result.mods)}")
print(f"  - Package mods: {len(package_mods)}")
print(f"  - Script mods: {len(script_mods)}")
print(f"Total Size: {total_size / 1024 / 1024:.1f} MB")
print(f"Total Resources: {total_resources}")
print(f"Average mod size: {total_size / len(result.mods) / 1024:.1f} KB")

# Largest mods
print("\nTop 5 Largest Mods:")
sorted_mods = sorted(result.mods, key=lambda m: m.size, reverse=True)
for i, mod in enumerate(sorted_mods[:5], 1):
    print(f"  {i}. {mod.name} - {mod.size / 1024 / 1024:.2f} MB")
```

**Output:**
```
=== MOD COLLECTION STATISTICS ===
Total Mods: 47
  - Package mods: 42
  - Script mods: 5
Total Size: 45.2 MB
Total Resources: 2847
Average mod size: 985.2 KB

Top 5 Largest Mods:
  1. MegaMod.package - 8.54 MB
  2. ComplexMod.package - 6.23 MB
  3. LargeMod.package - 4.89 MB
  4. BigMod.ts4script - 3.45 MB
  5. HugeMod.package - 2.98 MB
```

### Example 6: Compare Two Directories

Compare two mod collections:

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

analyzer = ModAnalyzer()

# Analyze two collections
collection1 = analyzer.analyze_directory(Path("./mods/collection1"))
collection2 = analyzer.analyze_directory(Path("./mods/collection2"))

# Compare
print("=== COLLECTION COMPARISON ===")
print(f"Collection 1: {len(collection1.mods)} mods, {len(collection1.conflicts)} conflicts")
print(f"Collection 2: {len(collection2.mods)} mods, {len(collection2.conflicts)} conflicts")

# Find mods in common (by name)
names1 = {mod.name for mod in collection1.mods}
names2 = {mod.name for mod in collection2.mods}

common = names1 & names2
only_in_1 = names1 - names2
only_in_2 = names2 - names1

print(f"\nMods in both: {len(common)}")
print(f"Only in collection 1: {len(only_in_1)}")
print(f"Only in collection 2: {len(only_in_2)}")

if only_in_1:
    print("\nMods only in collection 1:")
    for name in sorted(only_in_1)[:5]:
        print(f"  - {name}")
```

## Real-World Workflows

### Workflow 1: Before Game Session

Check for issues before playing:

```bash
#!/bin/bash
# check_mods.sh

echo "Checking mods for conflicts..."
simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods \
    --quiet --output pregame_check.json

# Count critical conflicts
critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' pregame_check.json)

if [ $critical -gt 0 ]; then
    echo "⚠️  WARNING: Found $critical critical conflicts!"
    echo "Review pregame_check.json before playing."
    exit 1
else
    echo "✅ No critical conflicts. Safe to play!"
    exit 0
fi
```

**Usage:**
```bash
chmod +x check_mods.sh
./check_mods.sh
```

### Workflow 2: After Adding Mods

Detect new conflicts after mod installation:

```bash
#!/bin/bash
# detect_new_conflicts.sh

MODS_DIR=~/Documents/"Electronic Arts"/"The Sims 4"/Mods
BASELINE=baseline.json
CURRENT=current.json

# Create baseline if not exists
if [ ! -f "$BASELINE" ]; then
    echo "Creating baseline..."
    simanalysis analyze "$MODS_DIR" --quiet --output "$BASELINE"
    echo "Baseline created. Run again after adding mods."
    exit 0
fi

# Analyze current state
echo "Analyzing current mods..."
simanalysis analyze "$MODS_DIR" --quiet --output "$CURRENT"

# Compare
baseline_count=$(jq '.conflicts | length' "$BASELINE")
current_count=$(jq '.conflicts | length' "$CURRENT")

echo "Conflicts:"
echo "  Before: $baseline_count"
echo "  After: $current_count"
echo "  Change: $((current_count - baseline_count))"

if [ $current_count -gt $baseline_count ]; then
    echo ""
    echo "⚠️  New conflicts detected!"
    echo "Review $CURRENT for details"
else
    echo ""
    echo "✅ No new conflicts"
fi
```

### Workflow 3: Monthly Maintenance

Track mod collection health over time:

```python
# monthly_maintenance.py
import json
from datetime import datetime
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Paths
mods_dir = Path.home() / "Documents" / "Electronic Arts" / "The Sims 4" / "Mods"
reports_dir = Path("reports")
reports_dir.mkdir(exist_ok=True)

# Analyze
print("Performing monthly maintenance analysis...")
analyzer = ModAnalyzer()
result = analyzer.analyze_directory(mods_dir)

# Create report
timestamp = datetime.now()
report = {
    "timestamp": timestamp.isoformat(),
    "total_mods": len(result.mods),
    "total_conflicts": len(result.conflicts),
    "conflicts_by_severity": {},
}

# Count by severity
for conflict in result.conflicts:
    severity = conflict.severity
    report["conflicts_by_severity"][severity] = \
        report["conflicts_by_severity"].get(severity, 0) + 1

# Save monthly report
filename = f"report_{timestamp.strftime('%Y-%m-%d')}.json"
report_path = reports_dir / filename
with open(report_path, "w") as f:
    json.dump(report, f, indent=2)

print(f"Report saved to {report_path}")

# Load trend data
trends_file = reports_dir / "trends.json"
if trends_file.exists():
    with open(trends_file) as f:
        trends = json.load(f)
else:
    trends = []

trends.append(report)

# Save trends
with open(trends_file, "w") as f:
    json.dump(trends, f, indent=2)

# Display trend
print("\n=== TREND ANALYSIS ===")
print(f"{'Date':<12} {'Mods':<6} {'Conflicts':<10}")
print("-" * 30)
for entry in trends[-12:]:  # Last 12 months
    date = entry['timestamp'][:10]
    mods = entry['total_mods']
    conflicts = entry['total_conflicts']
    print(f"{date:<12} {mods:<6} {conflicts:<10}")
```

**Run monthly:**
```bash
python monthly_maintenance.py
```

### Workflow 4: Bulk Analysis

Analyze multiple mod collections:

```python
# bulk_analyze.py
import json
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Collections to analyze
collections = {
    "gameplay": Path("./mods/gameplay"),
    "cas": Path("./mods/cas"),
    "build_buy": Path("./mods/build_buy"),
    "scripts": Path("./mods/scripts"),
}

analyzer = ModAnalyzer()
results = {}

print("Analyzing mod collections...")
for name, path in collections.items():
    print(f"  - {name}...")
    result = analyzer.analyze_directory(path)
    results[name] = {
        "mods": len(result.mods),
        "conflicts": len(result.conflicts),
        "high_severity": sum(
            1 for c in result.conflicts
            if c.severity in ["HIGH", "CRITICAL"]
        ),
    }

# Display summary
print("\n=== COLLECTION SUMMARY ===")
print(f"{'Collection':<15} {'Mods':<6} {'Conflicts':<10} {'High Severity':<15}")
print("-" * 50)
for name, stats in results.items():
    print(f"{name:<15} {stats['mods']:<6} {stats['conflicts']:<10} {stats['high_severity']:<15}")

# Save report
with open("bulk_report.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nReport saved to bulk_report.json")
```

## Tips and Best Practices

### Tip 1: Start Simple

Begin with console output before exporting:

```bash
# First run
simanalysis analyze ./mods

# Review output, then export
simanalysis analyze ./mods --output report.json
```

### Tip 2: Use Quiet Mode for Automation

Always use `--quiet` in scripts:

```bash
simanalysis analyze ./mods --quiet --output report.json
```

### Tip 3: Filter by Severity

Focus on critical issues first:

```bash
jq '.conflicts[] | select(.severity == "CRITICAL" or .severity == "HIGH")' report.json
```

### Tip 4: Keep Historical Reports

Archive reports to track changes:

```bash
mkdir -p reports
simanalysis analyze ./mods --output "reports/$(date +%Y%m%d).json"
```

### Tip 5: Test After Resolving

Always re-analyze after fixing conflicts:

```bash
# Remove problematic mod
rm ./mods/ProblematicMod.package

# Verify conflict resolved
simanalysis analyze ./mods --output fixed.json
jq '.conflicts | length' fixed.json
```

## Next Steps

- Explore [Advanced Examples](advanced.md) for complex use cases
- Learn about [CI/CD Integration](cicd.md) for automation
- Read the [API Reference](../api/overview.md) for more details
- Check [User Guide](../user-guide/analyzing-mods.md) for comprehensive documentation

## Getting Help

- Check [Troubleshooting](../user-guide/troubleshooting.md) for common issues
- Review [USAGE_EXAMPLES.md](../../USAGE_EXAMPLES.md) for more examples
- Visit [GitHub Issues](https://github.com/justaride/Simanalysis/issues) for support

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
