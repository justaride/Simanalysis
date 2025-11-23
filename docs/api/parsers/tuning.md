# Tuning Parser

Parse XML tuning resources from The Sims 4 package files.

## Overview

The Tuning Parser extracts metadata from XML tuning files, including instance IDs, modules, classes, and pack requirements.

## Quick Example

```python
from simanalysis.parsers.tuning import TuningParser

# Parse tuning XML
parser = TuningParser()
xml_data = b"""<?xml version="1.0"?>
<I c="Trait" i="trait" m="traits.trait_Confident" n="trait_Confident" s="12345678">
    <T n="display_name">0x12AB34CD<!--Confident--></T>
</I>
"""

tuning = parser.parse(xml_data)

print(f"Instance ID: {tuning.instance_id}")
print(f"Module: {tuning.module}")
print(f"Class: {tuning.class_name}")
```

## API Reference

::: simanalysis.parsers.tuning
    options:
      show_root_heading: true
      show_source: true
      members:
        - TuningInfo
        - TuningParser
      group_by_category: true

## TuningInfo Structure

The parser returns a `TuningInfo` object with these attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `instance_id` | str | Tuning instance ID (hex string) |
| `module` | str | Python module path |
| `class_name` | str | Tuning class name |
| `name` | str | Tuning name attribute |
| `pack_requirement` | str \| None | Required pack (if any) |
| `attributes` | dict | Additional XML attributes |

## XML Format Details

### Root Element

```xml
<I c="ClassName" i="identifier" m="module.path" n="name" s="instance_id">
    <!-- Tuning content -->
</I>
```

**Attributes:**
- `c`: Class name (e.g., "Trait", "Buff", "Interaction")
- `i`: Identifier (generic name)
- `m`: Module path (e.g., "traits.trait_Confident")
- `n`: Specific name
- `s`: Instance ID (hex, without 0x prefix)

### Common Tuning Types

| Class | Description | Example Module |
|-------|-------------|----------------|
| Trait | Character traits | traits.trait_Confident |
| Buff | Temporary modifiers | buffs.buff_Energized |
| Interaction | Sim interactions | interactions.social.romance.Kiss |
| Object | Object tuning | objects.game_objects.Chair |
| Aspiration | Life goals | aspirations.aspiration_Bodybuilder |

### Pack Requirements

Some tunings require specific packs:

```xml
<T n="pack_requirement">EP01</T>
```

**Pack codes:**
- `EP01` - Get to Work
- `EP02` - Get Together
- `EP03` - City Living
- `GP01` - Outdoor Retreat
- `SP01` - Luxury Party Stuff

## Usage Examples

### Example 1: Parse from DBPF Resource

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.tuning import TuningParser

# Read package
reader = DBPFReader(Path("mod.package"))
resources = reader.read_index()

parser = TuningParser()

# Find and parse tuning resources
XML_TUNING_TYPE = 0x545503B2

for resource in resources:
    if resource.type == XML_TUNING_TYPE:
        data = reader.get_resource(resource)
        try:
            tuning = parser.parse(data)
            print(f"Found tuning: {tuning.name} (ID: {tuning.instance_id})")
        except Exception as e:
            print(f"Failed to parse: {e}")
```

### Example 2: Extract All Tunings

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.tuning import TuningParser

def extract_tunings(package_path: Path) -> list:
    """Extract all tunings from a package."""
    reader = DBPFReader(package_path)
    resources = reader.read_index()

    parser = TuningParser()
    tunings = []

    for resource in resources:
        if resource.type == 0x545503B2:  # XML tuning
            try:
                data = reader.get_resource(resource)
                tuning = parser.parse(data)
                tunings.append(tuning)
            except Exception:
                pass  # Skip invalid tunings

    return tunings

# Usage
tunings = extract_tunings(Path("mod.package"))
print(f"Extracted {len(tunings)} tunings")
```

### Example 3: Filter by Class

```python
from simanalysis.parsers.tuning import TuningParser

# Parse multiple tunings
parser = TuningParser()
tunings = [parser.parse(data) for data in tuning_data_list]

# Filter traits only
traits = [t for t in tunings if t.class_name == "Trait"]

# Filter buffs only
buffs = [t for t in tunings if t.class_name == "Buff"]

print(f"Traits: {len(traits)}")
print(f"Buffs: {len(buffs)}")
```

### Example 4: Check Pack Requirements

