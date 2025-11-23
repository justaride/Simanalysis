# Simanalysis Examples

This directory contains practical Python examples demonstrating the Simanalysis API.

## 📚 Available Examples

### 1. `basic_usage.py` - Getting Started

**Perfect for:** Beginners, quick integration, learning the basics

**Topics covered:**
- ✅ Analyzing a single mod file
- ✅ Analyzing a directory of mods
- ✅ Filtering conflicts by severity
- ✅ Exporting results to JSON/TXT
- ✅ Accessing performance metrics

**Run it:**
```bash
python examples/basic_usage.py
```

**Expected output:**
```
==================================================
SIMANALYSIS - BASIC USAGE EXAMPLES
==================================================

Example 1: Analyzing a Single Mod File
------------------------------------------------------
Analyzing: simple_mod.package
  DBPF Version: 2.1
  Resources: 1
  File Size: 314 bytes
  ...

Example 2: Analyzing a Directory
------------------------------------------------------
Analyzing directory: .../sample_mods
  Total Mods: 7
  Total Conflicts: 1
  ...
```

---

### 2. `advanced_usage.py` - Expert Techniques

**Perfect for:** Custom workflows, automation, integration

**Topics covered:**
- 🔧 Creating custom conflict detectors
- 📦 Batch processing multiple directories
- 📄 Custom report formats (Markdown)
- 🎯 Smart conflict resolution planning
- 🔗 External tool integration (JSON API)

**Run it:**
```bash
python examples/advanced_usage.py
```

**Key Features:**

**Custom Detector Example:**
```python
class DuplicateNameDetector(ConflictDetector):
    """Finds mods with similar names (potential duplicates)."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        # Your custom detection logic here
        ...
```

**Batch Processing:**
```python
def batch_analyze_directories(directories, output_dir):
    """Analyze multiple mod collections"""
    for directory in directories:
        result = analyzer.analyze_directory(directory)
        # Process results...
```

**Custom Reports:**
```python
def generate_markdown_report(result, output_file):
    """Generate Markdown report for GitHub/docs"""
    # Write formatted Markdown...
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install Simanalysis
pip install simanalysis

# Or from source
cd Simanalysis
pip install -e ".[dev]"
```

### Generate Test Fixtures (Optional)

The examples use test fixtures for demonstration:

```bash
cd tests/fixtures
python create_fixtures.py
```

### Run Examples

```bash
# Basic usage
python examples/basic_usage.py

# Advanced usage
python examples/advanced_usage.py
```

---

## 📖 Example Workflows

### Workflow 1: Pre-Release Mod Testing

```python
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from pathlib import Path

def test_my_mod(mod_path: Path) -> bool:
    """Test mod before release."""
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(mod_path.parent)

    # Check for critical conflicts
    critical = [c for c in result.conflicts
                if c.severity == "CRITICAL"]

    if critical:
        print(f"❌ {len(critical)} critical conflicts found!")
        return False

    print("✅ Mod passed analysis!")
    return True

# Usage
test_my_mod(Path("my_new_mod.package"))
```

### Workflow 2: Automated Conflict Reporting

```python
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
import json

def generate_daily_report(mods_dir):
    """Generate daily conflict report for mod collection."""
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(mods_dir)

    report = {
        "date": str(result.metadata.timestamp),
        "total_mods": len(result.mods),
        "new_conflicts": len(result.conflicts),
        "high_priority": len([c for c in result.conflicts
                             if c.severity in ["HIGH", "CRITICAL"]])
    }

    with open("daily_report.json", "w") as f:
        json.dump(report, f, indent=2)

    return report
```

### Workflow 3: CI/CD Integration

```python
#!/usr/bin/env python3
"""CI/CD Script: Check for conflicts before deployment."""
import sys
from pathlib import Path
from simanalysis.analyzers.mod_analyzer import ModAnalyzer

def ci_check(mods_dir: Path) -> int:
    """
    Run analysis in CI/CD pipeline.

    Returns:
        0: Success (no critical conflicts)
        1: Failure (critical conflicts found)
    """
    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(mods_dir)

    critical_conflicts = [c for c in result.conflicts
                          if c.severity == "CRITICAL"]

    if critical_conflicts:
        print(f"::error::Found {len(critical_conflicts)} critical conflicts")
        for conflict in critical_conflicts:
            print(f"::error::{conflict.description}")
        return 1

    print(f"::notice::Analysis passed - {len(result.mods)} mods, {len(result.conflicts)} conflicts")
    return 0

if __name__ == "__main__":
    sys.exit(ci_check(Path(sys.argv[1])))
```

**Use in GitHub Actions:**
```yaml
- name: Check mod conflicts
  run: python check_conflicts.py ./mods
```

---

## 🎓 Learning Path

**Level 1: Beginner**
1. Run `basic_usage.py`
2. Modify it to analyze your own mods
3. Try different export formats

**Level 2: Intermediate**
4. Run `advanced_usage.py`
5. Create a custom detector for your specific needs
6. Generate custom reports

**Level 3: Advanced**
7. Integrate with your mod manager
8. Create automated workflows
9. Build CI/CD pipelines
10. Contribute custom detectors back to the project

---

## 📝 Code Templates

### Template: Custom Detector

```python
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import Mod, ModConflict, Severity, ConflictType
from typing import List

class MyCustomDetector(ConflictDetector):
    """Detects my specific type of conflict."""

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        conflicts = []

        # Your detection logic here
        # Example: check for something specific
        for mod in mods:
            if self._has_issue(mod):
                conflict = ModConflict(
                    id=f"custom_{mod.name}",
                    severity=Severity.MEDIUM,
                    type=ConflictType.OTHER,
                    affected_mods=[mod.name],
                    description="Custom issue detected",
                    resolution="How to fix it"
                )
                conflicts.append(conflict)

        return conflicts

    def _has_issue(self, mod: Mod) -> bool:
        """Check if mod has the issue."""
        # Your check logic
        return False
```

### Template: Custom Report

```python
def generate_custom_report(result, output_file):
    """Generate report in your preferred format."""
    with open(output_file, 'w') as f:
        # Write header
        f.write(f"Analysis Report\n")
        f.write(f"="*50 + "\n\n")

        # Write summary
        f.write(f"Mods: {len(result.mods)}\n")
        f.write(f"Conflicts: {len(result.conflicts)}\n\n")

        # Write details
        for conflict in result.conflicts:
            f.write(f"- {conflict.description}\n")

        # Add your custom sections
        # ...
```

---

## 🔗 Related Resources

- **Main Documentation:** See `USAGE_EXAMPLES.md` in project root
- **API Reference:** (Coming soon with MkDocs)
- **Test Fixtures:** `tests/fixtures/README.md`
- **Contributing:** See `CONTRIBUTING.md`

---

## 💡 Tips & Tricks

1. **Start Simple:** Begin with `basic_usage.py` and modify incrementally
2. **Use Test Fixtures:** The `tests/fixtures/sample_mods/` directory has ready-to-use examples
3. **Check Return Types:** Use type hints to understand what methods return
4. **Read the Source:** The code is well-documented - explore `src/simanalysis/`
5. **Ask Questions:** Open an issue if examples are unclear

---

## 🤝 Contributing Examples

Have a useful example? We'd love to include it!

1. Create your example script
2. Add documentation to this README
3. Test it works standalone
4. Submit a pull request

**Example ideas we'd love to see:**
- Integration with specific mod managers
- GUI applications using Simanalysis
- Web API wrappers
- Discord bot integrations
- Automated mod pack testing

---

**Version:** 3.0.0
**Last Updated:** 2025-11-23
**License:** MIT
