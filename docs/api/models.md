# Data Models

Core data structures used throughout Simanalysis.

## Overview

Simanalysis uses well-defined data models for representing mods, conflicts, and analysis results. These models provide type safety and clear interfaces.

## Core Models

### Mod

Represents a single mod file (.package or .ts4script).

```python
from pathlib import Path
from simanalysis.models import Mod

mod = Mod(
    name="AwesomeMod.package",
    path=Path("./mods/AwesomeMod.package"),
    size=1048576,
    mod_type="package",
    resources=[...],  # List of DBPFResource objects
    tunings=[...],    # List of TuningInfo objects
)

print(f"Name: {mod.name}")
print(f"Size: {mod.size} bytes")
print(f"Type: {mod.mod_type}")
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | str | Mod file name |
| `path` | Path | Full path to mod file |
| `size` | int | File size in bytes |
| `mod_type` | str | "package" or "script" |
| `resources` | List[DBPFResource] | DBPF resources (packages only) |
| `tunings` | List[TuningInfo] | Tuning metadata (packages only) |
| `hash` | str \| None | File hash (optional) |

### ModConflict

Represents a detected conflict between mods.

```python
from pathlib import Path
from simanalysis.models import ModConflict

conflict = ModConflict(
    type="tuning",
    severity="HIGH",
    description="Multiple mods modify instance 0x12345678",
    affected_mods=[
        Path("./mods/ModA.package"),
        Path("./mods/ModB.package"),
    ],
    instance_id="0x12345678",
    recommendation="Keep only one mod or use compatibility patch",
)
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | str | Conflict type ("tuning", "resource", "script") |
| `severity` | str | "CRITICAL", "HIGH", "MEDIUM", or "LOW" |
| `description` | str | Human-readable description |
| `affected_mods` | List[Path] | Paths to conflicting mods |
| `instance_id` | str \| None | Tuning instance ID (tuning conflicts) |
| `resource_hash` | str \| None | Resource hash (resource conflicts) |
| `recommendation` | str \| None | Resolution suggestion |

### DBPFHeader

DBPF package file header information.

```python
from simanalysis.models import DBPFHeader

header = DBPFHeader(
    magic=b"DBPF",
    major_version=2,
    minor_version=1,
    index_count=45,
    index_offset=96,
    index_size=1440,
)

print(f"Version: {header.major_version}.{header.minor_version}")
print(f"Resources: {header.index_count}")
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `magic` | bytes | Magic bytes (should be b"DBPF") |
| `major_version` | int | Major version (typically 2) |
| `minor_version` | int | Minor version (typically 1) |
| `index_count` | int | Number of resources |
| `index_offset` | int | Offset to index table |
| `index_size` | int | Size of index table |

### DBPFResource

Single DBPF resource entry.

```python
from simanalysis.models import DBPFResource

resource = DBPFResource(
    type=0x545503B2,  # XML tuning
    group=0,
    instance=0x12345678,
    offset=2048,
    size=4096,
    compressed_size=0,  # 0 = not compressed
)

print(f"Type: 0x{resource.type:08X}")
print(f"Instance: 0x{resource.instance:08X}")
print(f"Compressed: {resource.is_compressed}")
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | int | Resource type ID |
| `group` | int | Resource group ID |
| `instance` | int | Resource instance ID |
| `offset` | int | Offset to resource data |
| `size` | int | Uncompressed size |
| `compressed_size` | int | Compressed size (0 if not compressed) |
| `is_compressed` | bool | Whether resource is compressed |

### TuningInfo

Tuning metadata extracted from XML.

