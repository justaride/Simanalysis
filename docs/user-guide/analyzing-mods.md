# Analyzing Mods

A comprehensive guide to analyzing The Sims 4 mod collections with Simanalysis.

## Overview

Simanalysis provides powerful tools to analyze your Sims 4 mods, detecting conflicts, validating structure, and providing insights into your mod collection.

## Quick Analysis

The fastest way to analyze your mods:

```bash
simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods
```

This will:
1. Scan all .package and .ts4script files recursively
2. Parse DBPF packages and extract resources
3. Detect conflicts between mods
4. Display a comprehensive report

## Analysis Process

### 1. Discovery Phase

Simanalysis first discovers all mod files in your directory:

```bash
simanalysis scan ./mods
```

**What happens:**
- Walks directory tree recursively (unless `--no-recursive`)
- Identifies .package and .ts4script files
- Skips hidden files and directories
- Reports file count and total size

### 2. Parsing Phase

Each mod file is parsed to extract metadata:

**For .package files:**
- Read DBPF header (version, index count)
- Parse resource index (types, groups, instances)
- Extract tuning XML from resources
- Parse tuning instance IDs and modules

**For .ts4script files:**
- Open ZIP archive
- Extract Python files
- Perform AST analysis
- Detect injection patterns and imports

### 3. Conflict Detection

Simanalysis analyzes all mods together to find conflicts:

**Tuning Conflicts:**
```
When two mods have the same tuning instance ID:
  Mod A: trait_confident (ID: 0x12345678)
  Mod B: trait_confident_custom (ID: 0x12345678)
  → Conflict! Only one will load.
```

**Resource Conflicts:**
```
When two mods have resources with identical hashes:
  Mod A: texture.dds (Hash: 0xABCDEF01)
  Mod B: custom_texture.dds (Hash: 0xABCDEF01)
  → Conflict! Resources will overwrite.
```

**Script Conflicts:**
```
When two scripts inject into the same function:
  Mod A: inject_into(sims4.commands.execute)
  Mod B: inject_into(sims4.commands.execute)
  → Potential conflict! Load order matters.
```

### 4. Report Generation

Results are compiled into a comprehensive report showing:
- Total mods analyzed
- Conflicts found (by severity)
- Performance metrics
- Detailed conflict information

## Analysis Options

### File Type Filtering

Analyze only specific file types:

```bash
# Only .package files
simanalysis analyze ./mods --extensions .package

# Only .ts4script files
simanalysis analyze ./mods --extensions .ts4script

# Both (explicit)
simanalysis analyze ./mods --extensions .package .ts4script
```

**Use case:** Focus analysis on specific mod types when troubleshooting.

### Directory Depth

Control how deep the scan goes:

```bash
# Non-recursive (current directory only)
simanalysis analyze ./mods --no-recursive

# Default: recursive through all subdirectories
simanalysis analyze ./mods
```

**Use case:** Analyze subdirectories individually to isolate conflicts.

### Verbosity Control

Adjust output detail:

```bash
# Quiet mode (no console output)
simanalysis analyze ./mods --quiet --output report.json

# Verbose mode (detailed progress)
simanalysis analyze ./mods --verbose

# Default: balanced output
simanalysis analyze ./mods
```

### Logging

Configure diagnostic logging:

```bash
# Debug logging
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log

# Info logging (default)
simanalysis analyze ./mods --log-level INFO

# Only errors
simanalysis analyze ./mods --log-level ERROR
```

**Log levels:**
- **DEBUG**: Everything (file opens, parsing steps, decisions)
- **INFO**: Important events (mod discovered, conflict found)
- **WARNING**: Potential issues (malformed files, missing data)
- **ERROR**: Failures (corrupted files, parse errors)

## Output Formats

### Console Output

Default human-readable format:

```
=== MOD ANALYSIS REPORT ===

Total Mods: 47
Total Conflicts: 3

Conflicts by Severity:
  🔴 CRITICAL: 0
  🟠 HIGH: 1
  🟡 MEDIUM: 2
  🟢 LOW: 0

High Priority Conflicts:
  1. [HIGH] Tuning conflict detected
     Instance ID: 0x12345678
     Affected mods:
       - AwesomeMod.package
       - BetterMod.package
     Resolution: Keep only one mod
```

### JSON Export

Machine-readable format for automation:

```bash
simanalysis analyze ./mods --output report.json --format json
```

