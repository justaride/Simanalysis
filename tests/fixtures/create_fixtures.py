"""Script to create comprehensive sample fixture mod files for testing.

This creates realistic .package files that can be used for integration testing,
examples for users, and edge case testing.
"""

import struct
import zlib
from pathlib import Path
from typing import Optional


class DBPFBuilder:
    """Builder for creating DBPF package files programmatically."""

    DBPF_MAGIC = b"DBPF"
    HEADER_SIZE = 96
    INDEX_ENTRY_SIZE = 32

    # Resource type IDs
    TYPE_XML_TUNING = 0x545503B2
    TYPE_SIMDATA = 0x545238C9
    TYPE_STBL = 0x220557DA

    def __init__(self, major_version: int = 2, minor_version: int = 1):
        """
        Initialize DBPF builder.

        Args:
            major_version: DBPF major version (default: 2)
            minor_version: DBPF minor version (default: 1)
        """
        self.major_version = major_version
        self.minor_version = minor_version
        self.resources = []

    def add_resource(
        self,
        resource_type: int,
        group: int,
        instance: int,
        data: bytes,
        compressed: bool = True,
    ) -> 'DBPFBuilder':
        """
        Add a resource to the package.

        Args:
            resource_type: Resource type ID
            group: Resource group ID
            instance: Resource instance ID
            data: Raw resource data
            compressed: Whether to compress the data

        Returns:
            Self for method chaining
        """
        if compressed:
            compressed_data = zlib.compress(data, level=9)
        else:
            compressed_data = data

        self.resources.append({
            'type': resource_type,
            'group': group,
            'instance': instance,
            'data': compressed_data,
            'uncompressed_size': len(data),
            'compressed_size': len(compressed_data),
        })

        return self

    def add_xml_tuning(
        self,
        instance_id: int,
        tuning_name: str,
        tuning_class: str = "Buff",
        module: str = "buffs.buff_tuning",
        attributes: Optional[dict] = None,
    ) -> 'DBPFBuilder':
        """
        Add an XML tuning resource.

        Args:
            instance_id: Tuning instance ID
            tuning_name: Name of the tuning
            tuning_class: Class name (e.g., "Buff", "Trait")
            module: Python module path
            attributes: Custom attributes to add

        Returns:
            Self for method chaining
        """
        if attributes is None:
            attributes = {}

        xml_content = f'''<?xml version="1.0" encoding="utf-8"?>
<I c="{tuning_class}" i="{tuning_name}" m="{module}" n="{tuning_name}" s="{instance_id}">
  <T n="buff_type">1</T>
  <T n="mood_type">14</T>
  <L n="mood_weight">
    <T>1</T>
  </L>
'''

        # Add custom attributes
        for attr_name, attr_value in attributes.items():
            xml_content += f'  <T n="{attr_name}">{attr_value}</T>\n'

        xml_content += '</I>\n'

        self.add_resource(
            resource_type=self.TYPE_SIMDATA,  # Using SIMDATA for XML
            group=0x00000000,
            instance=instance_id,
            data=xml_content.encode('utf-8'),
            compressed=True,
        )

        return self

    def build(self, output_path: Path) -> None:
        """
        Build and write the DBPF package to disk.

        Args:
            output_path: Path where the package file should be written
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Calculate offsets
        index_count = len(self.resources)
        index_offset = self.HEADER_SIZE
        index_size = index_count * self.INDEX_ENTRY_SIZE
        data_offset = index_offset + index_size

        # Build header
        header = bytearray(self.HEADER_SIZE)
        header[0:4] = self.DBPF_MAGIC
        header[4:8] = struct.pack("<I", self.major_version)
        header[8:12] = struct.pack("<I", self.minor_version)
        header[40:44] = struct.pack("<I", index_count)
        header[44:48] = struct.pack("<I", index_offset)
        header[48:52] = struct.pack("<I", index_size)

        # Build index entries
        index_entries = []
        current_offset = data_offset

        for resource in self.resources:
            index_entry = struct.pack(
                "<IIQIIII",  # Added extra I for flags field (32 bytes total)
                resource['type'],
                resource['group'],
                resource['instance'],
                current_offset,
                resource['uncompressed_size'],
                resource['compressed_size'],
                0,  # flags (unused, set to 0)
            )
            index_entries.append(index_entry)
            current_offset += resource['compressed_size']

        # Write file
        with open(output_path, "wb") as f:
            f.write(header)

            for entry in index_entries:
                f.write(entry)

            for resource in self.resources:
                f.write(resource['data'])

        print(f"✅ Created: {output_path.name} ({index_count} resources, {output_path.stat().st_size} bytes)")


def create_simple_mod(output_dir: Path) -> None:
    """Create a simple mod with no conflicts."""
    builder = DBPFBuilder()
    builder.add_xml_tuning(
        instance_id=0x11111111,
        tuning_name="buff_simple_happy",
        tuning_class="Buff",
        attributes={
            "visible": "True",
            "is_walkstyle_buff": "False",
        }
    )
    builder.build(output_dir / "simple_mod.package")


def create_conflicting_mods(output_dir: Path) -> None:
    """Create two mods that conflict on tuning ID."""
    # Mod A
    builder_a = DBPFBuilder()
    builder_a.add_xml_tuning(
        instance_id=0xAAAAAAAA,  # Same ID!
        tuning_name="buff_confident",
        attributes={"mood_weight": "2"}
    )
    builder_a.build(output_dir / "conflicting_mod_a.package")

    # Mod B (conflicts with A)
    builder_b = DBPFBuilder()
    builder_b.add_xml_tuning(
        instance_id=0xAAAAAAAA,  # Same ID!
        tuning_name="buff_confident",
        attributes={"mood_weight": "5"}  # Different value!
    )
    builder_b.build(output_dir / "conflicting_mod_b.package")


def create_large_mod(output_dir: Path) -> None:
    """Create a mod with many resources for performance testing."""
    builder = DBPFBuilder()

    # Add 50 tunings
    for i in range(50):
        builder.add_xml_tuning(
            instance_id=0x22220000 + i,
            tuning_name=f"buff_large_mod_{i}",
        )

    builder.build(output_dir / "large_mod.package")


def create_edge_case_files(output_dir: Path) -> None:
    """Create edge case files for testing error handling."""

    # 1. Empty file
    empty_file = output_dir / "empty.package"
    empty_file.write_bytes(b"")
    print(f"✅ Created: {empty_file.name} (0 bytes)")

    # 2. Corrupted header (invalid magic)
    corrupted = output_dir / "corrupted_header.package"
    bad_header = bytearray(96)
    bad_header[0:4] = b"XXXX"  # Invalid magic
    corrupted.write_bytes(bad_header)
    print(f"✅ Created: {corrupted.name} (corrupted header)")

    # 3. Truncated file (header only, no index)
    truncated = output_dir / "truncated.package"
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[40:44] = struct.pack("<I", 10)  # Claims 10 resources
    header[44:48] = struct.pack("<I", 96)  # Index at byte 96
    truncated.write_bytes(header)  # But file ends here!
    print(f"✅ Created: {truncated.name} (truncated)")

    # 4. Package with uncompressed data
    builder = DBPFBuilder()
    builder.add_resource(
        resource_type=DBPFBuilder.TYPE_XML_TUNING,
        group=0,
        instance=0x33333333,
        data=b"Uncompressed test data",
        compressed=False,
    )
    builder.build(output_dir / "uncompressed.package")


def create_script_mods(output_dir: Path) -> None:
    """Create .ts4script files for script analysis testing."""
    import zipfile

    # Simple script with command
    script1 = b'''"""Simple Test Script"""
import sims4.commands

@sims4.commands.Command('test_command', command_type=sims4.commands.CommandType.Live)
def test_command(_connection=None):
    """Test command."""
    sims4.commands.output('Test!', _connection)
    return True
'''
    script_path = output_dir / "script_mod_simple.ts4script"
    with zipfile.ZipFile(script_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("test_script.py", script1)
    print(f"✅ Created: script_mod_simple.ts4script")

    # Script with injection
    script2 = b'''"""Script with Injection"""
import sims4.commands
from interactions import social_mixer

@inject_to(social_mixer.SocialMixer, 'apply_posture_state')
def custom_injection(original, self, *args, **kwargs):
    """Custom injection."""
    result = original(self, *args, **kwargs)
    return result

@sims4.commands.Command('custom_cmd')
def my_command(_connection=None):
    return True
'''
    script_path = output_dir / "script_mod_injection.ts4script"
    with zipfile.ZipFile(script_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("injection_script.py", script2)
    print(f"✅ Created: script_mod_injection.ts4script")

    # Script with conflicting command (same as simple)
    script3 = b'''"""Conflicting Script"""
import sims4.commands

@sims4.commands.Command('test_command', command_type=sims4.commands.CommandType.Live)
def different_test_command(_connection=None):
    """Different implementation of test_command - CONFLICT!"""
    sims4.commands.output('Different test!', _connection)
    return True
'''
    script_path = output_dir / "script_mod_conflicting.ts4script"
    with zipfile.ZipFile(script_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("conflicting_script.py", script3)
    print(f"✅ Created: script_mod_conflicting.ts4script")


def main():
    """Create all sample fixture files."""
    fixtures_dir = Path(__file__).parent / "sample_mods"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Creating comprehensive sample fixture mods...")
    print("=" * 60)
    print()

    print("📦 Core Fixtures:")
    create_simple_mod(fixtures_dir)
    create_conflicting_mods(fixtures_dir)
    create_large_mod(fixtures_dir)
    print()

    print("⚠️  Edge Case Fixtures:")
    create_edge_case_files(fixtures_dir)
    print()

    print("🐍 Script Fixtures:")
    create_script_mods(fixtures_dir)
    print()

    file_count = len(list(fixtures_dir.glob('*')))
    print("=" * 60)
    print(f"✅ Created {file_count} fixture files in {fixtures_dir}")
    print("=" * 60)
    print()
    print("These files can be used for:")
    print("  • Integration tests with real mod files")
    print("  • User examples and documentation")
    print("  • Manual testing and debugging")
    print("  • Edge case and error handling tests")
    print("  • Performance benchmarking")
    print()


if __name__ == "__main__":
    main()
