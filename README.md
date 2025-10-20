# Simanalysis 🔬

**Derrick - The PhD in Simology and Complexity Theory**

When creators complexify The Sim Universe with modifications within EA's restrictive parameters, we need surgeons and surveyors. That is Derrick's passion.

## Overview

Simanalysis is an AI-powered analysis tool for The Sims 4 mods and custom content. Built with Claude Code integration, it provides deep insights into mod conflicts, performance impacts, and compatibility issues.

## Features

- **Conflict Detection**: Identify tuning conflicts, resource overlaps, and script collisions
- **Performance Analysis**: Assess mod impact on game performance
- **Dependency Mapping**: Visualize mod dependencies and requirements
- **XML Tuning Analysis**: Deep dive into tuning modifications
- **Package Inspection**: Extract and analyze .package file contents
- **AI-Powered Insights**: Leverage Claude's understanding of mod complexity

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
```

### AI-Assisted Analysis
```bash
# Use with Claude Code
claude analyze-mods --path ~/Mods --deep-scan
```

## Project Structure

```
Simanalysis/
├── .codex/              # Codex AI configuration
│   ├── config.json      # Project settings
│   └── prompts.md       # Analysis prompts
├── src/                 # Source code
│   ├── analyzer.py      # Core analysis engine
│   ├── parser.py        # Package/XML parsing
│   └── detector.py      # Conflict detection
├── tests/               # Test suite
└── README.md
```

## Contributing

Contributions welcome! This tool is built for the Sims modding community.

## License

MIT License - Use freely, mod responsibly

---

*"In complexity, we find clarity. In chaos, we find patterns."* - Derrick
