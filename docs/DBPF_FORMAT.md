# DBPF Format Specification for The Sims 4

**Author:** Simanalysis Project
**Date:** 2025-10-24
**Format Version:** DBPF 2.1 (The Sims 4)
**References:** [SimsWiki DBPF](https://simswiki.info/DatabasePackedFile)

---

## Table of Contents

1. [Overview](#overview)
2. [File Structure](#file-structure)
3. [Header Format](#header-format)
4. [Index Table](#index-table)
5. [Resource Data](#resource-data)
6. [Compression](#compression)
7. [Resource Types](#resource-types)
8. [Examples](#examples)

---

## Overview

DBPF (Database Packed File) is Electronic Arts' proprietary archive format used across The Sims franchise. The Sims 4 uses **DBPF 2.1**, which stores game resources such as:

- XML tuning files (gameplay parameters)
- SimData (binary object definitions)
- String tables (localized text)
- Images and textures
- 3D meshes and animations
- Python script mods

### Key Characteristics

- **Binary format**: All multi-byte values are little-endian
- **Fixed header**: 96 bytes at offset 0
- **Indexed access**: Central index table for fast resource lookup
- **Compressed resources**: Optional zlib compression per resource
- **Type-Group-Instance**: Unique 3-part key system (TGI)

---

## File Structure

```
┌─────────────────────────────────────┐
│  DBPF Header (96 bytes)             │  Offset: 0x00
│  - Magic: "DBPF"                    │
│  - Version: 2.1                     │
│  - Index offset/size                │
├─────────────────────────────────────┤
│  Resource Data (variable size)      │  Offset: 96+
│  - Resource 1 (compressed/raw)      │
│  - Resource 2 (compressed/raw)      │
│  - ...                              │
│  - Resource N (compressed/raw)      │
├─────────────────────────────────────┤
│  Index Table (variable size)        │  Offset: header.index_offset
│  - Index Entry 1 (32 bytes)         │
│  - Index Entry 2 (32 bytes)         │
│  - ...                              │
│  - Index Entry N (32 bytes)         │
└─────────────────────────────────────┘
```

**Note:** The index table is typically at the **end** of the file for efficient appending of resources.

---

## Header Format

The DBPF header is exactly **96 bytes** and appears at the start of every .package file.

### Field Layout

| Offset | Size | Type   | Field Name       | Description | Required Value |
|--------|------|--------|------------------|-------------|----------------|
| 0x00   | 4    | char[4]| magic            | File signature | "DBPF" |
| 0x04   | 4    | uint32 | major_version    | Major version | 2 |
| 0x08   | 4    | uint32 | minor_version    | Minor version | 0 or 1 |
| 0x0C   | 4    | uint32 | user_version     | User version | 0 |
| 0x10   | 4    | uint32 | flags            | File flags | Varies |
| 0x14   | 4    | uint32 | created_date     | Creation timestamp | Unix time |
| 0x18   | 4    | uint32 | modified_date    | Modification timestamp | Unix time |
| 0x1C   | 4    | uint32 | index_version    | Index format version | 0 |
| 0x20   | 4    | uint32 | reserved_1       | Reserved | 0 |
| 0x24   | 4    | uint32 | reserved_2       | Reserved | 0 |
| 0x28   | 4    | uint32 | index_count      | Number of index entries | > 0 |
| 0x2C   | 4    | uint32 | index_offset     | Byte offset to index | >= 96 |
| 0x30   | 4    | uint32 | index_size       | Size of index in bytes | count × 32 |
| 0x34   | 4    | uint32 | hole_count       | Number of holes | Usually 0 |
| 0x38   | 4    | uint32 | hole_offset      | Offset to hole table | 0 if no holes |
| 0x3C   | 4    | uint32 | hole_size        | Size of hole table | 0 if no holes |
| 0x40   | 32   | uint32[8] | reserved_3    | Reserved | All zeros |

### Binary Representation

```
Offset(h) 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F

00000000  44 42 50 46 02 00 00 00 01 00 00 00 00 00 00 00  DBPF............
00000010  00 00 00 00 F4 65 8A 65 F4 65 8A 65 00 00 00 00  .....e.e.e.e....
00000020  00 00 00 00 00 00 00 00 05 00 00 00 A0 12 00 00  ................
00000030  A0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
00000040  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
00000050  00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00  ................
```

### Validation Rules

1. **Magic must be "DBPF"** (bytes 0-3)
2. **Major version must be 2** (The Sims 4)
3. **Index offset >= 96** (must be after header)
4. **Index size == index_count × 32**
5. **File size >= index_offset + index_size**

---

## Index Table

The index table is a directory of all resources in the package. Each entry is **32 bytes**.

### Index Entry Format

| Offset | Size | Type   | Field Name          | Description |
|--------|------|--------|---------------------|-------------|
| 0x00   | 4    | uint32 | type_id             | Resource type identifier |
| 0x04   | 4    | uint32 | group_id            | Resource group identifier |
| 0x08   | 8    | uint64 | instance_id         | Resource instance identifier |
| 0x10   | 4    | uint32 | offset              | Byte offset to resource data |
| 0x14   | 4    | uint32 | size                | Uncompressed resource size |
| 0x18   | 4    | uint32 | compressed_size     | Compressed size (0 = uncompressed) |
| 0x1C   | 4    | uint32 | flags               | Resource flags |

### TGI Key System

Resources are uniquely identified by their **TGI** (Type-Group-Instance) triple:

```python
# Example TGI key
type_id     = 0x545503B2  # XML Tuning
group_id    = 0x00000000  # Default group
instance_id = 0x1234567890ABCDEF  # Unique instance

# Combined key (for lookups)
tgi_key = (type_id, group_id, instance_id)
```

### Compression Flag

```python
# Check if resource is compressed
is_compressed = (compressed_size > 0 and compressed_size < size)

# If compressed:
#   - Read 'compressed_size' bytes from 'offset'
#   - Decompress to 'size' bytes
# If uncompressed:
#   - Read 'size' bytes from 'offset'
```

---

## Resource Data

Resource data follows the header and precedes the index table.

### Layout

```
┌──────────────────────┐
│  Resource 1 Data     │  Offset: entry[0].offset
│  (compressed or raw) │  Size: entry[0].compressed_size or entry[0].size
├──────────────────────┤
│  Resource 2 Data     │  Offset: entry[1].offset
│  ...                 │
└──────────────────────┘
```

### Reading Algorithm

```python
def read_resource(package_file, index_entry):
    # Seek to resource offset
    package_file.seek(index_entry.offset)

    # Determine read size
    if index_entry.compressed_size > 0:
        data = package_file.read(index_entry.compressed_size)
        data = decompress(data)  # zlib or RefPack
        assert len(data) == index_entry.size
    else:
        data = package_file.read(index_entry.size)

    return data
```

---

## Compression

The Sims 4 packages use multiple compression formats:

### 1. ZLib Compression (Most Common)

```python
import zlib

# Compress
compressed = zlib.compress(data, level=6)

# Decompress
decompressed = zlib.decompress(compressed)
```

**Detection:** Try `zlib.decompress()` first; if it succeeds, it's ZLib.

### 2. RefPack Compression (Legacy)

RefPack is EA's proprietary LZ77-based compression.

**Header Signature:** `0x10FB` (big-endian, first 2 bytes)

**Detection:**
```python
signature = struct.unpack(">H", data[0:2])[0]
if signature == 0x10FB:
    # RefPack compression
    decompressed = decompress_refpack(data)
```

**Status in Simanalysis:** ❌ Not yet implemented (rare in TS4)

### 3. Internal Compression (DeleteRecord)

Used for special resource types that store deletion markers.

**Status in Simanalysis:** ❌ Not yet implemented

---

## Resource Types

Common resource type IDs used in The Sims 4:

| Type ID      | Name            | Description | Parser Status |
|--------------|-----------------|-------------|---------------|
| `0x545503B2` | XML Tuning      | Gameplay tuning files (XML) | ✅ `tuning.py` |
| `0x0333406C` | SimData         | Binary object definitions | ❌ Raw bytes |
| `0x220557DA` | STBL            | String tables (localized text) | ❌ Raw bytes |
| `0x025ED6F4` | OBJD            | Object definitions | ❌ Raw bytes |
| `0x00B2D882` | _IMG            | Images (PNG, DDS) | ❌ Raw bytes |
| `0x034AEECB` | Catalog         | Catalog resources | ❌ Raw bytes |
| `0x515CA4CD` | Relationship Bit| Relationship tuning | ✅ Via XML |
| `0x3453CF95` | Buff            | Buff tuning | ✅ Via XML |
| `0xE882D22F` | Trait           | Trait tuning | ✅ Via XML |

### Type ID Naming Convention

Type IDs are often derived from FNV-32 hash of type name:

```python
# Example: "Trait" → 0xE882D22F
import hashlib

def fnv32(text: str) -> int:
    """Calculate FNV-1 32-bit hash."""
    hash = 0x811c9dc5  # FNV offset basis
    for byte in text.encode('utf-8').lower():
        hash = ((hash ^ byte) * 0x01000193) & 0xFFFFFFFF
    return hash

type_id = fnv32("Trait")  # 0xE882D22F
```

---

## Examples

### Example 1: Reading a Package Header

```python
import struct
from pathlib import Path

def read_dbpf_header(package_path: Path):
    with open(package_path, 'rb') as f:
        header = f.read(96)

    magic = header[0:4]
    major_version = struct.unpack('<I', header[4:8])[0]
    minor_version = struct.unpack('<I', header[8:12])[0]
    index_count = struct.unpack('<I', header[40:44])[0]
    index_offset = struct.unpack('<I', header[44:48])[0]
    index_size = struct.unpack('<I', header[48:52])[0]

    print(f"Magic: {magic}")
    print(f"Version: {major_version}.{minor_version}")
    print(f"Resources: {index_count}")
    print(f"Index at: 0x{index_offset:08X}")
```

### Example 2: Listing All Resources

```python
from simanalysis.parsers.dbpf import DBPFReader

reader = DBPFReader("my_mod.package")
resources = reader.read_index()

for i, res in enumerate(resources):
    print(f"Resource {i}:")
    print(f"  Type:     0x{res.type:08X}")
    print(f"  Group:    0x{res.group:08X}")
    print(f"  Instance: 0x{res.instance:016X}")
    print(f"  Size:     {res.size} bytes")
    print(f"  Compressed: {res.is_compressed}")
    print()
```

### Example 3: Extracting XML Tuning Files

```python
from simanalysis.parsers.dbpf import DBPFReader

reader = DBPFReader("my_mod.package")

# Get all XML tuning resources
XML_TUNING_TYPE = 0x545503B2
xml_resources = reader.get_resources_by_type(XML_TUNING_TYPE)

for res in xml_resources:
    # Extract resource data
    data = reader.get_resource(res)

    # Parse XML
    xml_string = data.decode('utf-8')
    print(f"XML Instance 0x{res.instance:016X}:")
    print(xml_string[:200])  # First 200 chars
    print()
```

### Example 4: Performance Benchmark

```python
import time
from simanalysis.parsers.dbpf import DBPFReader

package_path = "large_mod.package"

# Benchmark header parsing
start = time.perf_counter()
reader = DBPFReader(package_path)
header = reader.read_header()
header_time = time.perf_counter() - start

# Benchmark index parsing
start = time.perf_counter()
resources = reader.read_index()
index_time = time.perf_counter() - start

print(f"Header parse: {header_time*1000:.2f}ms")
print(f"Index parse:  {index_time*1000:.2f}ms ({len(resources)} resources)")
print(f"Total:        {(header_time + index_time)*1000:.2f}ms")
```

---

## Implementation Notes

### Performance Considerations

1. **Lazy Loading**: Don't read resources until needed
2. **Index Caching**: Parse index once, cache in memory
3. **Streaming**: For large files, use file seeks instead of reading entire file
4. **Decompression**: Only decompress when resource data is accessed

### Error Handling

1. **Validate header magic** before parsing
2. **Check version compatibility** (major version == 2)
3. **Verify index bounds** (offset + size <= file size)
4. **Handle corrupted compression** (zlib errors, size mismatches)
5. **Skip unknown resource types** gracefully

### Security Considerations

1. **Limit decompression size** to prevent zip bombs
2. **Validate all offsets** to prevent out-of-bounds reads
3. **Sanitize file paths** when extracting
4. **Check for integer overflow** in size calculations

---

## References

- [SimsWiki: DBPF](https://simswiki.info/DatabasePackedFile)
- [SimsWiki: RefPack](https://wiki.niotso.org/RefPack)
- [Sims 4 Modding Documentation](https://modthesims.info)
- [s4pi Library](https://sourceforge.net/projects/sims4tools/)

---

## Changelog

**2025-10-24:** Initial documentation for Simanalysis project
**2025-10-24:** Added TGI key system explanation
**2025-10-24:** Added compression format details
**2025-10-24:** Added resource type table

---

*This documentation is part of the Simanalysis project.*
*Licensed under MIT License.*