**Structure:**
```json
{
  "metadata": {
    "timestamp": "2025-11-23T10:30:00",
    "simanalysis_version": "3.0.0",
    "scan_directory": "/path/to/mods"
  },
  "mods": [
    {
      "name": "AwesomeMod.package",
      "path": "/path/to/mods/AwesomeMod.package",
      "size": 1048576,
      "mod_type": "package",
      "resources": [...]
    }
  ],
  "conflicts": [
    {
      "type": "tuning",
      "severity": "HIGH",
      "instance_id": "0x12345678",
      "affected_mods": ["AwesomeMod.package", "BetterMod.package"],
      "description": "Tuning conflict detected"
    }
  ],
  "summary": {
    "total_mods": 47,
    "total_conflicts": 3,
    "by_severity": {
      "CRITICAL": 0,
      "HIGH": 1,
      "MEDIUM": 2,
      "LOW": 0
    }
  }
}
```

### TXT Export

Human-readable file format:

```bash
simanalysis analyze ./mods --output report.txt --format txt
```

Good for:
- Sharing with others
- Reading in text editors
- Searching with grep/find

### YAML Export

Structured and readable:

```bash
simanalysis analyze ./mods --output report.yaml --format yaml
```

Good for:
- Configuration management
- Version control
- Human editing

## Interactive Mode (TUI)

Launch the text-based user interface:

```bash
simanalysis analyze ./mods --tui
```

### TUI Features

**Navigation:**
- ↑↓ Arrow keys: Move through lists
- Enter: Select item for details
- Tab: Switch between panels
- q: Quit application

**Panels:**
1. **Mod List**: All discovered mods with sizes
2. **Conflict List**: All conflicts with severity
3. **Details**: Selected item details
4. **Summary**: Overall statistics

**Filtering:**
- Press `f` to filter by severity
- Press `s` to sort (name, size, conflicts)
- Press `/` to search

**Actions:**
- Press `e` to export current view
- Press `r` to refresh analysis
- Press `h` for help

### TUI Use Cases

**Quick Exploration:**
```bash
# Launch TUI to explore large collection
simanalysis analyze ./mods --tui

# Navigate to high-severity conflicts
# Press 'f', select 'HIGH'
# Review each conflict interactively
```

**Selective Export:**
```bash
# Launch TUI
simanalysis analyze ./mods --tui

# Filter to CRITICAL conflicts only
# Press 'e' to export filtered view
```

## Advanced Analysis

### Analyzing Multiple Directories

Analyze multiple mod directories separately:

```bash
# Analyze main mods
simanalysis analyze ~/Mods --output mods_report.json

# Analyze custom content
simanalysis analyze ~/CC --output cc_report.json

# Compare results
diff <(jq -S . mods_report.json) <(jq -S . cc_report.json)
```

### Incremental Analysis

Analyze only new/changed mods:

```bash
# First analysis
simanalysis analyze ./mods --output baseline.json

# After adding new mods
simanalysis analyze ./mods --output current.json

# Find differences
jq '.mods | length' baseline.json  # 45
jq '.mods | length' current.json   # 47
# 2 new mods added
```

### Batch Processing

Analyze many directories:

```bash
#!/bin/bash
for player_dir in /players/*/Mods; do
    player=$(basename $(dirname "$player_dir"))
    simanalysis analyze "$player_dir" \
        --quiet \
        --output "reports/${player}_report.json"
done

echo "Analyzed ${#players[@]} mod collections"
```

## Performance Considerations

### Large Collections (1000+ mods)

**Symptoms:**
- Analysis takes several minutes
- High memory usage
- Console output floods terminal

**Solutions:**

1. **Use quiet mode:**
```bash
simanalysis analyze ./mods --quiet --output report.json
```

2. **Limit file types:**
```bash
# Analyze packages first
simanalysis analyze ./mods --extensions .package --output packages.json

# Then scripts
simanalysis analyze ./mods --extensions .ts4script --output scripts.json
```

3. **Analyze subdirectories separately:**
```bash
for subdir in ./mods/*/; do
    name=$(basename "$subdir")
    simanalysis analyze "$subdir" --output "${name}.json"
done
```

### Slow Disk I/O

**Symptoms:**
- Analysis pauses frequently
- Disk activity light constantly on

**Solutions:**

1. **Move mods to SSD** (if using HDD)
2. **Close other disk-intensive programs**
3. **Use non-recursive mode** for shallow scans

### Memory Constraints

**Symptoms:**
- System becomes sluggish during analysis
- Out of memory errors

