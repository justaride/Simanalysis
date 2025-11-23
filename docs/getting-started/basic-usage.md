# Basic Usage

Learn the fundamental concepts and commands for using Simanalysis.

## Core Concepts

### Mods
Individual mod files with extensions:
- `.package` - DBPF package files (tunings, resources)
- `.ts4script` - Python script mods

### Conflicts
When multiple mods modify the same game element:
- **Tuning Conflicts**: Same tuning ID in multiple mods
- **Resource Conflicts**: Same resource hash in multiple mods
- **Script Conflicts**: Same Python function injection

### Severity Levels
- 🔴 **CRITICAL**: Game-breaking, must resolve
- 🟠 **HIGH**: Likely to cause issues
- 🟡 **MEDIUM**: May cause minor problems
- 🟢 **LOW**: Informational, unlikely to cause issues

## Command Structure

```bash
simanalysis <command> [options] <arguments>
```

### Main Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `analyze` | Analyze mods | `simanalysis analyze ./mods` |
| `scan` | List mods | `simanalysis scan ./mods` |
| `view` | View report | `simanalysis view report.json` |
| `info` | Show version | `simanalysis info` |

## Analyze Command

The most commonly used command.

### Basic Syntax

```bash
simanalysis analyze <directory> [options]
```

### Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `--output FILE` | Export report | `--output report.json` |
| `--format FORMAT` | Output format | `--format json` |
| `--log-level LEVEL` | Logging level | `--log-level DEBUG` |
| `--log-file FILE` | Log file path | `--log-file analysis.log` |
| `--quiet` | Suppress output | `--quiet` |
| `--verbose` | Detailed output | `--verbose` |
| `--extensions EXT` | File types | `--extensions .package` |
| `--no-recursive` | Don't scan subdirs | `--no-recursive` |
| `--tui` | Interactive mode | `--tui` |

### Examples

#### Analyze Directory

```bash
simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods
```

#### Analyze with Export

```bash
simanalysis analyze ./mods --output report.json --format json
```

#### Analyze Specific Types

```bash
# Only .package files
simanalysis analyze ./mods --extensions .package

# Both packages and scripts
simanalysis analyze ./mods --extensions .package .ts4script
```

#### Non-Recursive Scan

Analyze only the specified directory (skip subdirectories):

```bash
simanalysis analyze ./mods --no-recursive
```

#### Debug Mode

```bash
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log
```

#### Quiet Mode

No console output, only export:

```bash
simanalysis analyze ./mods --quiet --output report.json
```

## Scan Command

List mods without full analysis.

### Basic Usage

```bash
simanalysis scan <directory>
```

### Examples

```bash
# List all mods
simanalysis scan ./mods

# With details
simanalysis scan ./mods --verbose

# Only .package files
simanalysis scan ./mods --extensions .package
```

## View Command

View previously generated reports.

### Basic Usage

```bash
simanalysis view <report_file>
```

### Examples

```bash
# View JSON report
simanalysis view report.json

# View with pager
simanalysis view report.json | less
```

## Working with Output

### Export Formats

#### JSON

Machine-readable, perfect for automation:

```bash
simanalysis analyze ./mods --output report.json --format json
```

Structure:
```json
{
  "metadata": {...},
  "mods": [...],
  "conflicts": [...],
  "summary": {...},
  "performance": {...}
}
```

#### TXT

Human-readable, terminal-friendly:

```bash
simanalysis analyze ./mods --output report.txt --format txt
```

#### YAML

Structured and readable:

```bash
simanalysis analyze ./mods --output report.yaml --format yaml
```

### Processing Output

#### Using jq (JSON)

```bash
# Count conflicts
simanalysis analyze ./mods --output report.json
jq '.conflicts | length' report.json

# Filter high-severity conflicts
jq '.conflicts[] | select(.severity == "HIGH")' report.json

# List mod names
jq '.mods[].name' report.json
```

#### Using grep (TXT)

```bash
# Find conflicts
simanalysis analyze ./mods --output report.txt
grep "CONFLICT" report.txt

# Count HIGH severity
grep -c "HIGH" report.txt
```

