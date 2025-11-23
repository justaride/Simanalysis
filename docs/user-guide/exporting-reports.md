# Exporting Reports

A comprehensive guide to exporting, processing, and sharing analysis reports from Simanalysis.

## Overview

Simanalysis supports multiple export formats, each optimized for different use cases:

- **JSON**: Machine-readable, perfect for automation
- **TXT**: Human-readable, terminal-friendly
- **YAML**: Structured and readable, good for version control
- **Console**: Default real-time output

## Export Basics

### Simple Export

Export to any format with the `--output` flag:

```bash
# JSON format (inferred from extension)
simanalysis analyze ./mods --output report.json

# TXT format
simanalysis analyze ./mods --output report.txt

# YAML format
simanalysis analyze ./mods --output report.yaml
```

### Explicit Format

Specify format explicitly with `--format`:

```bash
# Explicit JSON
simanalysis analyze ./mods --output report.json --format json

# Force JSON even with .txt extension
simanalysis analyze ./mods --output data.txt --format json
```

### Quiet Mode with Export

Suppress console output, only export:

```bash
simanalysis analyze ./mods --quiet --output report.json
```

**Use case:** Automation scripts where console output is noise.

## JSON Export

### Structure

```json
{
  "metadata": {
    "timestamp": "2025-11-23T14:30:00.000000",
    "simanalysis_version": "3.0.0",
    "scan_directory": "/path/to/mods",
    "python_version": "3.11.0",
    "platform": "Windows-10"
  },
  "mods": [
    {
      "name": "AwesomeMod.package",
      "path": "/path/to/mods/AwesomeMod.package",
      "size": 1048576,
      "mod_type": "package",
      "hash": "abc123...",
      "resources": [
        {
          "type": 545238217,
          "group": 0,
          "instance": 305419896,
          "size": 4096
        }
      ],
      "tunings": [
        {
          "instance_id": "0x12345678",
          "module": "traits.trait_Confident",
          "class": "Trait"
        }
      ]
    }
  ],
  "conflicts": [
    {
      "type": "tuning",
      "severity": "HIGH",
      "instance_id": "0x12345678",
      "affected_mods": [
        "/path/to/mods/AwesomeMod.package",
        "/path/to/mods/BetterMod.package"
      ],
      "description": "Tuning conflict: Multiple mods modify instance 0x12345678",
      "recommendation": "Keep only one mod or use compatibility patch"
    }
  ],
  "summary": {
    "total_mods": 47,
    "total_size": 47185920,
    "total_resources": 2847,
    "total_tunings": 456,
    "total_scripts": 12,
    "total_conflicts": 3,
    "conflicts_by_severity": {
      "CRITICAL": 0,
      "HIGH": 1,
      "MEDIUM": 2,
      "LOW": 0
    }
  }
}
```

### JSON Use Cases

#### 1. Automation

```bash
#!/bin/bash
# Auto-analyze and alert on critical conflicts

simanalysis analyze ./mods --quiet --output report.json

critical=$(jq '.conflicts[] | select(.severity == "CRITICAL") | length' report.json | wc -l)

if [ $critical -gt 0 ]; then
    echo "❌ CRITICAL conflicts found!"
    jq '.conflicts[] | select(.severity == "CRITICAL")' report.json
    exit 1
else
    echo "✅ No critical conflicts"
    exit 0
fi
```

#### 2. CI/CD Integration

```yaml
# .github/workflows/mod-check.yml
name: Check Mod Conflicts

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Simanalysis
        run: pip install simanalysis

      - name: Analyze Mods
        run: |
          simanalysis analyze ./mods --quiet --output report.json

      - name: Check for Critical Conflicts
        run: |
          critical=$(jq '[.conflicts[] | select(.severity == "CRITICAL")] | length' report.json)
          if [ $critical -gt 0 ]; then
            echo "Found $critical critical conflicts"
            exit 1
          fi

      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: analysis-report
          path: report.json
```

