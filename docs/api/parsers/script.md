# Script Parser

Analyze Python script mods (.ts4script files) for The Sims 4.

## Overview

The Script Parser analyzes .ts4script files (ZIP archives containing Python code) to extract metadata, detect imports, and identify injection patterns.

## Quick Example

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

# Analyze script mod
analyzer = ScriptAnalyzer()
script_info = analyzer.analyze(Path("awesome_mod.ts4script"))

print(f"Name: {script_info.name}")
print(f"Python files: {len(script_info.python_files)}")
print(f"Imports: {len(script_info.imports)}")
print(f"Injections: {len(script_info.injections)}")
```

## API Reference

::: simanalysis.parsers.script
    options:
      show_root_heading: true
      show_source: true
      members:
        - ScriptInfo
        - ImportInfo
        - InjectionInfo
        - ScriptAnalyzer
      group_by_category: true

## ScriptInfo Structure

The analyzer returns a `ScriptInfo` object:

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | str | Script mod name |
| `path` | Path | Path to .ts4script file |
| `size` | int | File size in bytes |
| `python_files` | List[str] | List of .py files in archive |
| `imports` | List[ImportInfo] | Imported modules |
| `injections` | List[InjectionInfo] | Detected injection patterns |
| `has_init` | bool | Whether __init__.py exists |

## ImportInfo Structure

Information about imports:

| Attribute | Type | Description |
|-----------|------|-------------|
| `module` | str | Module name (e.g., "sims4.commands") |
| `names` | List[str] | Imported names (if "from" import) |
| `alias` | str \| None | Import alias (if "as") |
| `source_file` | str | File containing the import |

## InjectionInfo Structure

Information about detected injections:

| Attribute | Type | Description |
|-----------|------|-------------|
| `target` | str | Target function/method |
| `type` | str | Injection type ("wrap", "replace", "before", "after") |
| `source_file` | str | File containing injection |
| `line_number` | int | Line number in source |

## File Format

.ts4script files are ZIP archives containing Python code:

```
awesome_mod.ts4script (ZIP archive)
├── awesome_mod/
│   ├── __init__.py
│   ├── main.py
│   ├── utils.py
│   └── config.py
└── other_files...
```

## Usage Examples

### Example 1: List Python Files

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

analyzer = ScriptAnalyzer()
script_info = analyzer.analyze(Path("mod.ts4script"))

print("Python files:")
for py_file in script_info.python_files:
    print(f"  - {py_file}")
```

### Example 2: Analyze Imports

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

analyzer = ScriptAnalyzer()
script_info = analyzer.analyze(Path("mod.ts4script"))

print(f"Total imports: {len(script_info.imports)}")

# Group by module
from collections import defaultdict
by_module = defaultdict(list)

for imp in script_info.imports:
    by_module[imp.module].append(imp.source_file)

print("\nImports by module:")
for module, files in sorted(by_module.items()):
    print(f"  {module}: {len(files)} files")
```

### Example 3: Detect Injections

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

analyzer = ScriptAnalyzer()
script_info = analyzer.analyze(Path("mod.ts4script"))

if script_info.injections:
    print("Detected injections:")
    for injection in script_info.injections:
        print(f"  [{injection.type}] {injection.target}")
        print(f"    File: {injection.source_file}:{injection.line_number}")
else:
    print("No injections detected")
```

### Example 4: Find Script Conflicts

```python
from pathlib import Path
from collections import defaultdict
from simanalysis.parsers.script import ScriptAnalyzer

def find_injection_conflicts(script_mods: list[Path]) -> dict:
    """Find scripts that inject into the same targets."""
    analyzer = ScriptAnalyzer()
    injection_map = defaultdict(list)

    for script_path in script_mods:
        try:
            script_info = analyzer.analyze(script_path)

            for injection in script_info.injections:
                injection_map[injection.target].append({
                    "mod": script_path.name,
                    "type": injection.type,
                    "file": injection.source_file,
                })
        except Exception as e:
            print(f"Failed to analyze {script_path.name}: {e}")

    # Find conflicts (multiple mods injecting same target)
    conflicts = {
        target: mods
        for target, mods in injection_map.items()
        if len(mods) > 1
    }

    return conflicts

# Usage
scripts = list(Path("./mods").glob("*.ts4script"))
conflicts = find_injection_conflicts(scripts)

if conflicts:
    print(f"Found {len(conflicts)} injection conflicts:")
    for target, mods in conflicts.items():
        print(f"\n  Target: {target}")
        for mod in mods:
            print(f"    - {mod['mod']} ({mod['type']})")
else:
    print("No injection conflicts detected")
```

### Example 5: Dependency Analysis

```python
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

def analyze_dependencies(script_path: Path) -> dict:
    """Analyze script dependencies."""
    analyzer = ScriptAnalyzer()
    script_info = analyzer.analyze(script_path)

    # Categorize imports
    sims4_imports = []
    standard_lib = []
    third_party = []

    for imp in script_info.imports:
        if imp.module.startswith("sims4"):
            sims4_imports.append(imp.module)
        elif imp.module in ["os", "sys", "re", "json", "collections"]:
            standard_lib.append(imp.module)
        else:
            third_party.append(imp.module)

    return {
        "name": script_info.name,
        "sims4_dependencies": sorted(set(sims4_imports)),
        "standard_lib": sorted(set(standard_lib)),
        "third_party": sorted(set(third_party)),
    }

# Usage
deps = analyze_dependencies(Path("mod.ts4script"))

print(f"Script: {deps['name']}")
print(f"\nSims 4 dependencies:")
for dep in deps['sims4_dependencies']:
    print(f"  - {dep}")

if deps['third_party']:
    print(f"\n⚠️  Third-party dependencies detected:")
    for dep in deps['third_party']:
        print(f"  - {dep}")
```