**Solutions:**

1. **Close other applications**
2. **Analyze in smaller batches**
3. **Use Docker with memory limit:**
```bash
docker run -m 2g simanalysis:latest analyze /mods
```

## Common Workflows

### Workflow 1: New Mod Installation

After installing new mods:

```bash
# Quick check for new conflicts
simanalysis analyze ./mods --output latest.json

# Compare with previous report
diff <(jq -S .conflicts previous.json) <(jq -S .conflicts latest.json)

# If no new conflicts, you're good!
```

### Workflow 2: Conflict Resolution

When conflicts are found:

```bash
# Generate detailed report
simanalysis analyze ./mods --verbose --output conflicts.json

# Review conflicts
jq '.conflicts[] | select(.severity == "HIGH" or .severity == "CRITICAL")' conflicts.json

# Remove problematic mod
rm ./mods/ProblematicMod.package

# Re-analyze
simanalysis analyze ./mods --output fixed.json

# Verify conflict resolved
jq '.conflicts | length' fixed.json
```

### Workflow 3: Pre-Game Check

Before starting game:

```bash
# Quick analysis
simanalysis analyze ./mods --quiet --output pregame.json

# Check for critical issues
critical=$(jq '.conflicts[] | select(.severity == "CRITICAL") | length' pregame.json)

if [ "$critical" -gt 0 ]; then
    echo "⚠️  Critical conflicts found! Review before playing."
    simanalysis view pregame.json
else
    echo "✅ No critical conflicts. Safe to play!"
fi
```

### Workflow 4: Mod Collection Maintenance

Monthly maintenance:

```bash
# Full analysis with debug logging
simanalysis analyze ./mods \
    --log-level DEBUG \
    --log-file maintenance.log \
    --output monthly_report.json

# Archive report
mkdir -p reports/$(date +%Y-%m)
cp monthly_report.json reports/$(date +%Y-%m)/report_$(date +%d).json

# Review trends
ls -lh reports/*/report_*.json
```

## Interpreting Results

### Understanding Conflict Severity

**CRITICAL (🔴):**
- Game crashes expected
- Data corruption possible
- **Action required immediately**
- Examples: Core game file conflicts, broken package headers

**HIGH (🟠):**
- Gameplay issues likely
- Features may not work
- **Should resolve soon**
- Examples: Tuning conflicts, overlapping injections

**MEDIUM (🟡):**
- Minor issues possible
- Visual glitches may occur
- **Optional to resolve**
- Examples: Texture hash collisions, similar tuning modules

**LOW (🟢):**
- Informational only
- Unlikely to cause problems
- **No action needed**
- Examples: Different resources with nearby IDs

### Conflict Patterns

**Pattern 1: Tuning Overlap**
```
Multiple mods editing same trait/buff/interaction
→ Last loaded wins
→ Solution: Use compatibility patch or choose one
```

**Pattern 2: Resource Hash Collision**
```
Two mods using same resource hash accidentally
→ One resource overwrites the other
→ Solution: Regenerate hash or remove one mod
```

**Pattern 3: Script Injection Order**
```
Multiple scripts injecting same function
→ Load order determines execution
→ Solution: Check mod documentation for load order
```

## Troubleshooting Analysis

### Analysis Takes Too Long

**Check:**
```bash
# How many mods?
find ./mods -name "*.package" -o -name "*.ts4script" | wc -l

# Total size?
du -sh ./mods
```

**If 1000+ mods or 5GB+:**
- Use `--no-recursive` for subdirectories
- Analyze in batches
- Enable `--quiet` mode

### No Conflicts Detected (Expected Some)

**Possible causes:**
1. Mods use different tuning IDs (no actual conflict)
2. Mods in different directories (not analyzed together)
3. File type filter excluding relevant mods

**Debug:**
```bash
# Analyze with debug logging
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log

# Check what was found
grep "discovered" debug.log
grep "conflict" debug.log
```

### Too Many False Positives

**Check severity:**
```bash
# Show only HIGH and CRITICAL
jq '.conflicts[] | select(.severity == "HIGH" or .severity == "CRITICAL")' report.json
```

Most conflicts are informational (MEDIUM/LOW) and safe to ignore.

## Next Steps

- Learn more in [Understanding Conflicts](understanding-conflicts.md)
- Export results following [Exporting Reports](exporting-reports.md)
- Troubleshoot issues in [Troubleshooting](troubleshooting.md)
- See practical examples in [Basic Examples](../examples/basic.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
