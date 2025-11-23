# 🔬 Simanalysis

**Derrick - The PhD in Simology**
*Surgical analysis of Sims 4 mods and CC. When creators complexify The Sim Universe, we need surveyors.*

[![Tests](https://github.com/justaride/Simanalysis/actions/workflows/tests.yml/badge.svg)](https://github.com/justaride/Simanalysis/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/justaride/Simanalysis/branch/main/graph/badge.svg)](https://codecov.io/gh/justaride/Simanalysis)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## ⚡ Quickstart

```bash
# Install
pip install simanalysis

# Analyze your mods (interactive mode - recommended!)
simanalysis analyze "~/Documents/Electronic Arts/The Sims 4/Mods" --interactive

# Or use beautiful Rich TUI for quick check
simanalysis analyze ~/Mods --tui

# Export detailed report
simanalysis analyze ~/Mods --output report.json --format json

# ⭐ NEW: Find unused CC (save disk space!)
simanalysis save-scan ~/saves ~/Mods --output usage_report.txt

# Check save for missing CC
simanalysis save-check MySave.save ~/Mods

# Generate CC list for sharing Sims
simanalysis tray-cc MySim.trayitem ~/Mods --output required_cc.txt
```

**That's it!** Simanalysis will:
- ✅ Scan all your mods and CC
- 🔍 Detect conflicts, duplicates, and compatibility issues
- 📊 Show performance impact and load time estimates
- 💡 Provide actionable recommendations
- 📤 Export detailed reports
- 💾 **NEW:** Identify used/unused CC and generate sharing lists

---

## 🎯 What Is Simanalysis?

Simanalysis is a **proactive conflict detection and analysis tool** for The Sims 4 mods. Unlike runtime error trackers (like Better Exceptions), Simanalysis performs **static analysis** of your entire mod collection *before* you launch the game, identifying conflicts, duplicates, and compatibility issues.

### 🆚 How It Differs from Better Exceptions

| Feature | Simanalysis | Better Exceptions |
|---------|-------------|-------------------|
| **When** | Before game launch | During/after errors |
| **Approach** | Proactive prevention | Reactive debugging |
| **Detection** | Static file analysis | Runtime monitoring |
| **Conflicts** | Finds "silent" conflicts | Finds crash-causing errors |
| **Detail** | Tuning-level precision | Error traces |

**Use both together:** Simanalysis prevents 80-90% of issues before launch, Better Exceptions catches unexpected runtime bugs.

---

## ✨ Features

### 🔍 **Deep Conflict Detection**
- **Tuning Overlaps**: Identifies when multiple mods modify the same game tuning
- **Resource Duplicates**: Finds identical or conflicting resources (textures, meshes, objects)
- **Script Injections**: Detects when scripts hook into the same game functions
- **Hash Collisions**: Discovers duplicate files packaged separately

### 📊 **Comprehensive Analysis**
- **Performance Metrics**: Estimates load time, memory usage, and complexity
- **Dependency Mapping**: Tracks mod requirements and pack dependencies
- **Severity Classification**: CRITICAL/HIGH/MEDIUM/LOW priority system
- **Smart Recommendations**: Actionable advice for resolving conflicts

### 💾 **Save File & CC Analysis** ⭐ NEW IN v4.0!
- **Used CC Detection**: Identifies which CC is actually used in your saves
- **Unused CC Cleanup**: Find CC that's safe to remove (often 5-10 GB!)
- **Missing CC Detection**: Check saves for missing/broken custom content
- **Tray CC Lists**: Generate required CC lists for sharing Sims
- **Usage Analytics**: Track CC usage frequency across all saves

### 📝 **Professional Reports**
- **Text Reports**: Human-readable summaries with conflict details
- **JSON Export**: Machine-readable format for integration
- **Detailed Conflict Info**: Tuning IDs, resource keys, affected attributes

### 🎮 **Supported File Types**
- ✅ `.package` files (DBPF format)
- ✅ `.ts4script` files (Python mods)
- ✅ XML tuning data
- ✅ Recursive directory scanning

---

## 🚀 Installation

### Prerequisites
- Python 3.9 or higher
- The Sims 4 (obviously!)

### Install via pip (Recommended)

```bash
pip install simanalysis
```

### Install from source

```bash
# Clone the repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Install in development mode
pip install -e .

# Or install dependencies manually
pip install -r requirements.txt
```

---

## 📖 Usage

### Command-Line Interface (CLI)

The easiest way to use Simanalysis is through the command-line interface:

```bash
# Interactive mode with keyboard navigation (best experience!)
simanalysis analyze "~/Documents/Electronic Arts/The Sims 4/Mods" --interactive

# Analyze with beautiful Rich TUI (great for one-time analysis)
simanalysis analyze ~/Mods --tui

# Analyze with mod list displayed
simanalysis analyze ~/Mods --tui --show-mods

# Standard CLI output
simanalysis analyze ~/Mods

# Quick scan with TUI
simanalysis scan ~/Mods --tui --verbose

# Quick scan (faster, no hashing)
simanalysis analyze ~/Mods --quick

# Export detailed report
simanalysis analyze ~/Mods --output report.json --format json

# Verbose output with conflict details
simanalysis analyze ~/Mods --verbose

# Quick directory scan (no conflict detection)
simanalysis scan ~/Mods

# View a saved report
simanalysis view report.json

# Show program info
simanalysis info
```

#### Interactive Terminal Interface

For the **best experience**, use the `--interactive` (or `-i`) flag for a fully interactive application:
- ⌨️  **Keyboard navigation** - Use arrow keys, Tab, and shortcuts
- 📑 **Tabbed interface** - Switch between Conflicts, Mods, and Details
- 🔍 **Filtering** - Filter conflicts by severity level
- 📤 **Export dialog** - Save reports to TXT or JSON interactively
- 📊 **Live tables** - Browse conflicts and mods with sortable tables
- ❓ **Built-in help** - Press `?` for keyboard shortcuts

#### Rich Terminal Interface (TUI)

For beautiful one-time analysis, use the `--tui` flag:
- 🎨 **Beautiful colored output** with tables, panels, and trees
- 📊 **Visual progress bars** during analysis
- 🔍 **Hierarchical conflict view** grouped by severity
- 📈 **Performance metrics dashboard**
- 💡 **Color-coded recommendations**

The interactive mode uses [Textual](https://github.com/Textualize/textual) for a full TUI app, while the Rich TUI uses [Rich](https://github.com/Textualize/rich) for beautiful static output.

#### CLI Options

**analyze** - Full analysis with conflict detection:
- `--interactive, -i` - Interactive mode with keyboard navigation (**recommended**)
- `--tui` - Rich terminal interface (beautiful output)
- `--show-mods` - Show detailed mod list (TUI mode only)
- `--output, -o PATH` - Export report to file
- `--format, -f [txt|json]` - Report format (default: txt)
- `--quick, -q` - Skip hash calculation (faster)
- `--no-tunings` - Skip tuning parsing
- `--no-scripts` - Skip script analysis
- `--recursive/--no-recursive` - Scan subdirectories (default: recursive)
- `--verbose, -v` - Show detailed output

**scan** - Quick directory scan without analysis:
- `--tui` - Use Rich terminal interface
- `--recursive/--no-recursive` - Scan subdirectories
- `--verbose, -v` - Show mod list

**view** - View saved JSON report

**info** - Show program information

### Python API

You can also use Simanalysis as a Python library:

```python
from pathlib import Path
from simanalysis.analyzers import ModAnalyzer

# Create analyzer
analyzer = ModAnalyzer()

# Analyze your Mods folder
result = analyzer.analyze_directory(
    Path("~/Documents/Electronic Arts/The Sims 4/Mods").expanduser()
)

# View results
print(f"Found {len(result.mods)} mods")
print(f"Detected {len(result.conflicts)} conflicts")
print(f"Critical issues: {len(result.critical_conflicts)}")

# Get recommendations
summary = analyzer.get_summary(result)
recommendations = analyzer.get_recommendations(result)

for rec in recommendations:
    print(rec)
```

### Export Reports

```python
from pathlib import Path

# Export text report
analyzer.export_report(
    result,
    Path("~/Desktop/mod_analysis.txt"),
    format="txt"
)

# Export JSON report
analyzer.export_report(
    result,
    Path("~/Desktop/mod_analysis.json"),
    format="json"
)
```

### Advanced Options

```python
# Customize analysis
analyzer = ModAnalyzer(
    parse_tunings=True,      # Parse XML tunings (default: True)
    parse_scripts=True,      # Analyze Python scripts (default: True)
    calculate_hashes=True,   # Calculate file hashes (default: True)
)

# Scan specific extensions
result = analyzer.analyze_directory(
    mods_path,
    recursive=True,
    extensions={".package", ".ts4script"}
)
```

### Analyzing Pre-Scanned Mods

```python
from simanalysis.scanners import ModScanner

# Scan mods separately
scanner = ModScanner()
mods = scanner.scan_directory(mods_path)

# Analyze later
result = analyzer.analyze_mods(mods)
```

---

## 📊 Understanding Results

### Conflict Types

| Type | Description | Severity |
|------|-------------|----------|
| `TUNING_OVERLAP` | Multiple mods modify same tuning | CRITICAL if core tuning |
| `RESOURCE_DUPLICATE` | Identical resource keys | MEDIUM-CRITICAL |
| `SCRIPT_INJECTION` | Scripts hook same function | HIGH |
| `DEPENDENCY_MISSING` | Required mod not found | HIGH |
| `VERSION_CONFLICT` | Incompatible mod versions | MEDIUM |
| `NAMESPACE_COLLISION` | Python namespace conflicts | HIGH |

### Severity Levels

- 🔴 **CRITICAL**: May cause crashes or severe instability
- 🟠 **HIGH**: Significant issues, features may break
- 🟡 **MEDIUM**: Moderate issues, some conflicts
- 🟢 **LOW**: Minor issues, cosmetic conflicts

### Example Output

```
⚠️  CRITICAL: 3 critical conflicts detected.
  - Tuning 'buff_confident' (ID: 0x12345678) modified by 2 mods
  - Resource 0x0333406C (Object Definition) in 3 mods
  - Script injection conflict in sim_info module

💡 TIP: 5 duplicate mods found (15MB wasted space)

✅ 142 mods have no conflicts
```

---

## 🏗️ Project Structure

```
simanalysis/
├── src/simanalysis/
│   ├── analyzers/          # Analysis pipeline
│   │   └── mod_analyzer.py # Main analyzer class
│   ├── detectors/          # Conflict detectors
│   │   ├── base.py         # Base detector framework
│   │   ├── tuning_conflicts.py
│   │   └── resource_conflicts.py
│   ├── parsers/            # File format parsers
│   │   ├── dbpf.py         # DBPF package parser
│   │   ├── tuning.py       # XML tuning parser
│   │   └── script.py       # Python script analyzer
│   ├── scanners/           # Directory scanning
│   │   └── mod_scanner.py  # Recursive mod finder
│   ├── models.py           # Data models
│   ├── exceptions.py       # Custom exceptions
│   └── __init__.py
│
├── tests/                  # Test suite (175 tests, 93% coverage)
│   ├── unit/
│   │   ├── analyzers/
│   │   ├── detectors/
│   │   ├── parsers/
│   │   └── scanners/
│   └── integration/
│
├── docs/                   # Documentation
│   ├── TECHNICAL_SPECIFICATION.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   └── CONTRIBUTING.md
│
├── pyproject.toml         # Package configuration
├── pytest.ini             # Test configuration
└── README.md
```

---

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/simanalysis --cov-report=html

# Run specific test module
pytest tests/unit/detectors/

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

---

## 📚 Documentation

- [Technical Specification](docs/TECHNICAL_SPECIFICATION.md) - Detailed architecture
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md) - Development plan
- [Project Structure](docs/PROJECT_STRUCTURE.md) - Code organization
- [Contributing Guide](CONTRIBUTING.md) - How to contribute

---

## 🔮 Roadmap

### Current Version (2.0.0)
- ✅ Complete file format parsing
- ✅ Tuning and resource conflict detection
- ✅ Performance metrics
- ✅ Report generation

### Planned Features
- 🔄 CLI interface (`simanalysis analyze /path/to/mods`)
- 🔄 HTML report with interactive UI
- 🔄 Mod compatibility database
- 🔄 Automatic fix suggestions
- 🔄 Integration with mod managers

---

## 🐛 Troubleshooting

### Common Issues

**Q: "No conflicts detected but game still crashes"**
A: Simanalysis detects static conflicts. Some issues only occur at runtime (hardware-specific, game bugs, etc.). Use Better Exceptions to catch these.

**Q: "Analysis is slow with many mods"**
A: Disable hash calculation for faster scans:
```python
analyzer = ModAnalyzer(calculate_hashes=False)
```

**Q: "Can't find certain conflicts"**
A: Ensure parsing is enabled:
```python
analyzer = ModAnalyzer(
    parse_tunings=True,
    parse_scripts=True
)
```

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

- **TwistedMexi** - Inspiration from Better Exceptions
- **Sims 4 Modding Community** - For creating amazing mods
- **Contributors** - Everyone who helps improve this tool

---

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/justaride/Simanalysis/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/justaride/Simanalysis/discussions)
- 📧 **Contact**: Via GitHub

---

## 🌟 Star History

If this tool helped you, consider giving it a star! ⭐

---

*"In complexity, we find clarity. In chaos, we find patterns."* - Derrick, PhD in Simology

**Made with ❤️ for The Sims modding community**