## Detection Patterns

### Injection Patterns

The analyzer detects common injection patterns:

**1. Wrap Injection:**
```python
@sims4.commands.Command('my_command')
def wrapped_function(original, *args, **kwargs):
    # Before
    result = original(*args, **kwargs)
    # After
    return result
```

**2. Replace Injection:**
```python
original_func = module.func
module.func = my_replacement_func
```

**3. Decorator Injection:**
```python
@inject_to(TargetClass, 'method_name')
def injected_method(self, *args, **kwargs):
    pass
```

### Import Patterns

**Standard imports:**
```python
import sims4.commands
from sims4.commands import Command
from sims4 import commands as cmd
```

**Star imports:**
```python
from sims4.commands import *
```

**Relative imports:**
```python
from . import utils
from ..parent import helper
```

## Error Handling

```python
from simanalysis.parsers.script import ScriptAnalyzer
from simanalysis.exceptions import AnalysisError

try:
    analyzer = ScriptAnalyzer()
    script_info = analyzer.analyze(Path("mod.ts4script"))
except AnalysisError as e:
    print(f"Analysis error: {e}")
except FileNotFoundError:
    print("Script file not found")
except Exception as e:
    print(f"Unexpected error: {e}")
```

**Common errors:**

- **Invalid ZIP**: File is not a valid ZIP archive
- **No Python files**: Archive contains no .py files
- **Syntax errors**: Python code has syntax errors
- **Encoding issues**: Non-UTF-8 encoding in Python files

## Performance

Script analysis performance characteristics:

- **Throughput**: 50-100 scripts per second
- **Memory**: ~1MB per script during analysis
- **I/O bound**: ZIP extraction is the bottleneck
- **Caching**: No caching by default

## Advanced Usage

### Custom AST Analysis

```python
import ast
from pathlib import Path
from zipfile import ZipFile

def custom_ast_analysis(script_path: Path) -> dict:
    """Perform custom AST analysis."""
    results = {
        "functions": [],
        "classes": [],
        "global_vars": [],
    }

    with ZipFile(script_path) as zf:
        for name in zf.namelist():
            if name.endswith(".py"):
                code = zf.read(name).decode("utf-8")
                try:
                    tree = ast.parse(code)

                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            results["functions"].append(node.name)
                        elif isinstance(node, ast.ClassDef):
                            results["classes"].append(node.name)
                        elif isinstance(node, ast.Assign):
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    results["global_vars"].append(target.id)
                except SyntaxError:
                    pass  # Skip files with syntax errors

    return results
```

### Extract Specific Files

```python
from pathlib import Path
from zipfile import ZipFile

def extract_init_file(script_path: Path) -> str:
    """Extract __init__.py content."""
    with ZipFile(script_path) as zf:
        for name in zf.namelist():
            if name.endswith("__init__.py"):
                return zf.read(name).decode("utf-8")
    return None

# Usage
init_content = extract_init_file(Path("mod.ts4script"))
if init_content:
    print("__init__.py content:")
    print(init_content)
```

### Parallel Analysis

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from simanalysis.parsers.script import ScriptAnalyzer

def analyze_scripts_parallel(script_paths: list[Path]) -> list:
    """Analyze multiple scripts in parallel."""
    analyzer = ScriptAnalyzer()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(analyzer.analyze, path): path
            for path in script_paths
        }

        results = []
        for future in futures:
            try:
                result = future.result(timeout=30)
                results.append(result)
            except Exception as e:
                print(f"Failed: {e}")

    return results

# Usage
scripts = list(Path("./mods").glob("*.ts4script"))
results = analyze_scripts_parallel(scripts)
print(f"Analyzed {len(results)} scripts")
```

## Security Considerations

### Safe Analysis

Script analysis is read-only and does not execute code:

```python
# Safe - only reads and parses
analyzer = ScriptAnalyzer()
script_info = analyzer.analyze(Path("untrusted.ts4script"))
```

**What's analyzed:**
- ✅ File structure (ZIP contents)
- ✅ Python syntax (AST parsing)
- ✅ Import statements
- ✅ Function definitions

**What's NOT executed:**
- ❌ Python code
- ❌ Imports
- ❌ Side effects

### Sandboxing

For extra safety, run analysis in Docker:

```bash
docker run -v ./mods:/mods:ro simanalysis:latest \
    analyze /mods --extensions .ts4script
```

## Limitations

### Detection Limitations

- **Dynamic injections**: Runtime injections not detectable via static analysis
- **Obfuscated code**: Heavily obfuscated code may not parse correctly
- **Complex patterns**: Custom injection frameworks may not be detected

### Performance Limitations

- Large scripts (100MB+) may be slow to analyze
- Many files in archive increases processing time

## See Also

- [DBPF Parser](dbpf.md) - Parse package files
- [Tuning Parser](tuning.md) - Parse XML tuning
- [Models](../models.md) - ScriptInfo data structure
- [Advanced Examples](../../examples/advanced.md) - Complex script analysis

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
