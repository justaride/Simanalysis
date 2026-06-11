"""Tests for DBPF parser."""

import struct
import zlib
from pathlib import Path

import pytest

from simanalysis.exceptions import DBPFError
from simanalysis.formats.types import SIMDATA, TUNING_GENERIC
from simanalysis.models import DBPFHeader
from simanalysis.parsers.dbpf import DBPFReader


class TestDBPFReader:
    """Tests for DBPFReader class."""

    @pytest.fixture
    def valid_dbpf_file(self, tmp_path: Path) -> Path:
        """Create a valid minimal DBPF file for testing."""
        dbpf_file = tmp_path / "test.package"

        # Create valid DBPF header (96 bytes)
        header = bytearray(96)

        # Magic "DBPF"
        header[0:4] = b"DBPF"

        # Major version = 2
        header[4:8] = struct.pack("<I", 2)

        # Minor version = 0
        header[8:12] = struct.pack("<I", 0)

        # User version = 0
        header[12:16] = struct.pack("<I", 0)

        # Flags = 0 (skip)
        header[16:20] = struct.pack("<I", 0)

        # Created date = 0 (skip)
        header[20:24] = struct.pack("<I", 0)

        # Modified date = 0 (skip)
        header[24:28] = struct.pack("<I", 0)

        # Index version = 0 (skip)
        header[28:32] = struct.pack("<I", 0)

        # 4 bytes reserved (skip)
        header[32:36] = struct.pack("<I", 0)

        # DBPF 2.0 spec (Sims 4):
        # Index count at offset 36
        header[36:40] = struct.pack("<I", 2)

        # Unknown/reserved at offset 40 (set to 0, parser will use offset 64)
        header[40:44] = struct.pack("<I", 0)

        # Index size at offset 44 (4-byte flags word + 2 entries * 32 bytes = 68)
        header[44:48] = struct.pack("<I", 68)

        # Reserved bytes 48-64
        header[48:64] = bytes(16)

        # Index offset at offset 64 (right after header = 96)
        header[64:68] = struct.pack("<I", 96)

        # Rest of header is zeros/reserved
        header[68:96] = bytes(28)

        # Build a real Sims 4 DBPF v2 index: a 32-bit mnIndexType flags word
        # followed by the entries. Here mnIndexType=0 (no constant fields), so
        # every entry is the full 32 bytes:
        #   type(4) group(4) instanceHi(4) instanceLo(4) chunkOffset(4)
        #   fileSize(4) memSize(4) compressed(2) committed(2)
        index_block_size = 4 + 2 * 32  # flags word + two 32-byte entries
        index = bytearray()
        index += struct.pack("<I", 0)  # mnIndexType: no constant fields

        # Resource 1: Generic tuning (uncompressed)
        resource1_offset = 96 + index_block_size  # after header + index
        resource1_data = b"<I>Test Generic Tuning Data</I>"
        resource1_size = len(resource1_data)
        index += struct.pack("<I", int(TUNING_GENERIC))  # type
        index += struct.pack("<I", 0x00000000)  # group
        index += struct.pack("<I", 0x12345678)  # instance high
        index += struct.pack("<I", 0x90ABCDEF)  # instance low
        index += struct.pack("<I", resource1_offset)  # chunk offset
        index += struct.pack("<I", resource1_size)  # file size (on disk)
        index += struct.pack("<I", resource1_size)  # mem size (uncompressed)
        index += struct.pack("<H", 0x0000)  # compressed: none
        index += struct.pack("<H", 1)  # committed

        # Resource 2: SimData (zlib-compressed)
        resource2_data = b"This is test SimData that will be compressed" * 10
        resource2_compressed = zlib.compress(resource2_data)
        resource2_size = len(resource2_data)
        resource2_compressed_size = len(resource2_compressed)
        resource2_offset = resource1_offset + resource1_size
        index += struct.pack("<I", int(SIMDATA))  # type
        index += struct.pack("<I", 0x00000000)  # group
        index += struct.pack("<I", 0xFEDCBA09)  # instance high
        index += struct.pack("<I", 0x87654321)  # instance low
        index += struct.pack("<I", resource2_offset)  # chunk offset
        index += struct.pack("<I", resource2_compressed_size)  # file size (compressed)
        index += struct.pack("<I", resource2_size)  # mem size (uncompressed)
        index += struct.pack("<H", 0x5A42)  # compressed: zlib
        index += struct.pack("<H", 1)  # committed

        # Write complete file
        with open(dbpf_file, "wb") as f:
            f.write(header)
            f.write(index)
            f.write(resource1_data)
            f.write(resource2_compressed)

        return dbpf_file

    @pytest.fixture
    def invalid_magic_file(self, tmp_path: Path) -> Path:
        """Create a file with invalid DBPF magic."""
        invalid_file = tmp_path / "invalid.package"

        header = bytearray(96)
        header[0:4] = b"ABCD"  # Invalid magic
        header[4:8] = struct.pack("<I", 2)  # Valid version

        with open(invalid_file, "wb") as f:
            f.write(header)

        return invalid_file

    @pytest.fixture
    def invalid_version_file(self, tmp_path: Path) -> Path:
        """Create a file with invalid DBPF version."""
        invalid_file = tmp_path / "invalid_version.package"

        header = bytearray(96)
        header[0:4] = b"DBPF"  # Valid magic
        header[4:8] = struct.pack("<I", 1)  # Invalid version (should be 2)

        with open(invalid_file, "wb") as f:
            f.write(header)

        return invalid_file

    @pytest.fixture
    def truncated_file(self, tmp_path: Path) -> Path:
        """Create a truncated DBPF file."""
        truncated_file = tmp_path / "truncated.package"

        # Only 50 bytes (less than 96 byte header)
        with open(truncated_file, "wb") as f:
            f.write(b"DBPF" + bytes(46))

        return truncated_file

    def test_init_nonexistent_file(self) -> None:
        """Test initialization with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            DBPFReader("/nonexistent/path/to/file.package")

    def test_init_directory(self, tmp_path: Path) -> None:
        """Test initialization with directory instead of file."""
        with pytest.raises(DBPFError, match="Path is not a file"):
            DBPFReader(tmp_path)

    def test_read_header_valid(self, valid_dbpf_file: Path) -> None:
        """Test reading valid DBPF header."""
        reader = DBPFReader(valid_dbpf_file)
        header = reader.read_header()

        assert isinstance(header, DBPFHeader)
        assert header.magic == b"DBPF"
        assert header.major_version == 2
        assert header.minor_version == 0
        assert header.user_version == 0
        assert header.index_count == 2
        assert header.index_offset == 96
        assert header.index_size == 68
        assert header.file_size > 0

    def test_read_header_invalid_magic(self, invalid_magic_file: Path) -> None:
        """Test reading header with invalid magic."""
        reader = DBPFReader(invalid_magic_file)

        with pytest.raises(DBPFError, match="Invalid DBPF"):
            reader.read_header()

    def test_read_header_invalid_version(self, invalid_version_file: Path) -> None:
        """Test reading header with invalid version."""
        reader = DBPFReader(invalid_version_file)

        with pytest.raises(DBPFError, match="Unsupported DBPF version"):
            reader.read_header()

    def test_read_header_truncated(self, truncated_file: Path) -> None:
        """Test reading truncated header."""
        reader = DBPFReader(truncated_file)

        with pytest.raises(DBPFError, match="File too small"):
            reader.read_header()

    def test_read_index_valid(self, valid_dbpf_file: Path) -> None:
        """Test reading valid index table."""
        reader = DBPFReader(valid_dbpf_file)
        resources = reader.read_index()

        assert len(resources) == 2

        # Check first resource (generic tuning)
        res1 = resources[0]
        assert res1.type == int(TUNING_GENERIC)
        assert res1.group == 0x00000000
        assert res1.instance == 0x1234567890ABCDEF
        assert res1.size > 0
        assert not res1.is_compressed

        # Check second resource (SimData, compressed)
        res2 = resources[1]
        assert res2.type == int(SIMDATA)
        assert res2.group == 0x00000000
        assert res2.instance == 0xFEDCBA0987654321
        assert res2.size > 0
        assert res2.is_compressed

    @pytest.fixture
    def flagged_dbpf_file(self, tmp_path: Path) -> Path:
        """Create a DBPF whose index uses constant Type+Group (mnIndexType=0x3).

        This is the real-world Sims 4 layout the old flat 32-byte parser could
        not read: constant fields are stored once and each entry is only 24
        bytes, so index_count * 32 overruns the (smaller) index table.
        """
        dbpf_file = tmp_path / "flagged.package"
        const_type = 0x034AEECB  # CAS Part
        const_group = 0x80000000
        entries = [
            # (instance_hi, instance_lo, payload)
            (0x00000000, 0x11111111, b"resource one"),
            (0x0000000A, 0x22222222, b"resource two is longer"),
            (0xDEADBEEF, 0x33333333, b"three"),
        ]
        n = len(entries)
        index_block_size = 4 + 4 + 4 + n * 24  # flags + const type + const group + 24B entries
        data_offset = 96 + index_block_size

        index = bytearray()
        index += struct.pack("<I", 0x3)  # mnIndexType: Type + Group constant
        index += struct.pack("<I", const_type)
        index += struct.pack("<I", const_group)

        blob = bytearray()
        for inst_hi, inst_lo, payload in entries:
            offset = data_offset + len(blob)
            index += struct.pack("<I", inst_hi)  # instance high
            index += struct.pack("<I", inst_lo)  # instance low
            index += struct.pack("<I", offset)  # chunk offset
            index += struct.pack("<I", len(payload))  # file size (on disk)
            index += struct.pack("<I", len(payload))  # mem size
            index += struct.pack("<H", 0x0000)  # compressed: none
            index += struct.pack("<H", 1)  # committed
            blob += payload

        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)  # major version
        header[8:12] = struct.pack("<I", 1)  # minor version
        header[36:40] = struct.pack("<I", n)  # index count
        header[44:48] = struct.pack("<I", len(index))  # index size
        header[64:68] = struct.pack("<I", 96)  # index offset

        with open(dbpf_file, "wb") as f:
            f.write(header)
            f.write(index)
            f.write(blob)
        return dbpf_file

    def test_read_index_with_constant_fields(self, flagged_dbpf_file: Path) -> None:
        """Index with constant Type/Group (24-byte entries) must parse correctly."""
        reader = DBPFReader(flagged_dbpf_file)
        header = reader.read_header()

        # The old flat parser assumed 32 bytes/entry, which overruns this table.
        assert header.index_count * 32 > header.index_size

        resources = reader.read_index()
        assert len(resources) == 3

        # The constant Type+Group (stored once) apply to every entry.
        assert all(r.type == 0x034AEECB for r in resources)
        assert all(r.group == 0x80000000 for r in resources)

        # Per-entry instances reconstruct as (hi << 32) | lo.
        assert resources[0].instance == 0x0000000011111111
        assert resources[1].instance == (0x0000000A << 32) | 0x22222222
        assert resources[2].instance == (0xDEADBEEF << 32) | 0x33333333

        # Offsets/sizes parsed from variable-size entries extract correctly.
        assert reader.get_resource(resources[2]) == b"three"

    def test_get_resource_uncompressed(self, valid_dbpf_file: Path) -> None:
        """Test extracting uncompressed resource."""
        reader = DBPFReader(valid_dbpf_file)
        resources = reader.read_index()

        # Get first resource (uncompressed tuning)
        data = reader.get_resource(resources[0])

        assert isinstance(data, bytes)
        assert b"Test Generic Tuning Data" in data
        assert len(data) == resources[0].size

    def test_get_resource_compressed(self, valid_dbpf_file: Path) -> None:
        """Test extracting compressed resource."""
        reader = DBPFReader(valid_dbpf_file)
        resources = reader.read_index()

        # Get second resource (compressed SimData)
        data = reader.get_resource(resources[1])

        assert isinstance(data, bytes)
        assert b"This is test SimData" in data
        assert len(data) == resources[1].size

    def test_get_resources_by_type(self, valid_dbpf_file: Path) -> None:
        """Test filtering resources by type."""
        reader = DBPFReader(valid_dbpf_file)

        # Get generic tuning resources
        tuning_resources = reader.get_resources_by_type(int(TUNING_GENERIC))
        assert len(tuning_resources) == 1
        assert tuning_resources[0].type == int(TUNING_GENERIC)

        # Get SimData resources
        simdata_resources = reader.get_resources_by_type(int(SIMDATA))
        assert len(simdata_resources) == 1
        assert simdata_resources[0].type == int(SIMDATA)

        # Get nonexistent type
        nonexistent = reader.get_resources_by_type(0xFFFFFFFF)
        assert len(nonexistent) == 0

    def test_get_resource_count(self, valid_dbpf_file: Path) -> None:
        """Test getting resource count."""
        reader = DBPFReader(valid_dbpf_file)
        count = reader.get_resource_count()

        assert count == 2

    def test_lazy_loading_resources(self, valid_dbpf_file: Path) -> None:
        """Test that resources are lazy loaded."""
        reader = DBPFReader(valid_dbpf_file)

        # Resources should not be loaded yet
        assert reader._resources is None

        # Access resources property
        resources = reader.resources

        # Resources should now be loaded
        assert reader._resources is not None
        assert len(resources) == 2

        # Accessing again should return cached resources
        resources2 = reader.resources
        assert resources is resources2

    def test_lazy_loading_header(self, valid_dbpf_file: Path) -> None:
        """Test that header is lazy loaded."""
        reader = DBPFReader(valid_dbpf_file)

        # Header should not be loaded yet
        assert reader._header is None

        # Access header property
        header = reader.header

        # Header should now be loaded
        assert reader._header is not None
        assert header.magic == b"DBPF"

        # Accessing again should return cached header
        header2 = reader.header
        assert header is header2

    def test_resource_key_property(self, valid_dbpf_file: Path) -> None:
        """Test DBPFResource.key property."""
        reader = DBPFReader(valid_dbpf_file)
        resources = reader.read_index()

        res1_key = resources[0].key
        assert isinstance(res1_key, tuple)
        assert len(res1_key) == 3
        assert res1_key[0] == resources[0].type
        assert res1_key[1] == resources[0].group
        assert res1_key[2] == resources[0].instance