```python
from simanalysis.models import TuningInfo

tuning = TuningInfo(
    instance_id="0x12345678",
    module="traits.trait_Confident",
    class_name="Trait",
    name="trait_Confident",
    pack_requirement="EP01",
)

print(f"Instance: {tuning.instance_id}")
print(f"Module: {tuning.module}")
print(f"Requires: {tuning.pack_requirement}")
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `instance_id` | str | Tuning instance ID (hex string) |
| `module` | str | Python module path |
| `class_name` | str | Tuning class name |
| `name` | str | Tuning name |
| `pack_requirement` | str \| None | Required pack code |
| `attributes` | dict | Additional XML attributes |

### ScriptInfo

Script mod metadata.

```python
from pathlib import Path
from simanalysis.models import ScriptInfo, ImportInfo

script_info = ScriptInfo(
    name="awesome_mod.ts4script",
    path=Path("./mods/awesome_mod.ts4script"),
    size=524288,
    python_files=["main.py", "utils.py"],
    imports=[
        ImportInfo(
            module="sims4.commands",
            names=["Command"],
            alias=None,
            source_file="main.py",
        )
    ],
    has_init=True,
)

print(f"Name: {script_info.name}")
print(f"Python files: {len(script_info.python_files)}")
print(f"Imports: {len(script_info.imports)}")
```

**Attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `name` | str | Script mod name |
| `path` | Path | Path to .ts4script file |
| `size` | int | File size in bytes |
| `python_files` | List[str] | List of .py files |
| `imports` | List[ImportInfo] | Imported modules |
| `injections` | List[InjectionInfo] | Detected injections |
| `has_init` | bool | Whether __init__.py exists |

## Usage Examples

### Example 1: Create Mod Instance

```python
from pathlib import Path
from simanalysis.models import Mod

def create_mod_from_file(file_path: Path) -> Mod:
    """Create Mod instance from file."""
    return Mod(
        name=file_path.name,
        path=file_path,
        size=file_path.stat().st_size,
        mod_type="package" if file_path.suffix == ".package" else "script",
    )

mod = create_mod_from_file(Path("./mods/MyMod.package"))
```

### Example 2: Filter Mods

```python
from typing import List
from simanalysis.models import Mod

def filter_large_mods(mods: List[Mod], size_mb: float = 10.0) -> List[Mod]:
    """Filter mods larger than specified size."""
    size_bytes = size_mb * 1024 * 1024
    return [mod for mod in mods if mod.size > size_bytes]

large_mods = filter_large_mods(all_mods, size_mb=5.0)
```

### Example 3: Process Conflicts

```python
from typing import List
from simanalysis.models import ModConflict

def group_by_severity(conflicts: List[ModConflict]) -> dict:
    """Group conflicts by severity."""
    groups = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}

    for conflict in conflicts:
        if conflict.severity in groups:
            groups[conflict.severity].append(conflict)

    return groups

grouped = group_by_severity(all_conflicts)
print(f"Critical: {len(grouped['CRITICAL'])}")
print(f"High: {len(grouped['HIGH'])}")
```

## Type Hints

All models support type hints for better IDE support:

```python
from typing import List, Optional
from pathlib import Path
from simanalysis.models import Mod, ModConflict

def analyze_mods(mods: List[Mod]) -> List[ModConflict]:
    """Analyze mods and return conflicts."""
    conflicts: List[ModConflict] = []
    # Analysis logic
    return conflicts

def find_mod_by_name(mods: List[Mod], name: str) -> Optional[Mod]:
    """Find mod by name."""
    for mod in mods:
        if mod.name == name:
            return mod
    return None
```

## Serialization

Models can be serialized to JSON:

```python
import json
from dataclasses import asdict
from simanalysis.models import Mod

# Convert to dict
mod_dict = {
    "name": mod.name,
    "path": str(mod.path),
    "size": mod.size,
    "type": mod.mod_type,
}

# Save to JSON
with open("mod.json", "w") as f:
    json.dump(mod_dict, f, indent=2)
```

## See Also

- [Mod Analyzer](analyzers/mod_analyzer.md) - Uses these models
- [Parsers](parsers/dbpf.md) - Create these models
- [Exceptions](exceptions.md) - Error handling

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
