"""Script to create sample fixture mod files for testing.

This creates realistic .package files that can be used for integration testing
and as examples for users.
"""

import struct
import zlib
from pathlib import Path


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
    # DBPF Header (96 bytes)
    header = bytearray(96)
    header[0:4] = b"DBPF"  # Magic number
    header[4:8] = struct.pack("<I", 2)  # Major version
    header[8:12] = struct.pack("<I", 1)  # Minor version
    header[40:44] = struct.pack("<I", resource_count)  # Index entry count
    header[44:48] = struct.pack("<I", 96)  # Index offset
    header[48:52] = struct.pack("<I", 32 * resource_count)  # Index size

    # Create resources
    resources = []
    current_offset = 96 + (32 * resource_count)

    for i in range(resource_count):
        resource_data = f"{name} {i}".encode('utf-8')
        compressed_data = zlib.compress(resource_data)

        # Index entry (32 bytes each)
        index_entry = struct.pack(
            "<IIQIII",
            0x545503B2,  # Type ID (XML tuning)
            0x00000000,  # Group ID
            tuning_id + i,  # Instance ID
            current_offset,  # File offset
            len(compressed_data),  # Compressed size
            len(resource_data),  # Decompressed size
        )

        resources.append((index_entry, compressed_data))
        current_offset += len(compressed_data)

    # Write file
    with open(output_path, "wb") as f:
        # Write header
        f.write(header)

        # Write index entries
        for index_entry, _ in resources:
            f.write(index_entry)

        # Write resource data
        for _, compressed_data in resources:
            f.write(compressed_data)

    print(f"Created: {output_path.name} (tuning ID: 0x{tuning_id:08X})")


def create_ts4script_file(output_path: Path, content: str = None) -> None:
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
        name="Simple Buff"
    )

    # 2. Conflicting mod A
    create_package_file(
        fixtures_dir / "conflicting_mod_a.package",
        tuning_id=0xAAAAAAAA,
        resource_count=2,
        name="Overlapping Buff A"
    )

    # 3. Conflicting mod B (same tuning ID as A)
    create_package_file(
        fixtures_dir / "conflicting_mod_b.package",
        tuning_id=0xAAAAAAAA,  # Same as mod A!
        resource_count=2,
        name="Overlapping Buff B"
    )

    # 4. Large mod with many resources
    create_package_file(
        fixtures_dir / "large_mod.package",
        tuning_id=0x22222222,
        resource_count=10,
        name="Complex Mod Resource"
    )

    # 5. Script mod
    create_ts4script_file(
        fixtures_dir / "script_mod.ts4script"
    )

    print(f"\n✅ Created {len(list(fixtures_dir.glob('*')))} fixture files in {fixtures_dir}")
    print("\nThese files can be used for:")
    print("  - Integration tests")
    print("  - User examples")
    print("  - Manual testing")
    print("  - Documentation screenshots")


if __name__ == "__main__":
    main()
