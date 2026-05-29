"""Script to create sample fixture mod files for testing.

This creates realistic .package files that can be used for integration testing
and as examples for users.
"""

import struct
import zlib
from pathlib import Path
from typing import Optional


def create_package_file(
    output_path: Path,
    tuning_id: int,
    resource_count: int = 1,
    name: str = "Test Resource",
) -> None:
    """
    Create a minimal but valid DBPF package file.

    Args:
        output_path: Where to save the package
        tuning_id: Instance ID for the tuning
        resource_count: Number of resources to include
        name: Name/description for the resource
    """
    # DBPF header (96 bytes). The parser reads index_count@36, index_size@44 and
    # index_offset@40 (falling back to @64). The index sits right after the
    # header; resource data follows the index.
    index_size = 4 + 32 * resource_count  # mnIndexType flags word + 32-byte v2 entries
    index_offset = 96
    data_offset = index_offset + index_size

    header = bytearray(96)
    header[0:4] = b"DBPF"  # Magic number
    header[4:8] = struct.pack("<I", 2)  # Major version
    header[8:12] = struct.pack("<I", 1)  # Minor version
    header[36:40] = struct.pack("<I", resource_count)  # Index entry count
    header[44:48] = struct.pack("<I", index_size)  # Index size
    header[64:68] = struct.pack("<I", index_offset)  # Index offset

    # Real Sims 4 DBPF v2 index: mnIndexType flags word (0 = no constant fields)
    # followed by full 32-byte entries:
    #   type(4) group(4) instanceHi(4) instanceLo(4) chunkOffset(4)
    #   fileSize(4) memSize(4) compressed(2) committed(2)
    index = bytearray()
    index += struct.pack("<I", 0)  # mnIndexType

    blobs = []
    current_offset = data_offset
    for i in range(resource_count):
        resource_data = f"{name} {i}".encode()
        compressed_data = zlib.compress(resource_data)
        instance = tuning_id + i
        index += struct.pack("<I", 0x545503B2)  # type (XML tuning)
        index += struct.pack("<I", 0x00000000)  # group
        index += struct.pack("<I", instance >> 32)  # instance high
        index += struct.pack("<I", instance & 0xFFFFFFFF)  # instance low
        index += struct.pack("<I", current_offset)  # chunk offset
        index += struct.pack("<I", len(compressed_data))  # file size (compressed, on disk)
        index += struct.pack("<I", len(resource_data))  # mem size (uncompressed)
        index += struct.pack("<H", 0x5A42)  # compressed: zlib
        index += struct.pack("<H", 1)  # committed
        blobs.append(compressed_data)
        current_offset += len(compressed_data)

    # Write file: header, then index, then resource data
    with open(output_path, "wb") as f:
        f.write(header)
        f.write(index)
        for compressed_data in blobs:
            f.write(compressed_data)

    print(f"Created: {output_path.name} (tuning ID: 0x{tuning_id:08X})")


def create_ts4script_file(output_path: Path, content: Optional[str] = None) -> None:
    """
    Create a simple .ts4script file (Python code).

    Args:
        output_path: Where to save the script
        content: Python code content
    """
    if content is None:
        content = '''"""Sample Sims 4 Script Mod"""

import sims4.commands

@sims4.commands.Command('test_command', command_type=sims4.commands.CommandType.Live)
def test_command(_connection=None):
    """Test command that does nothing."""
    sims4.commands.output('Test command executed!', _connection)
    return True
'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Created: {output_path.name}")


def main():
    """Create all sample fixture files."""
    fixtures_dir = Path(__file__).parent / "sample_mods"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    print("Creating sample fixture mods...\n")

    # 1. Simple mod - no conflicts
    create_package_file(
        fixtures_dir / "simple_mod.package",
        tuning_id=0x11111111,
        resource_count=1,
        name="Simple Buff",
    )

    # 2. Conflicting mod A
    create_package_file(
        fixtures_dir / "conflicting_mod_a.package",
        tuning_id=0xAAAAAAAA,
        resource_count=2,
        name="Overlapping Buff A",
    )

    # 3. Conflicting mod B (same tuning ID as A)
    create_package_file(
        fixtures_dir / "conflicting_mod_b.package",
        tuning_id=0xAAAAAAAA,  # Same as mod A!
        resource_count=2,
        name="Overlapping Buff B",
    )

    # 4. Large mod with many resources
    create_package_file(
        fixtures_dir / "large_mod.package",
        tuning_id=0x22222222,
        resource_count=10,
        name="Complex Mod Resource",
    )

    # 5. Script mod
    create_ts4script_file(fixtures_dir / "script_mod.ts4script")

    print(f"\n✅ Created {len(list(fixtures_dir.glob('*')))} fixture files in {fixtures_dir}")
    print("\nThese files can be used for:")
    print("  - Integration tests")
    print("  - User examples")
    print("  - Manual testing")
    print("  - Documentation screenshots")


if __name__ == "__main__":
    main()
