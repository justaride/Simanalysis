# Simanalysis Usage Examples

This guide provides practical examples for using Simanalysis to analyze Sims 4 mods.

## Table of Contents

- [Quick Start](#quick-start)
- [Basic Analysis](#basic-analysis)
- [Advanced Analysis](#advanced-analysis)
- [Working with Reports](#working-with-reports)
- [Troubleshooting](#troubleshooting)
- [Integration with Development Workflow](#integration-with-development-workflow)

## Quick Start

### Installation

```bash
pip install simanalysis
```

### First Analysis

```bash
# Analyze your Mods folder
simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods

# Or use a relative path
simanalysis analyze ./mods

# Analyze with verbose output
simanalysis analyze ./mods --verbose
```

## Basic Analysis

### Analyze a Single Mod

```bash
# Analyze one .package file
simanalysis analyze my_custom_mod.package

# Show detailed information
simanalysis analyze my_custom_mod.package --verbose
```

### Analyze a Directory (Non-Recursive)

```bash
# Only analyze files in the specified directory (don't scan subdirectories)
simanalysis analyze ./mods --no-recursive
```

### Filter by File Type

```bash
# Only analyze .package files
simanalysis analyze ./mods --extensions .package

# Only analyze script mods
simanalysis analyze ./mods --extensions .ts4script

# Analyze both packages and scripts
simanalysis analyze ./mods --extensions .package .ts4script
```

## Advanced Analysis

### With Logging

```bash
# Enable debug logging to console
simanalysis analyze ./mods --log-level DEBUG

# Save logs to a file
simanalysis analyze ./mods --log-file analysis.log

# Debug logging with file output
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log

# Quiet mode (no console output, only file logging)
simanalysis analyze ./mods --quiet --log-file silent.log
```

### Export Analysis Results

```bash
# Export to JSON
simanalysis analyze ./mods --output report.json --format json

# Export to TXT (human-readable)
simanalysis analyze ./mods --output report.txt --format txt

# Export to YAML
simanalysis analyze ./mods --output report.yaml --format yaml
```

### Conflict-Focused Analysis

```bash
# Show only high-severity conflicts
simanalysis analyze ./mods | grep "HIGH"

# Export conflicts to JSON for processing
simanalysis analyze ./mods --output conflicts.json --format json
python3 << 'EOF'
import json
with open('conflicts.json') as f:
    data = json.load(f)
    high_conflicts = [c for c in data['conflicts'] if c['severity'] == 'HIGH']
    print(f"Found {len(high_conflicts)} high-severity conflicts")
EOF
```

## Working with Reports

### Understanding JSON Output

```python
import json

# Load analysis results
with open('report.json') as f:
    analysis = json.load(f)

# Print summary
print(f"Total mods: {len(analysis['mods'])}")
print(f"Total conflicts: {len(analysis['conflicts'])}")
print(f"Summary: {analysis['summary']}")

# List all conflicts
for conflict in analysis['conflicts']:
    print(f"{conflict['severity']}: {conflict['description']}")
    print(f"  Affected mods: {', '.join(conflict['affected_mods'])}")
    print()

# Find specific mod
for mod in analysis['mods']:
    if 'my_mod' in mod['name'].lower():
        print(f"Found: {mod['name']}")
        print(f"  Resources: {mod['resource_count']}")
        print(f"  Size: {mod['size']} bytes")
        print(f"  Hash: {mod['hash']}")
```

### Filter Conflicts by Type

```python
import json

with open('report.json') as f:
    analysis = json.load(f)

# Group conflicts by type
conflict_types = {}
for conflict in analysis['conflicts']:
    ctype = conflict['type']
    if ctype not in conflict_types:
        conflict_types[ctype] = []
    conflict_types[ctype].append(conflict)

# Print summary
for ctype, conflicts in conflict_types.items():
    print(f"{ctype}: {len(conflicts)} conflicts")
    for c in conflicts:
        print(f"  - {c['description'][:80]}...")
```

## Troubleshooting

### Debugging Failed Parses

```bash
# Enable debug logging to see parsing errors
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log

# Check the log file for errors
grep ERROR debug.log
```

### Common Error Messages

**"File too small: expected at least 96 bytes"**
- The file is corrupted or incomplete
- Solution: Re-download the mod

**"Invalid DBPF magic"**
- The file is not a valid .package file
- Solution: Verify file integrity, check if it's the correct file type

**"File is not a valid ZIP archive"**
- The .ts4script file is corrupted
- Solution: Re-download the script mod

**"Invalid XML syntax"**
- The tuning XML inside the package is malformed
- Solution: Contact mod author, or try re-downloading

### Performance Optimization

```bash
# For large mod collections, disable recursive scanning
simanalysis analyze ./mods --no-recursive

# Analyze only .package files (skip scripts)
simanalysis analyze ./mods --extensions .package

# Use quiet mode for faster processing
simanalysis analyze ./mods --quiet --output report.json
```

## Integration with Development Workflow

### Pre-Release Mod Testing

```bash
#!/bin/bash
# test_mod.sh - Test mod before release

MOD_FILE=$1

echo "Analyzing $MOD_FILE..."
simanalysis analyze "$MOD_FILE" --output test_report.json --format json

# Check for conflicts
python3 << 'EOF'
import json, sys

with open('test_report.json') as f:
    report = json.load(f)

high_conflicts = [c for c in report['conflicts'] if c['severity'] == 'HIGH']
critical_conflicts = [c for c in report['conflicts'] if c['severity'] == 'CRITICAL']

if critical_conflicts:
    print(f"❌ CRITICAL: Found {len(critical_conflicts)} critical conflicts!")
    sys.exit(1)
elif high_conflicts:
    print(f"⚠️  WARNING: Found {len(high_conflicts)} high-severity conflicts")
    sys.exit(1)
else:
    print("✅ No critical conflicts detected")
    sys.exit(0)
EOF

if [ $? -eq 0 ]; then
    echo "✅ Mod passed analysis!"
else
    echo "❌ Mod has conflicts - review test_report.json"
    exit 1
fi
```

### Automated Conflict Detection for Mod Collections

```python
#!/usr/bin/env python3
"""
check_collection.py - Analyze a mod collection and report conflicts
"""

import json
import subprocess
import sys
from pathlib import Path

def analyze_collection(mods_dir: Path) -> dict:
    """Run simanalysis and return results."""
    output_file = Path("collection_analysis.json")

    cmd = [
        "simanalysis", "analyze", str(mods_dir),
        "--output", str(output_file),
        "--format", "json",
        "--quiet"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Analysis failed: {result.stderr}")
        sys.exit(1)

    with open(output_file) as f:
        return json.load(f)

def generate_report(analysis: dict) -> None:
    """Generate human-readable conflict report."""
    mods = analysis['mods']
    conflicts = analysis['conflicts']
    summary = analysis['summary']

    print("=" * 60)
    print("MOD COLLECTION ANALYSIS REPORT")
    print("=" * 60)
    print()

    print(f"Total Mods: {len(mods)}")
    print(f"Total Conflicts: {len(conflicts)}")
    print()

    # Conflict breakdown by severity
    severity_counts = {}
    for conflict in conflicts:
        sev = conflict['severity']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    print("Conflicts by Severity:")
    for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = severity_counts.get(severity, 0)
        if count > 0:
            print(f"  {severity}: {count}")
    print()

    # List high-priority conflicts
    high_priority = [c for c in conflicts
                    if c['severity'] in ['CRITICAL', 'HIGH']]

    if high_priority:
        print("⚠️  HIGH PRIORITY CONFLICTS:")
        print()
        for i, conflict in enumerate(high_priority, 1):
            print(f"{i}. [{conflict['severity']}] {conflict['description']}")
            print(f"   Affected: {', '.join(conflict['affected_mods'][:3])}")
            if len(conflict['affected_mods']) > 3:
                print(f"   ... and {len(conflict['affected_mods']) - 3} more")
            print()

    # Recommendations
    if analysis.get('recommendations'):
        print("RECOMMENDATIONS:")
        for rec in analysis['recommendations']:
            print(f"  • {rec}")
        print()

    print("=" * 60)
    print("Full report saved to: collection_analysis.json")
    print("=" * 60)

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_collection.py <mods_directory>")
        sys.exit(1)

    mods_dir = Path(sys.argv[1])
    if not mods_dir.exists():
        print(f"Error: Directory not found: {mods_dir}")
        sys.exit(1)

    print(f"Analyzing mods in: {mods_dir}")
    print()

    analysis = analyze_collection(mods_dir)
    generate_report(analysis)

if __name__ == "__main__":
    main()
```

Usage:
```bash
python3 check_collection.py ~/Documents/"Electronic Arts"/"The Sims 4"/Mods
```

### CI/CD Integration (GitHub Actions)

```yaml
# .github/workflows/test-mod.yml
name: Test Mod
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Simanalysis
        run: pip install simanalysis

      - name: Analyze mod
        run: |
          simanalysis analyze ./package/*.package \
            --output report.json \
            --format json \
            --quiet

      - name: Check for critical conflicts
        run: |
          python3 << 'EOF'
          import json, sys
          with open('report.json') as f:
              report = json.load(f)
          critical = [c for c in report['conflicts']
                     if c['severity'] == 'CRITICAL']
          if critical:
              print(f"❌ Found {len(critical)} critical conflicts!")
              for c in critical:
                  print(f"  - {c['description']}")
              sys.exit(1)
          print("✅ No critical conflicts")
          EOF

      - name: Upload analysis report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: analysis-report
          path: report.json
```

### Batch Processing Multiple Mods

```bash
#!/bin/bash
# batch_analyze.sh - Analyze multiple individual mod files

OUTPUT_DIR="./analysis_results"
mkdir -p "$OUTPUT_DIR"

for mod in *.package; do
    echo "Analyzing $mod..."

    # Generate output filename
    output_name=$(basename "$mod" .package)
    output_file="$OUTPUT_DIR/${output_name}_report.json"

    # Analyze
    simanalysis analyze "$mod" \
        --output "$output_file" \
        --format json \
        --quiet

    echo "  Report saved to: $output_file"
done

echo "All mods analyzed! Reports in: $OUTPUT_DIR"
```

## Python API Usage

```python
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

# Create analyzer
analyzer = ModAnalyzer()

# Analyze directory
mods_dir = Path("~/Documents/Electronic Arts/The Sims 4/Mods").expanduser()
result = analyzer.analyze_directory(mods_dir)

# Access results
print(f"Found {len(result.mods)} mods")
print(f"Detected {len(result.conflicts)} conflicts")

# Check specific conflict types
for conflict in result.conflicts:
    if conflict.severity == "HIGH":
        print(f"High-severity conflict: {conflict.description}")
        print(f"  Affected: {', '.join(conflict.affected_mods)}")

# Export to JSON
analyzer.export_report(result, Path("output.json"), format="json")
```

## Tips & Best Practices

### For Mod Users

1. **Regular Scans**: Run analysis after adding new mods
2. **Check Conflicts**: Focus on HIGH and CRITICAL severity
3. **Keep Logs**: Save analysis reports for troubleshooting
4. **Before Updates**: Analyze before game patches to anticipate issues

### For Mod Creators

1. **Pre-Release Testing**: Always analyze before releasing
2. **Conflict Awareness**: Check for conflicts with popular mods
3. **Version Control**: Keep analysis reports with each release
4. **Documentation**: Include conflict information in README

### For Collection Curators

1. **Baseline Analysis**: Document your "clean" mod set
2. **Incremental Testing**: Analyze after each mod addition
3. **Conflict Matrix**: Track which mods conflict with each other
4. **Update Checks**: Re-analyze after mod updates

## Next Steps

- See `tests/fixtures/README.md` for test fixture examples
- Check `CHANGELOG.md` for latest features
- Review `IMPLEMENTATION_PLAN_V3.md` for upcoming features
- Report issues at https://github.com/anthropics/claude-code/issues

---

**Version**: 3.0.0
**Last Updated**: 2025-11-23
**License**: MIT