#### 3. Data Processing

```python
import json

# Load report
with open('report.json') as f:
    data = json.load(f)

# Find largest mods
mods_by_size = sorted(data['mods'], key=lambda m: m['size'], reverse=True)
print("Top 10 largest mods:")
for mod in mods_by_size[:10]:
    size_mb = mod['size'] / 1024 / 1024
    print(f"  {mod['name']}: {size_mb:.2f} MB")

# Find most conflicted mods
from collections import Counter
conflicted = Counter()
for conflict in data['conflicts']:
    for mod_path in conflict['affected_mods']:
        conflicted[mod_path] += 1

print("\nMost conflicted mods:")
for mod_path, count in conflicted.most_common(5):
    mod_name = mod_path.split('/')[-1]
    print(f"  {mod_name}: {count} conflicts")
```

#### 4. Web Dashboard

```javascript
// Load and display report in web page
fetch('report.json')
  .then(response => response.json())
  .then(data => {
    // Display summary
    document.getElementById('total-mods').textContent = data.summary.total_mods;
    document.getElementById('total-conflicts').textContent = data.summary.total_conflicts;

    // Display conflicts
    const conflictsList = document.getElementById('conflicts');
    data.conflicts.forEach(conflict => {
      const item = document.createElement('li');
      item.className = `severity-${conflict.severity.toLowerCase()}`;
      item.textContent = conflict.description;
      conflictsList.appendChild(item);
    });
  });
```

### JSON Query Examples

Using `jq` to query JSON reports:

```bash
# Count mods
jq '.mods | length' report.json

# List mod names
jq '.mods[].name' report.json

# Find mods over 10MB
jq '.mods[] | select(.size > 10485760) | .name' report.json

# Get high-severity conflicts
jq '.conflicts[] | select(.severity == "HIGH")' report.json

# Count conflicts by type
jq '.conflicts | group_by(.type) | map({type: .[0].type, count: length})' report.json

# Find mods involved in conflicts
jq '[.conflicts[].affected_mods[]] | unique' report.json

# Get script mods only
jq '.mods[] | select(.mod_type == "script")' report.json

# Calculate total collection size
jq '[.mods[].size] | add' report.json

# Find conflicts affecting specific mod
jq '.conflicts[] | select(.affected_mods[] | contains("AwesomeMod"))' report.json
```

## TXT Export

### Format

```
=== MOD ANALYSIS REPORT ===

Generated: 2025-11-23 14:30:00
Simanalysis Version: 3.0.0
Scan Directory: /path/to/mods

=== SUMMARY ===

Total Mods: 47
Total Size: 45.0 MB
Total Resources: 2,847
Total Tunings: 456
Total Scripts: 12

Total Conflicts: 3

Conflicts by Severity:
  🔴 CRITICAL: 0
  🟠 HIGH: 1
  🟡 MEDIUM: 2
  🟢 LOW: 0

=== MODS ===

1. AwesomeMod.package
   Path: /path/to/mods/AwesomeMod.package
   Size: 1.0 MB
   Resources: 45
   Tunings: 12

2. BetterMod.package
   Path: /path/to/mods/BetterMod.package
   Size: 2.5 MB
   Resources: 128
   Tunings: 34

[... more mods ...]

=== CONFLICTS ===

🟠 HIGH SEVERITY

1. Tuning Conflict
   Instance ID: 0x12345678
   Affected Mods:
     - AwesomeMod.package
     - BetterMod.package
   Description: Multiple mods modify instance 0x12345678
   Recommendation: Keep only one mod or use compatibility patch

🟡 MEDIUM SEVERITY

2. Resource Conflict
   Hash: 0xABCDEF01
   Affected Mods:
     - CustomClothes.package
     - RecolorPack.package
   Description: Resource hash collision detected
   Recommendation: Visual conflict, test in CAS

[... more conflicts ...]

=== END REPORT ===
```

### TXT Use Cases

#### 1. Sharing with Others