## Logging

### Log Levels

| Level | When to Use | Output |
|-------|-------------|--------|
| DEBUG | Development, troubleshooting | Everything |
| INFO | Normal operation | Important events |
| WARNING | Potential issues | Warnings and errors |
| ERROR | Failures only | Errors only |

### Log Files

#### Default Location

```
~/.simanalysis/logs/simanalysis.log
```

#### Custom Location

```bash
simanalysis analyze ./mods --log-file /path/to/custom.log
```

#### View Logs

```bash
# Tail logs
tail -f ~/.simanalysis/logs/simanalysis.log

# Search logs
grep ERROR ~/.simanalysis/logs/simanalysis.log

# View with less
less ~/.simanalysis/logs/simanalysis.log
```

## Common Workflows

### Workflow 1: Quick Check

```bash
# Quick analysis with TXT output
simanalysis analyze ./mods --output report.txt
cat report.txt
```

### Workflow 2: Detailed Investigation

```bash
# Full debug logging
simanalysis analyze ./mods \
  --log-level DEBUG \
  --log-file investigation.log \
  --output detailed_report.json
```

### Workflow 3: CI/CD Pipeline

```bash
# Silent analysis for automation
simanalysis analyze ./mods \
  --quiet \
  --output ci_report.json \
  --format json

# Check exit code
if [ $? -eq 0 ]; then
    echo "Analysis succeeded"
else
    echo "Analysis failed"
fi
```

### Workflow 4: Compare Two Collections

```bash
# Analyze collection 1
simanalysis analyze ./mods/collection1 --output c1.json

# Analyze collection 2
simanalysis analyze ./mods/collection2 --output c2.json

# Compare with jq
diff <(jq -S . c1.json) <(jq -S . c2.json)
```

## Interactive Mode (TUI)

Launch the text-based user interface:

```bash
simanalysis analyze ./mods --tui
```

Features:
- Navigate with arrow keys
- Filter conflicts by severity
- View mod details
- Export from interface

### TUI Controls

| Key | Action |
|-----|--------|
| ↑↓ | Navigate |
| Enter | Select |
| Tab | Switch panels |
| q | Quit |
| e | Export |
| f | Filter |
| s | Sort |

## Performance Tips

### For Large Collections (1000+ mods)

```bash
# Use quiet mode
simanalysis analyze ./mods --quiet --output report.json

# Limit file types
simanalysis analyze ./mods --extensions .package
```

### For Quick Scans

```bash
# Non-recursive
simanalysis analyze ./mods --no-recursive

# Or use scan command
simanalysis scan ./mods
```

## Troubleshooting

### No Mods Found

```bash
# Check directory
ls ./mods

# Try absolute path
simanalysis analyze /full/path/to/mods

# Check extensions
simanalysis scan ./mods --verbose
```

### Permission Denied

```bash
# Check permissions
ls -la ./mods

# Use sudo (not recommended)
sudo simanalysis analyze ./mods

# Or fix permissions
chmod -R u+r ./mods
```

### Analysis Takes Too Long

```bash
# Use non-recursive
simanalysis analyze ./mods --no-recursive

# Or analyze subdirectories separately
for dir in ./mods/*/; do
    simanalysis analyze "$dir" --output "$(basename $dir).json"
done
```

## Getting Help

### Built-in Help

```bash
# General help
simanalysis --help

# Command-specific help
simanalysis analyze --help
simanalysis scan --help
```

### Documentation

- [Understanding Conflicts](../user-guide/understanding-conflicts.md)
- [API Reference](../api/overview.md)
- [Examples](../examples/basic.md)

### Support

- [GitHub Issues](https://github.com/justaride/Simanalysis/issues)
- [Discussions](https://github.com/justaride/Simanalysis/discussions)

## Next Steps

- Learn about [Understanding Conflicts](../user-guide/understanding-conflicts.md)
- Explore [Advanced Examples](../examples/advanced.md)
- Read the [API Documentation](../api/overview.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
