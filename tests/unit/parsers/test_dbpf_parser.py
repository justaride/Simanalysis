"""Tests for DBPF parser."""

import struct
import zlib
from pathlib import Path

import pytest

from simanalysis.exceptions import DBPFError
from simanalysis.models import DBPFHeader, DBPFResource
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

        # 4 bytes reserved (skip)
        header[36:40] = struct.pack("<I", 0)

        # Index count = 2 (we'll create 2 resources)
        header[40:44] = struct.pack("<I", 2)

        # Index offset = 96 (right after header)
        header[44:48] = struct.pack("<I", 96)

        # Index size = 64 (2 entries * 32 bytes)
        header[48:52] = struct.pack("<I", 64)

        # Rest of header is zeros/reserved
        header[52:96] = bytes(44)

        # Create index table (2 entries * 32 bytes = 64 bytes)
        index = bytearray(64)

        # Resource 1: XML Tuning
        resource1_offset = 96 + 64  # After header and index
        resource1_data = b"<I>Test XML Tuning Data</I>"
        resource1_size = len(resource1_data)

        # Type = 0x545238C9 (XML Tuning)
        index[0:4] = struct.pack("<I", 0x545238C9)
        # Group = 0
        index[4:8] = struct.pack("<I", 0x00000000)
        # Instance = 0x1234567890ABCDEF
        index[8:16] = struct.pack("<Q", 0x1234567890ABCDEF)
        # Offset
        index[16:20] = struct.pack("<I", resource1_offset)
        # Size
        index[20:24] = struct.pack("<I", resource1_size)
        # Compressed size = 0 (not compressed)
        index[24:28] = struct.pack("<I", 0)
        # Flags = 0
        index[28:32] = struct.pack("<I", 0)

        # Resource 2: SimData (compressed)
        resource2_offset = resource1_offset + resource1_size
        resource2_data = b"This is test SimData that will be compressed" * 10
        resource2_compressed = zlib.compress(resource2_data)
        resource2_size = len(resource2_data)
        resource2_compressed_size = len(resource2_compressed)

        # Type = 0x0333406C (SimData)
        index[32:36] = struct.pack("<I", 0x0333406C)
        # Group = 0
        index[36:40] = struct.pack("<I", 0x00000000)
        # Instance = 0xFEDCBA0987654321
        index[40:48] = struct.pack("<Q", 0xFEDCBA0987654321)
        # Offset
        index[48:52] = struct.pack("<I", resource2_offset)
        # Size (uncompressed)
        index[52:56] = struct.pack("<I", resource2_size)
        # Compressed size
        index[56:60] = struct.pack("<I", resource2_compressed_size)
        # Flags = 0
        index[60:64] = struct.pack("<I", 0)

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
        assert header.index_size == 64
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

        # Check first resource (XML Tuning)
        res1 = resources[0]
        assert res1.type == 0x545238C9
        assert res1.group == 0x00000000
        assert res1.instance == 0x1234567890ABCDEF
        assert res1.size > 0
        assert not res1.is_compressed

        # Check second resource (SimData, compressed)
        res2 = resources[1]
        assert res2.type == 0x0333406C
        assert res2.group == 0x00000000
        assert res2.instance == 0xFEDCBA0987654321
        assert res2.size > 0
        assert res2.is_compressed

    def test_get_resource_uncompressed(self, valid_dbpf_file: Path) -> None:
        """Test extracting uncompressed resource."""
        reader = DBPFReader(valid_dbpf_file)
        resources = reader.read_index()

        # Get first resource (uncompressed XML)
        data = reader.get_resource(resources[0])

        assert isinstance(data, bytes)
        assert b"Test XML Tuning Data" in data
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

        # Get XML Tuning resources
        xml_resources = reader.get_resources_by_type(0x545238C9)
        assert len(xml_resources) == 1
        assert xml_resources[0].type == 0x545238C9

        # Get SimData resources
        simdata_resources = reader.get_resources_by_type(0x0333406C)
        assert len(simdata_resources) == 1
        assert simdata_resources[0].type == 0x0333406C

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