```python
from simanalysis.parsers.tuning import TuningParser

parser = TuningParser()
tunings = [parser.parse(data) for data in tuning_data_list]

# Find base game tunings (no pack required)
base_game = [t for t in tunings if not t.pack_requirement]

# Find expansion pack tunings
expansion_tunings = [t for t in tunings if t.pack_requirement]

print(f"Base game: {len(base_game)}")
print(f"Requires packs: {len(expansion_tunings)}")

# Count by pack
from collections import Counter
pack_counts = Counter(t.pack_requirement for t in expansion_tunings)
for pack, count in pack_counts.most_common():
    print(f"  {pack}: {count} tunings")
```

### Example 5: Detect Conflicts

```python
from collections import defaultdict
from simanalysis.parsers.tuning import TuningParser

def find_tuning_conflicts(packages: list[Path]) -> dict:
    """Find tuning conflicts across multiple packages."""
    parser = TuningParser()
    instance_map = defaultdict(list)

    # Parse all tunings
    for package in packages:
        reader = DBPFReader(package)
        resources = reader.read_index()

        for resource in resources:
            if resource.type == 0x545503B2:
                try:
                    data = reader.get_resource(resource)
                    tuning = parser.parse(data)

                    # Track which packages define this instance
                    instance_map[tuning.instance_id].append(package.name)
                except Exception:
                    pass

    # Find conflicts (same instance in multiple packages)
    conflicts = {
        instance_id: packages
        for instance_id, packages in instance_map.items()
        if len(packages) > 1
    }

    return conflicts

# Usage
packages = list(Path("./mods").glob("*.package"))
conflicts = find_tuning_conflicts(packages)

print(f"Found {len(conflicts)} tuning conflicts")
for instance_id, pkgs in conflicts.items():
    print(f"  Instance {instance_id}: {', '.join(pkgs)}")
```

## Error Handling

The parser includes comprehensive error handling:

```python
from simanalysis.parsers.tuning import TuningParser
from simanalysis.exceptions import TuningError

try:
    parser = TuningParser()
    tuning = parser.parse(xml_data)
except TuningError as e:
    print(f"Tuning parsing error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

**Common errors:**

- **Invalid XML**: Malformed XML structure
- **Missing attributes**: Required attributes not present
- **Empty data**: No XML content
- **Encoding issues**: Non-UTF-8 characters

## Performance

The tuning parser is optimized for speed:

- **Throughput**: 1000+ tunings per second
- **Memory**: ~500 bytes per parsed tuning
- **Parsing**: Uses fast XML parser (lxml/etree)

## Advanced Usage

### Custom Attribute Extraction

```python
from simanalysis.parsers.tuning import TuningParser
import xml.etree.ElementTree as ET

def parse_with_custom_attrs(xml_data: bytes) -> dict:
    """Parse tuning with custom attribute extraction."""
    parser = TuningParser()
    tuning = parser.parse(xml_data)

    # Parse XML again for custom attributes
    root = ET.fromstring(xml_data)

    # Extract display name
    display_name_elem = root.find(".//T[@n='display_name']")
    if display_name_elem is not None:
        display_name = display_name_elem.text
    else:
        display_name = None

    return {
        "instance_id": tuning.instance_id,
        "name": tuning.name,
        "display_name": display_name,
        "module": tuning.module,
        "class": tuning.class_name,
    }
```

### Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor
from simanalysis.parsers.tuning import TuningParser

def batch_parse_tunings(xml_data_list: list[bytes]) -> list:
    """Parse multiple tunings in parallel."""
    parser = TuningParser()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(parser.parse, data)
            for data in xml_data_list
        ]

        results = []
        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception:
                pass  # Skip failures

    return results
```

## Namespace Handling

The parser handles XML namespaces correctly:

```python
# With namespace
xml_with_ns = b"""<?xml version="1.0"?>
<I xmlns="http://www.w3.org/2001/XMLSchema-instance"
   c="Trait" i="trait" m="traits.trait_Confident" n="trait_Confident" s="12345678">
    <T n="display_name">Confident</T>
</I>
"""

parser = TuningParser()
tuning = parser.parse(xml_with_ns)  # Works correctly
```

## See Also

- [DBPF Parser](dbpf.md) - Parse package files
- [Script Parser](script.md) - Analyze script mods
- [Tuning Conflicts](../detectors/tuning_conflicts.md) - Detect tuning conflicts
- [Models](../models.md) - TuningInfo data structure

---

**Version**: 3.0.0 | **Last Updated**: 2025-11-23
