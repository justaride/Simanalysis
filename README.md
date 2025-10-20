# Simanalysis 🔬

**Derrick - The PhD in Simology and Complexity Theory**

When creators complexify The Sim Universe with modifications within EA's restrictive parameters, we need surgeons and surveyors. That is Derrick's passion.

## Overview

Simanalysis is an AI-powered analysis tool for The Sims 4 mods and custom content. Built with Claude Code integration, it provides deep insights into mod conflicts, performance impacts, and compatibility issues.

## Features

- **Conflict Detection**: Identify tuning conflicts, resource overlaps, and script collisions
- **Resource Introspection**: Parse `.package` files for duplicate Type/Group/Instance records
- **Script Intelligence**: Inspect `.ts4script` archives for module collisions and framework dependencies
- **Performance Analysis**: Assess mod impact on game performance
- **Dependency Mapping**: Visualize mod dependencies and requirements
- **XML Tuning Analysis**: Deep dive into tuning modifications
- **Package Inspection**: Extract and analyze `.package` file contents
- **AI-Powered Insights**: Leverage Claude's understanding of mod complexity
- **Roadmapped Runtime Monitoring**: See the [architecture plan](docs/architecture.md) for live telemetry and reporting goals.

## Codex Integration

This repository is optimized for Claude Code with:
- `.codex/` configuration for AI-assisted analysis
- Custom prompts for Sims 4 domain expertise
- MCP (Model Context Protocol) integration
- Automated conflict detection workflows

## Installation

```bash
# Clone the repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Analysis
```python
from simanalysis import ModAnalyzer

analyzer = ModAnalyzer()
results = analyzer.analyze_directory("/path/to/mods")
print(results.conflicts)
print(results.dependencies)
```

### Command-Line Report Generation
```
python -m src.main /path/to/mods --exceptions --output sims4_mod_report.html
```

This command prints a detailed summary to the console and (optionally) writes
an HTML report. Use `--exceptions` to include summaries from any
`lastException.txt` logs located near the scan path or the standard Sims 4
documents folder.

### AI-Assisted Analysis
```bash
# Use with Claude Code
claude analyze-mods --path ~/Mods --deep-scan
```

## Project Structure

```
Simanalysis/
├── docs/                # Project plans and architecture docs
│   └── architecture.md  # Long-term vision for the analyzer
├── src/                 # Source code
│   └── analyzer.py      # Core analysis engine
├── README.md
└── requirements.txt
```

For a deep dive into planned capabilities—static analysis, runtime instrumentation, and remediation workflows—see [docs/architecture.md](docs/architecture.md).

## Contributing

Contributions welcome! This tool is built for the Sims modding community.

## License

MIT License - Use freely, mod responsibly

---

*"In complexity, we find clarity. In chaos, we find patterns."* - Derrick
