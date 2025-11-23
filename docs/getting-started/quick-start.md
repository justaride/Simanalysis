# Quick Start

Get up and running with Simanalysis in 5 minutes.

## 1. Install

```bash
pip install simanalysis
```

## 2. Analyze Your Mods

=== "Windows"

    ```powershell
    simanalysis analyze "C:\Users\YourName\Documents\Electronic Arts\The Sims 4\Mods"
    ```

=== "macOS"

    ```bash
    simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods
    ```

=== "Linux"

    ```bash
    simanalysis analyze ~/.local/share/TheSims4/Mods
    ```

## 3. View Results

The analysis will display:

- ✅ Total mods found
- ⚠️ Conflicts detected
- 📊 Performance metrics
- 💡 Recommendations

Example output:

```
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

Performance:
  Size: 45.2 MB
  Resources: 2,847
  Load Time: ~2.3s
```

## Common Tasks

### Export to JSON

```bash
simanalysis analyze ./mods --output report.json --format json
```

### Filter by Type

```bash
# Only analyze .package files
simanalysis analyze ./mods --extensions .package

# Only analyze scripts
simanalysis analyze ./mods --extensions .ts4script
```

### Enable Debug Logging

```bash
simanalysis analyze ./mods --log-level DEBUG --log-file debug.log
```

### Interactive TUI Mode

```bash
simanalysis analyze ./mods --tui
```

## Next Steps

### For Mod Users

1. Review the [Understanding Conflicts](../user-guide/understanding-conflicts.md) guide
2. Learn about [Exporting Reports](../user-guide/exporting-reports.md)
3. Set up [automated analysis](../examples/cicd.md)

### For Mod Creators

1. Check [Basic Examples](../examples/basic.md)
2. Explore the [Python API](../api/overview.md)
3. Integrate into your [development workflow](../examples/advanced.md)

### For Developers

1. Read the [API Reference](../api/overview.md)
2. Try [Advanced Examples](../examples/advanced.md)
3. Learn about [Custom Detectors](../development/contributing.md)

## Getting Help

- 📖 [Full Documentation](../index.md)
- 💬 [GitHub Discussions](https://github.com/justaride/Simanalysis/discussions)
- 🐛 [Report Issues](https://github.com/justaride/Simanalysis/issues)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
