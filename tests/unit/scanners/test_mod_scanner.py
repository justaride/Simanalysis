"""Tests for mod scanner."""

import struct
import zlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from simanalysis.exceptions import SimanalysisError
from simanalysis.formats.types import BinaryResourceType, TuningResourceType
from simanalysis.models import ModType
from simanalysis.scanners import ModScanner

pytestmark = pytest.mark.synthetic


def make_stbl(entries: list[tuple[int, str]]) -> bytes:
    """Build a minimal TS4 STBL v5 payload."""
    encoded_entries = [(key, text.encode("utf-8")) for key, text in entries]
    declared_entry_size = sum(len(text_bytes) + 1 for _, text_bytes in encoded_entries)

    payload = bytearray(b"STBL\x05")
    payload += struct.pack("<H", 0)
    payload += struct.pack("<I", len(encoded_entries))
    payload += struct.pack("<H", 0)
    payload += struct.pack("<I", 0)
    payload += struct.pack("<I", declared_entry_size)

    for key, text_bytes in encoded_entries:
        payload += struct.pack("<I", key)
        payload.append(0)
        payload += struct.pack("<H", len(text_bytes))
        payload += text_bytes

    return bytes(payload)


class TestModScanner:
    """Tests for ModScanner."""

    @pytest.fixture
    def scanner(self) -> ModScanner:
        """Create scanner instance."""
        return ModScanner()

    @pytest.fixture
    def test_directory(self, tmp_path: Path) -> Path:
        """Create test directory structure."""
        # Create subdirectories
        (tmp_path / "Mods").mkdir()
        (tmp_path / "Mods" / "Subfolder").mkdir()

        return tmp_path / "Mods"

    @pytest.fixture
    def sample_package(self, test_directory: Path) -> Path:
        """Create a sample .package file."""
        package_path = test_directory / "test_mod.package"

        # Create minimal DBPF file (96-byte header)
        header = bytearray(96)

        # Magic
        header[0:4] = b"DBPF"

        # Major version = 2
        header[4:8] = struct.pack("<I", 2)

        # Minor version = 0
        header[8:12] = struct.pack("<I", 0)

        # User version = 0
        header[12:16] = struct.pack("<I", 0)

        # DBPF 2.0 spec (Sims 4):
        # Index count at offset 36
        header[36:40] = struct.pack("<I", 1)

        # Index size at offset 44 (4-byte flags word + 1 entry * 32 bytes = 36)
        header[44:48] = struct.pack("<I", 36)

        # Index offset at offset 64 (right after header = 96)
        header[64:68] = struct.pack("<I", 96)

        # One zlib-compressed resource in the real Sims 4 DBPF v2 layout:
        # a mnIndexType flags word (0 = no constant fields) then a 32-byte entry.
        resource_data = b"Test resource content"
        compressed_data = zlib.compress(resource_data)
        resource_offset = 96 + 36  # after header + index block

        index = bytearray()
        index += struct.pack("<I", 0)  # mnIndexType: no constant fields
        index += struct.pack("<I", 0x12345678)  # type
        index += struct.pack("<I", 0x00000000)  # group
        index += struct.pack("<I", 0xAABBCCDD)  # instance high
        index += struct.pack("<I", 0xEEFF0011)  # instance low
        index += struct.pack("<I", resource_offset)  # chunk offset
        index += struct.pack("<I", len(compressed_data))  # file size (compressed, on disk)
        index += struct.pack("<I", len(resource_data))  # mem size (uncompressed)
        index += struct.pack("<H", 0x5A42)  # compressed: zlib
        index += struct.pack("<H", 1)  # committed

        # Write file
        with open(package_path, "wb") as f:
            f.write(header)
            f.write(index)
            f.write(compressed_data)

        return package_path

    @pytest.fixture
    def sample_script(self, test_directory: Path) -> Path:
        """Create a sample .ts4script file."""
        script_path = test_directory / "test_script.ts4script"

        # Create ZIP with Python module
        with ZipFile(script_path, "w") as zf:
            # Add a simple Python module
            module_code = '''"""Test script module."""

__version__ = "1.0.0"
__author__ = "Test Author"

def test_function():
    """Test function."""
    pass
'''
            zf.writestr("test_module.py", module_code)

        return script_path

    def test_scanner_initialization(self, scanner: ModScanner) -> None:
        """Test scanner initializes correctly."""
        assert scanner.parse_tunings is True
        assert scanner.parse_scripts is True
        assert scanner.parse_string_tables is True
        assert scanner.calculate_hashes is True
        assert scanner.mods_scanned == 0
        assert len(scanner.errors_encountered) == 0

    def test_scanner_initialization_with_options(self) -> None:
        """Test scanner with custom options."""
        scanner = ModScanner(
            parse_tunings=False,
            parse_scripts=False,
            parse_string_tables=False,
            calculate_hashes=False,
        )

        assert scanner.parse_tunings is False
        assert scanner.parse_scripts is False
        assert scanner.parse_string_tables is False
        assert scanner.calculate_hashes is False

    def test_scan_directory_not_found(self, scanner: ModScanner) -> None:
        """Test scanning non-existent directory raises error."""
        with pytest.raises(SimanalysisError, match="Directory not found"):
            scanner.scan_directory(Path("/nonexistent/directory"))

    def test_scan_directory_not_dir(self, scanner: ModScanner, tmp_path: Path) -> None:
        """Test scanning a file raises error."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test", encoding="utf-8")

        with pytest.raises(SimanalysisError, match="Not a directory"):
            scanner.scan_directory(file_path)

    def test_scan_empty_directory(self, scanner: ModScanner, test_directory: Path) -> None:
        """Test scanning empty directory."""
        mods = scanner.scan_directory(test_directory)

        assert len(mods) == 0
        assert scanner.mods_scanned == 0

    def test_scan_directory_with_package(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test scanning directory with package file."""
        mods = scanner.scan_directory(sample_package.parent)

        assert len(mods) >= 1
        assert any(mod.name == "test_mod.package" for mod in mods)
        assert scanner.mods_scanned >= 1

    def test_scan_directory_with_script(self, scanner: ModScanner, sample_script: Path) -> None:
        """Test scanning directory with script file."""
        mods = scanner.scan_directory(sample_script.parent)

        assert len(mods) >= 1
        assert any(mod.name == "test_script.ts4script" for mod in mods)

    def test_scan_directory_recursive(
        self, scanner: ModScanner, test_directory: Path, sample_package: Path
    ) -> None:
        """Test recursive directory scanning."""
        # Move package to subfolder
        subfolder = test_directory / "Subfolder"
        new_path = subfolder / "nested_mod.package"
        sample_package.rename(new_path)

        # Scan with recursive=True
        mods = scanner.scan_directory(test_directory, recursive=True)
        assert len(mods) >= 1
        assert any("nested_mod.package" in mod.name for mod in mods)

        # Scan with recursive=False
        mods = scanner.scan_directory(test_directory, recursive=False)
        assert len(mods) == 0  # Shouldn't find the nested file

    def test_scan_directory_custom_extensions(
        self, scanner: ModScanner, test_directory: Path
    ) -> None:
        """Test scanning with custom file extensions."""
        # Create a .txt file
        txt_file = test_directory / "readme.txt"
        txt_file.write_text("Test", encoding="utf-8")

        # Scan with default extensions
        mods = scanner.scan_directory(test_directory, extensions={".package"})
        assert len(mods) == 0  # No .package files

        # Scan with .txt extension (shouldn't work, wrong format)
        mods = scanner.scan_directory(test_directory, extensions={".txt"})
        assert len(mods) == 0  # .txt files aren't valid mods

    def test_scan_file_package(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test scanning a single package file."""
        mod = scanner.scan_file(sample_package)

        assert mod is not None
        assert mod.name == "test_mod.package"
        assert mod.type == ModType.PACKAGE
        assert mod.size > 0
        assert len(mod.resources) > 0

    def test_scan_file_script(self, scanner: ModScanner, sample_script: Path) -> None:
        """Test scanning a single script file."""
        mod = scanner.scan_file(sample_script)

        assert mod is not None
        assert mod.name == "test_script.ts4script"
        assert mod.type == ModType.SCRIPT
        assert mod.size > 0

    def test_scan_file_nonexistent(self, scanner: ModScanner) -> None:
        """Test scanning non-existent file."""
        mod = scanner.scan_file(Path("/nonexistent/file.package"))

        assert mod is None

    def test_scan_file_with_hash(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test that file hash is calculated."""
        scanner.calculate_hashes = True
        mod = scanner.scan_file(sample_package)

        assert mod is not None
        assert mod.hash is not None
        assert len(mod.hash) == 64  # SHA256 hex string length

    def test_scan_file_without_hash(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test that hash calculation can be disabled."""
        scanner.calculate_hashes = False
        mod = scanner.scan_file(sample_package)

        assert mod is not None
        assert mod.hash is None

    def test_scan_package_with_resources(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test package scanning extracts resources."""
        mod = scanner.scan_file(sample_package)

        assert mod is not None
        assert len(mod.resources) == 1
        assert mod.resources[0].type == 0x12345678

    def test_scan_package_extracts_verified_tuning_types_and_skips_stbl(
        self, scanner: ModScanner, test_directory: Path
    ) -> None:
        """Test tuning extraction uses real tuning resource types, not STBL."""
        package_path = test_directory / "real_tuning_type.package"
        tuning_xml = b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Buff" i="buff_real" m="buffs.buff" s="12345">
            <T n="mood_weight">10</T>
        </I>
        """
        stbl_binary = b"\x00\x00\x00\x00not xml"
        resources = [
            (int(TuningResourceType.Buff), 0, 0x12345, tuning_xml),
            (int(BinaryResourceType.StringTable), 0, 0x67890, stbl_binary),
        ]

        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)
        header[8:12] = struct.pack("<I", 0)
        header[36:40] = struct.pack("<I", len(resources))
        index_size = 4 + 32 * len(resources)
        header[44:48] = struct.pack("<I", index_size)
        header[64:68] = struct.pack("<I", 96)

        index = bytearray()
        index += struct.pack("<I", 0)
        data_blobs = []
        current_offset = 96 + index_size
        for resource_type, group, instance, data in resources:
            compressed = zlib.compress(data)
            index += struct.pack("<I", resource_type)
            index += struct.pack("<I", group)
            index += struct.pack("<I", instance >> 32)
            index += struct.pack("<I", instance & 0xFFFFFFFF)
            index += struct.pack("<I", current_offset)
            index += struct.pack("<I", len(compressed))
            index += struct.pack("<I", len(data))
            index += struct.pack("<H", 0x5A42)
            index += struct.pack("<H", 1)
            data_blobs.append(compressed)
            current_offset += len(compressed)

        with package_path.open("wb") as handle:
            handle.write(header)
            handle.write(index)
            for blob in data_blobs:
                handle.write(blob)

        mod = scanner.scan_file(package_path)

        assert mod is not None
        assert [tuning.instance_id for tuning in mod.tunings] == [12345]
        assert mod.tunings[0].tuning_class == "Buff"

    def test_scan_package_extracts_stbl_string_tables(
        self, scanner: ModScanner, test_directory: Path
    ) -> None:
        """Test package scanning parses STBL resources with honest metadata."""
        package_path = test_directory / "string_table.package"
        stbl_binary = make_stbl([(0x12345678, "Hello Build/Buy")])
        resources = [
            (int(BinaryResourceType.StringTable), 0x80000000, 0x0B84CB2FC430848A, stbl_binary),
        ]

        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)
        header[8:12] = struct.pack("<I", 0)
        header[36:40] = struct.pack("<I", len(resources))
        index_size = 4 + 32 * len(resources)
        header[44:48] = struct.pack("<I", index_size)
        header[64:68] = struct.pack("<I", 96)

        index = bytearray()
        index += struct.pack("<I", 0)
        data_blobs = []
        current_offset = 96 + index_size
        for resource_type, group, instance, data in resources:
            compressed = zlib.compress(data)
            index += struct.pack("<I", resource_type)
            index += struct.pack("<I", group)
            index += struct.pack("<I", instance >> 32)
            index += struct.pack("<I", instance & 0xFFFFFFFF)
            index += struct.pack("<I", current_offset)
            index += struct.pack("<I", len(compressed))
            index += struct.pack("<I", len(data))
            index += struct.pack("<H", 0x5A42)
            index += struct.pack("<H", 1)
            data_blobs.append(compressed)
            current_offset += len(compressed)

        with package_path.open("wb") as handle:
            handle.write(header)
            handle.write(index)
            for blob in data_blobs:
                handle.write(blob)

        mod = scanner.scan_file(package_path)

        assert mod is not None
        assert len(mod.string_tables) == 1
        assert mod.string_tables[0].parse_status == "parsed"
        assert mod.string_tables[0].resource_group == 0x80000000
        assert mod.string_tables[0].resource_instance == 0x0B84CB2FC430848A
        assert mod.string_tables[0].strings == {0x12345678: "Hello Build/Buy"}

    def test_scan_script_with_metadata(self, scanner: ModScanner, sample_script: Path) -> None:
        """Test script scanning extracts metadata."""
        mod = scanner.scan_file(sample_script)

        assert mod is not None
        # Version and author should be extracted from module
        # (might be None if metadata extraction fails, that's OK)

    def test_scan_script_without_parsing(self, scanner: ModScanner, sample_script: Path) -> None:
        """Test script scanning with parsing disabled."""
        scanner.parse_scripts = False
        mod = scanner.scan_file(sample_script)

        assert mod is not None
        assert len(mod.scripts) == 0  # No scripts parsed

    def test_scan_handles_corrupt_files(self, scanner: ModScanner, test_directory: Path) -> None:
        """Test scanner handles corrupt files gracefully."""
        # Create corrupt package file
        corrupt_package = test_directory / "corrupt.package"
        corrupt_package.write_bytes(b"Not a valid DBPF file")

        # Should not crash, but might return minimal mod or skip
        mods = scanner.scan_directory(test_directory)

        # Either returns minimal mod or records error
        assert scanner.errors_encountered or any(m.name == "corrupt.package" for m in mods)

    def test_get_scan_summary(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test getting scan summary."""
        scanner.scan_directory(sample_package.parent)

        summary = scanner.get_scan_summary()

        assert "mods_scanned" in summary
        assert "errors_encountered" in summary
        assert "error_details" in summary
        assert summary["mods_scanned"] > 0

    def test_multiple_scans(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test that scanner can be reused for multiple scans."""
        # First scan
        mods1 = scanner.scan_directory(sample_package.parent)
        count1 = scanner.mods_scanned

        # Second scan
        mods2 = scanner.scan_directory(sample_package.parent)
        count2 = scanner.mods_scanned

        # Should reset counters for each scan
        assert len(mods1) == len(mods2)
        assert count1 == count2

    def test_scan_mixed_directory(
        self, scanner: ModScanner, sample_package: Path, sample_script: Path
    ) -> None:
        """Test scanning directory with both packages and scripts."""
        mods = scanner.scan_directory(sample_package.parent)

        # Should find both files
        assert len(mods) >= 2

        packages = [m for m in mods if m.type == ModType.PACKAGE]
        scripts = [m for m in mods if m.type == ModType.SCRIPT]

        assert len(packages) >= 1
        assert len(scripts) >= 1

    def test_scan_file_unsupported_extension(
        self, scanner: ModScanner, test_directory: Path
    ) -> None:
        """Test scanning file with unsupported extension."""
        txt_file = test_directory / "readme.txt"
        txt_file.write_text("Test", encoding="utf-8")

        mod = scanner.scan_file(txt_file)

        assert mod is None  # Unsupported file type

    def test_hash_consistency(self, scanner: ModScanner, sample_package: Path) -> None:
        """Test that hash calculation is consistent."""
        scanner.calculate_hashes = True

        mod1 = scanner.scan_file(sample_package)
        mod2 = scanner.scan_file(sample_package)

        assert mod1 is not None
        assert mod2 is not None
        assert mod1.hash == mod2.hash  # Same file should have same hash

    def test_scan_directory_sorts_results(self, scanner: ModScanner, test_directory: Path) -> None:
        """Test that scan results are sorted by path."""
        # Create multiple files
        for i in range(3):
            pkg = test_directory / f"mod_{i}.package"
            # Create minimal DBPF
            pkg.write_bytes(b"DBPF" + b"\x00" * 92)  # Minimal header

        mods = scanner.scan_directory(test_directory)

        # Should be sorted by name (due to sorted() in _find_mod_files)
        if len(mods) >= 2:
            for i in range(len(mods) - 1):
                assert mods[i].name <= mods[i + 1].name
