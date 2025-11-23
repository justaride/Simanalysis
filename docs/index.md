# Simanalysis Documentation

Welcome to the official documentation for **Simanalysis** - a comprehensive analyzer for The Sims 4 mod files.

## What is Simanalysis?

Simanalysis is a powerful Python tool that analyzes Sims 4 mods (.package and .ts4script files) to detect conflicts, validate integrity, and provide detailed insights into your mod collection.

### Key Features

✅ **Conflict Detection**: Automatically detect tuning overlaps, resource collisions, and script conflicts
✅ **Deep Analysis**: Parse DBPF packages, XML tunings, and Python scripts
✅ **Performance Metrics**: Estimate load times, memory usage, and complexity
✅ **Multiple Formats**: Export to JSON, TXT, YAML
✅ **CLI & Python API**: Use from command-line or integrate into your tools
✅ **Production Ready**: 240+ tests, 40% coverage, comprehensive logging

## Quick Start

### Installation

```bash
pip install simanalysis
```

### Basic Usage

=== "Command Line"

    ```bash
    # Analyze your Mods folder
    simanalysis analyze ~/Documents/"Electronic Arts"/"The Sims 4"/Mods

    # Export to JSON
    simanalysis analyze ./mods --output report.json
    ```

=== "Python API"

    ```python
    from pathlib import Path
    from simanalysis.analyzers.mod_analyzer import ModAnalyzer

    # Analyze directory
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(Path("./mods"))

    # Check conflicts
    print(f"Found {len(result.conflicts)} conflicts")
    for conflict in result.conflicts:
        print(f"  - {conflict.description}")
    ```

## Use Cases

### For Mod Users
- 🔍 Find conflicts before they cause issues
- 📊 Understand your mod collection
- 🛠️ Troubleshoot load order problems
- ⚡ Optimize for better performance

### For Mod Creators
- ✅ Test mods before release
- 🔬 Validate package structure
- 📝 Generate compatibility reports
- 🤝 Check for conflicts with popular mods

### For Mod Collection Curators
- 📦 Manage large mod collections
- 🔄 Automate conflict checking
- 📈 Track collection health
- 🚀 CI/CD integration

## Example Output

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
     Resolution: Keep only one mod or use compatibility patch

Performance Metrics:
  Total Size: 45.2 MB
  Resources: 2,847
  Est. Load Time: 2.3s
  Complexity: Medium
```

## Project Status

| Component | Status | Coverage |
|-----------|--------|----------|
| **DBPF Parser** | ✅ Production | 71% |
| **Tuning Parser** | ✅ Production | 93% |
| **Script Analyzer** | ✅ Production | 32% |
| **Conflict Detection** | ✅ Production | 76% |
| **CLI** | ✅ Production | 39% |
| **Overall** | ✅ v3.0.0 | 40% |

## Getting Help

- 📖 **Documentation**: You're reading it!
- 💡 **Examples**: See `examples/` directory
- 🐛 **Issues**: [GitHub Issues](https://github.com/justaride/Simanalysis/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/justaride/Simanalysis/discussions)

## Next Steps

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } __Quick Start__

    ---

    Get up and running in 5 minutes

    [:octicons-arrow-right-24: Quick Start Guide](getting-started/quick-start.md)

-   :material-book-open-variant:{ .lg .middle } __User Guide__

    ---

    Learn how to analyze mods and understand conflicts

    [:octicons-arrow-right-24: User Guide](user-guide/analyzing-mods.md)

-   :material-code-braces:{ .lg .middle } __API Reference__

    ---

    Comprehensive Python API documentation

    [:octicons-arrow-right-24: API Docs](api/overview.md)

-   :material-lightbulb:{ .lg .middle } __Examples__

    ---

    Real-world examples and integration patterns

    [:octicons-arrow-right-24: View Examples](examples/basic.md)

</div>

## Features in Detail

### DBPF Parser
Parse The Sims 4 package files with full binary format support:
- ✅ Header and index parsing
- ✅ Resource extraction with ZLib decompression
- ✅ Sub-millisecond performance (690+ MB/s)
- ✅ Comprehensive error handling

### Tuning Parser
Analyze XML tuning resources:
- ✅ Instance ID extraction
- ✅ Module and class detection
- ✅ Attribute parsing with namespace support
- ✅ Pack requirement detection

### Script Analyzer
Deep analysis of .ts4script files:
- ✅ ZIP archive parsing
- ✅ AST analysis for Python code
- ✅ Import detection
- ✅ Injection pattern identification

### Conflict Detection
Smart conflict detection with severity classification:
- ✅ Tuning overlaps (multiple mods modifying same tuning)
- ✅ Resource collisions (hash conflicts)
- ✅ Script injection conflicts
- ✅ Severity: CRITICAL, HIGH, MEDIUM, LOW

### Export Formats
- **JSON**: Machine-readable, perfect for automation
- **TXT**: Human-readable, terminal-friendly
- **YAML**: Structured data, easy to read and edit

## Architecture

```
simanalysis/
├── parsers/          # Binary and text file parsers
│   ├── dbpf.py      # DBPF package parser
│   ├── tuning.py    # XML tuning parser
│   └── script.py    # Python script analyzer
├── analyzers/        # High-level analysis
│   └── mod_analyzer.py
├── detectors/        # Conflict detection
│   ├── tuning_conflicts.py
│   └── resource_conflicts.py
├── scanners/         # File discovery
│   └── mod_scanner.py
├── models.py         # Data models
└── cli.py            # Command-line interface
```

## Contributing

We welcome contributions! See our [Contributing Guide](development/contributing.md) for details.

## License

Simanalysis is released under the [MIT License](license.md).

---

**Version**: 3.0.0 | **Status**: Production Ready | **Python**: 3.9+