TXT format is easiest to read and share:

```bash
# Export to TXT
simanalysis analyze ./mods --output report.txt

# Share via email, Discord, forums
# Recipients can read in any text editor
```

#### 2. Terminal Viewing

```bash
# View with pager
simanalysis analyze ./mods --output report.txt
less report.txt

# Search for specific conflicts
grep "HIGH" report.txt

# Count conflicts
grep -c "Conflict" report.txt
```

#### 3. Printing

TXT format is print-friendly:

```bash
# Print to physical printer
lpr report.txt

# Convert to PDF
enscript report.txt -o - | ps2pdf - report.pdf
```

### TXT Processing Examples

```bash
# Extract only high-severity conflicts
grep -A 10 "🟠 HIGH SEVERITY" report.txt > high_conflicts.txt

# Count mod types
grep "mod_type" report.txt | sort | uniq -c

# Find mods over certain size
awk '/Size:.*MB/ { if ($2 > 5) print $0 }' report.txt

# Create conflict summary
grep "Affected Mods:" report.txt | wc -l
```

## YAML Export

### Format

```yaml
metadata:
  timestamp: '2025-11-23T14:30:00'
  simanalysis_version: '3.0.0'
  scan_directory: /path/to/mods
  python_version: '3.11.0'
  platform: Windows-10

mods:
  - name: AwesomeMod.package
    path: /path/to/mods/AwesomeMod.package
    size: 1048576
    mod_type: package
    hash: abc123def456
    resources:
      - type: 545238217
        group: 0
        instance: 305419896
        size: 4096
    tunings:
      - instance_id: '0x12345678'
        module: traits.trait_Confident
        class: Trait

conflicts:
  - type: tuning
    severity: HIGH
    instance_id: '0x12345678'
    affected_mods:
      - /path/to/mods/AwesomeMod.package
      - /path/to/mods/BetterMod.package
    description: 'Tuning conflict: Multiple mods modify instance 0x12345678'
    recommendation: Keep only one mod or use compatibility patch

summary:
  total_mods: 47
  total_size: 47185920
  total_resources: 2847
  total_tunings: 456
  total_scripts: 12
  total_conflicts: 3
  conflicts_by_severity:
    CRITICAL: 0
    HIGH: 1
    MEDIUM: 2
    LOW: 0
```

### YAML Use Cases

#### 1. Configuration Management

```yaml
# Store in version control with mod collection
git add mods/ report.yaml
git commit -m "Add new mods, 3 conflicts detected"
```

#### 2. Easy Editing

YAML is human-editable for annotations:

```yaml
conflicts:
  - type: tuning
    severity: HIGH
    instance_id: '0x12345678'
    # RESOLVED: 2025-11-23 - Removed BetterMod
    status: resolved
    resolution_date: '2025-11-23'
    resolution_method: 'Removed BetterMod.package'
```

#### 3. Cross-Tool Integration

```python
import yaml

# Load YAML report
with open('report.yaml') as f:
    data = yaml.safe_load(f)

# Process same as JSON
for conflict in data['conflicts']:
    if conflict['severity'] == 'HIGH':
        print(f"⚠️  {conflict['description']}")
```

### YAML Processing Examples

```bash
# Convert YAML to JSON
python -c "import yaml, json; print(json.dumps(yaml.safe_load(open('report.yaml'))))" > report.json

# Query with yq (like jq for YAML)
yq '.conflicts[] | select(.severity == "HIGH")' report.yaml

# Count conflicts
yq '.conflicts | length' report.yaml
```

## Console Output

### Default Format

When no `--output` is specified:

```bash
simanalysis analyze ./mods
```

