# DBPF Parser

The DBPF parser provides low-level access to The Sims 4 package file format.

## Overview

The DBPF (Database Packed File) format is a binary container format used by The Sims 4 to store mod data. This parser provides full support for reading and extracting resources from .package files.

## Quick Example

```python
from pathlib import Path
from simanalysis.parsers.dbpf import DBPFReader

# Open a package file
reader = DBPFReader(Path("my_mod.package"))

# Read header
header = reader.read_header()
print(f"DBPF version: {header.major_version}.{header.minor_version}")
print(f"Resources: {header.index_count}")

# Read resource index
resources = reader.read_index()

# Extract first resource
if resources:
    data = reader.get_resource(resources[0])
    print(f"Extracted {len(data)} bytes")
```

## API Reference

::: simanalysis.parsers.dbpf
    options:
      show_root_heading: true
      show_source: true
      members:
        - DBPFHeader
        - DBPFResource
        - DBPFReader
      group_by_category: true

## Binary Format Details

### DBPF Header (96 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00 | 4 | magic | Magic bytes ("DBPF") |
| 0x04 | 4 | major_version | Major version (typically 2) |
| 0x08 | 4 | minor_version | Minor version (typically 1) |
| 0x28 | 4 | index_count | Number of resources |
| 0x2C | 4 | index_offset | Offset to index table |
| 0x30 | 4 | index_size | Size of index table |

### Index Entry (32 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00 | 4 | type | Resource type ID |
| 0x04 | 4 | group | Resource group ID |
| 0x08 | 8 | instance | Resource instance ID |
| 0x10 | 4 | offset | Offset to resource data |
| 0x14 | 4 | size | Uncompressed size |
| 0x18 | 4 | compressed_size | Compressed size (0 if not compressed) |
| 0x1C | 4 | flags | Resource flags |

## Common Resource Types

| Type ID | Description |
|---------|-------------|
| 0x545238C9 | SIMDATA (binary tuning) |
| 0x545503B2 | XML Tuning |
| 0x2D5DF13 | DDS Image |
| 0x015A1849 | Geometry |

## Performance

The DBPF parser is highly optimized:

- **Throughput**: 690+ MB/s
- **Index parsing**: <1ms for 1000 resources
- **Memory**: ~100 bytes per resource in index
- **Zero-copy**: Direct file mapping where possible

## Error Handling

The parser includes comprehensive error handling:

```python
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.exceptions import DBPFError

try:
    reader = DBPFReader(Path("mod.package"))
    header = reader.read_header()
except DBPFError as e:
    print(f"Invalid DBPF file: {e}")
```

Common errors:

- **Invalid DBPF magic**: File is not a package file
- **File too small**: Truncated or corrupted file
- **Index entry extends beyond file**: Corrupted index
- **Could not decompress resource**: ZLib decompression failed

## Advanced Usage

### Filtering Resources by Type

```python
# Get only XML tuning resources
XML_TUNING_TYPE = 0x545503B2

reader = DBPFReader(Path("mod.package"))
resources = reader.read_index()

xml_resources = [r for r in resources if r.type == XML_TUNING_TYPE]
print(f"Found {len(xml_resources)} XML tunings")
```

### Extracting All Resources

```python
reader = DBPFReader(Path("mod.package"))
resources = reader.read_index()

for i, resource in enumerate(resources):
    data = reader.get_resource(resource)
    output_file = Path(f"resource_{i:04d}.bin")
    output_file.write_bytes(data)
```

### Checking for Compression

```python
reader = DBPFReader(Path("mod.package"))
resources = reader.read_index()

for resource in resources:
    if resource.is_compressed:
        ratio = resource.size / resource.compressed_size
        print(f"Resource 0x{resource.instance:08X}: {ratio:.1f}x compression")
```

## See Also

- [Tuning Parser](tuning.md) - Parse XML tuning resources
- [Script Parser](script.md) - Analyze .ts4script files
- [DBPF Format Specification](../../development/architecture.md#dbpf-format)
