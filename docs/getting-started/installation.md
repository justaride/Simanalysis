# Installation

This guide covers different ways to install Simanalysis.

## Requirements

- **Python**: 3.9 or higher
- **Operating System**: Windows, macOS, or Linux
- **Disk Space**: ~100 MB (including dependencies)

## Installation Methods

### Method 1: pip (Recommended)

The easiest way to install Simanalysis:

```bash
pip install simanalysis
```

Verify installation:

```bash
simanalysis --version
```

### Method 2: From Source

For development or latest features:

```bash
# Clone the repository
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Install in development mode
pip install -e ".[dev]"
```

### Method 3: Docker

No Python installation needed:

```bash
docker pull simanalysis:latest
```

See the [Docker Guide](../DOCKER.md) for details.

## Optional Dependencies

### For AI Features

```bash
pip install simanalysis[ai]
```

### For Development

```bash
pip install simanalysis[dev]
```

Includes:
- pytest (testing)
- pytest-cov (coverage)
- ruff (linting)
- mypy (type checking)
- pre-commit (git hooks)

### For Documentation

```bash
pip install simanalysis[docs]
```

Includes:
- mkdocs
- mkdocs-material
- mkdocstrings

### Install Everything

```bash
pip install simanalysis[all]
```

## Verify Installation

### Check Version

```bash
simanalysis --version
```

Expected output:
```
Simanalysis version 3.0.0
```

### Run Help

```bash
simanalysis --help
```

### Test with Fixtures

```bash
# Clone the repository to get test fixtures
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis

# Generate fixtures
cd tests/fixtures
python create_fixtures.py

# Test analysis
cd ../..
simanalysis analyze tests/fixtures/sample_mods
```

## Platform-Specific Notes

### Windows

#### Using Command Prompt

```cmd
pip install simanalysis
simanalysis --version
```

#### Using PowerShell

```powershell
pip install simanalysis
simanalysis --version
```

#### Path Issues

If `simanalysis: command not found`, add Python Scripts to PATH:

1. Find Python Scripts directory:
   ```cmd
   python -m site --user-site
   ```
2. Add parent `Scripts` folder to PATH
3. Restart terminal

### macOS

#### Using Homebrew Python

```bash
brew install python@3.11
pip3 install simanalysis
simanalysis --version
```

#### Using System Python

```bash
python3 -m pip install simanalysis
python3 -m simanalysis --version
```

### Linux

#### Ubuntu/Debian

```bash
# Install Python 3.9+
sudo apt update
sudo apt install python3 python3-pip

# Install Simanalysis
pip3 install simanalysis

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### Fedora/RHEL

```bash
sudo dnf install python3 python3-pip
pip3 install simanalysis
```

#### Arch Linux

```bash
sudo pacman -S python python-pip
pip install simanalysis
```

## Virtual Environments (Recommended)

Using virtual environments keeps your system Python clean:

### Using venv

```bash
# Create virtual environment
python -m venv simanalysis-env

# Activate (Linux/macOS)
source simanalysis-env/bin/activate

# Activate (Windows)
simanalysis-env\Scripts\activate

# Install
pip install simanalysis

# Deactivate when done
deactivate
```

### Using conda

```bash
# Create environment
conda create -n simanalysis python=3.11

# Activate
conda activate simanalysis

# Install
pip install simanalysis

# Deactivate
conda deactivate
```

## Upgrading

### Upgrade to Latest

```bash
pip install --upgrade simanalysis
```

### Upgrade to Specific Version

```bash
pip install simanalysis==3.0.0
```

### Check for Updates

```bash
pip list --outdated | grep simanalysis
```

## Uninstallation

```bash
pip uninstall simanalysis
```

## Troubleshooting

### pip: command not found

Install pip:

```bash
# Linux
sudo apt install python3-pip

# macOS
python3 -m ensurepip

# Windows
python -m ensurepip
```

### Permission Denied

Use `--user` flag:

```bash
pip install --user simanalysis
```

### SSL Certificate Error

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org simanalysis
```

### Dependency Conflicts

Use a virtual environment or:

```bash
pip install simanalysis --no-deps
pip install -r requirements.txt
```

## Getting Help

- **Installation Issues**: [GitHub Issues](https://github.com/justaride/Simanalysis/issues)
- **General Help**: [Documentation Home](../index.md)
- **Docker Help**: [Docker Guide](../DOCKER.md)

## Next Steps

- [Quick Start Guide](quick-start.md)
- [Basic Usage](basic-usage.md)
- [API Reference](../api/overview.md)

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