```
🔍 Scanning for mods...
Found 47 mods in /path/to/mods

📦 Analyzing packages...
[████████████████████████████] 47/47 100%

🔬 Detecting conflicts...
Found 3 conflicts

=== MOD ANALYSIS REPORT ===

Total Mods: 47
Total Conflicts: 3

Conflicts by Severity:
  🟠 HIGH: 1
  🟡 MEDIUM: 2

High Priority Conflicts:
  1. [HIGH] Tuning conflict detected
     Instance ID: 0x12345678
     Affected: AwesomeMod.package, BetterMod.package

Medium Priority Conflicts:
  2. [MEDIUM] Resource conflict
     Hash: 0xABCDEF01
     Affected: CustomClothes.package, RecolorPack.package

✅ Analysis complete!
```

### Verbose Console

```bash
simanalysis analyze ./mods --verbose
```

Adds detailed progress:
- Each mod discovered
- Parsing progress per mod
- Resource extraction details
- Conflict detection logic

### Quiet Console

```bash
simanalysis analyze ./mods --quiet
```

No console output (use with `--output` for silent operation).

## Advanced Export Patterns

### Multiple Format Export

Export to multiple formats at once:

```bash
#!/bin/bash
# Export to all formats

BASE="report_$(date +%Y%m%d)"

simanalysis analyze ./mods --quiet --output "${BASE}.json"
simanalysis analyze ./mods --quiet --output "${BASE}.txt"
simanalysis analyze ./mods --quiet --output "${BASE}.yaml"

echo "Exported to:"
echo "  - ${BASE}.json"
echo "  - ${BASE}.txt"
echo "  - ${BASE}.yaml"
```

### Timestamped Reports

Keep history of analyses:

```bash
#!/bin/bash
# Archive reports with timestamps

REPORT_DIR="reports/$(date +%Y-%m)"
mkdir -p "$REPORT_DIR"

simanalysis analyze ./mods \
    --quiet \
    --output "$REPORT_DIR/report_$(date +%Y%m%d_%H%M%S).json"

echo "Report saved to $REPORT_DIR"
ls -lh "$REPORT_DIR"
```

### Filtered Exports

Export only critical conflicts:

```bash
# Full analysis
simanalysis analyze ./mods --quiet --output full_report.json

# Extract critical conflicts only
jq '{
    metadata: .metadata,
    conflicts: [.conflicts[] | select(.severity == "CRITICAL" or .severity == "HIGH")],
    summary: .summary
}' full_report.json > critical_only.json
```

### Comparative Reports

Compare two analysis runs:

```bash
# Baseline
simanalysis analyze ./mods --output baseline.json

# After adding mods
simanalysis analyze ./mods --output current.json

# Generate diff report
jq -s '{
    baseline_conflicts: .[0].summary.total_conflicts,
    current_conflicts: .[1].summary.total_conflicts,
    new_conflicts: [.[1].conflicts[] | select(.instance_id as $id |
        [.[0].conflicts[].instance_id] | contains([$id]) | not)]
}' baseline.json current.json > diff_report.json
```

### Aggregated Reports

Combine multiple collections:

```bash
#!/bin/bash
# Analyze multiple players' mods

players=("alice" "bob" "charlie")

for player in "${players[@]}"; do
    simanalysis analyze "/players/$player/mods" \
        --quiet \
        --output "${player}_report.json"
done

# Aggregate statistics
jq -s '{
    total_players: length,
    total_mods: [.[].summary.total_mods] | add,
    total_conflicts: [.[].summary.total_conflicts] | add,
    players: [.[] | {
        mods: .summary.total_mods,
        conflicts: .summary.total_conflicts
    }]
}' *_report.json > aggregate_report.json
```

## Report Sharing

### Email

```bash
# Generate and email report
simanalysis analyze ./mods --output report.txt

echo "See attached mod analysis report" | \
    mail -s "Mod Analysis $(date +%Y-%m-%d)" \
         -A report.txt \
         friend@example.com
```

### Discord/Slack

```bash
# Generate report
simanalysis analyze ./mods --output report.json

# Extract summary
summary=$(jq -r '"\(.summary.total_mods) mods, \(.summary.total_conflicts) conflicts"' report.json)

# Post to Discord webhook
curl -X POST "$DISCORD_WEBHOOK" \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"📊 Mod Analysis: $summary\"}"
```

### Web Upload

```bash
# Upload to file sharing
simanalysis analyze ./mods --output report.json

# Upload to pastebin/gist
curl -X POST https://api.github.com/gists \
    -H "Authorization: token $GITHUB_TOKEN" \
    -d "{
        \"public\": false,
        \"files\": {
            \"mod_report.json\": {
                \"content\": $(jq -R -s . report.json)
            }
        }
    }"
```

## Report Processing Tools

### Python

```python
import json
from pathlib import Path

def load_report(report_path: Path) -> dict:
    """Load analysis report."""
    with open(report_path) as f:
        return json.load(f)

def filter_high_severity(report: dict) -> list:
    """Get high severity conflicts only."""
    return [
        c for c in report['conflicts']
        if c['severity'] in ['HIGH', 'CRITICAL']
    ]

def generate_html_report(report: dict, output_path: Path):
    """Generate HTML report."""
    html = f"""
    <html>
    <head><title>Mod Analysis Report</title></head>
    <body>
        <h1>Mod Analysis Report</h1>
        <p>Total Mods: {report['summary']['total_mods']}</p>
        <p>Total Conflicts: {report['summary']['total_conflicts']}</p>
        <h2>Conflicts</h2>
        <ul>
    """
    for conflict in report['conflicts']:
        severity_color = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MEDIUM': 'yellow',
            'LOW': 'green'
        }[conflict['severity']]
        html += f"""
            <li style="color: {severity_color}">
                [{conflict['severity']}] {conflict['description']}
            </li>
        """
    html += """
        </ul>
    </body>
    </html>
    """
    output_path.write_text(html)

# Usage
report = load_report(Path('report.json'))
high_conflicts = filter_high_severity(report)
generate_html_report(report, Path('report.html'))
```

### Shell Script

```bash
#!/bin/bash
# Report processing utilities

# Function: Get conflict count by severity
get_conflict_count() {
    severity=$1
    jq ".conflicts[] | select(.severity == \"$severity\") | length" report.json | wc -l
}

# Function: List mods in conflicts
list_conflicted_mods() {
    jq -r '.conflicts[].affected_mods[]' report.json | sort -u
}

# Function: Generate summary
generate_summary() {
    total_mods=$(jq '.summary.total_mods' report.json)
    total_conflicts=$(jq '.summary.total_conflicts' report.json)
    critical=$(get_conflict_count "CRITICAL")
    high=$(get_conflict_count "HIGH")

    echo "=== MOD COLLECTION SUMMARY ==="
    echo "Total Mods: $total_mods"
    echo "Total Conflicts: $total_conflicts"
    echo "  - Critical: $critical"
    echo "  - High: $high"
}

# Usage
generate_summary
```

## Best Practices

### 1. Always Export for Records

Even if you view console output, export for future reference:

```bash
simanalysis analyze ./mods --output report.json
```

### 2. Use JSON for Automation

JSON is best for scripts and tools:

```bash
simanalysis analyze ./mods --quiet --output report.json
```

### 3. Use TXT for Sharing

TXT is most readable for humans:

```bash
simanalysis analyze ./mods --output report.txt
```

### 4. Version Control YAML

YAML works well in git:

```bash
simanalysis analyze ./mods --output report.yaml
git add report.yaml
git commit -m "Update mod analysis"
```

### 5. Archive Reports

Keep historical records:

```bash
mkdir -p reports
simanalysis analyze ./mods --output "reports/$(date +%Y%m%d).json"
```

## Next Steps

- Learn analysis techniques in [Analyzing Mods](analyzing-mods.md)
- Understand conflicts in [Understanding Conflicts](understanding-conflicts.md)
- Troubleshoot issues in [Troubleshooting](troubleshooting.md)
- See integration examples in [CI/CD Integration](../examples/cicd.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
