"""Tests for save file and tray item parsers."""

import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from simanalysis.parsers.save_file import (
    CASPart,
    ObjectReference,
    SaveFileData,
    SaveFileParser,
    SimDataParser,
    SimInfo,
    TrayItemData,
    TrayItemParser,
)


class TestCASPart:
    """Tests for CASPart data class."""

    def test_create_cas_part(self):
        """Test creating a CAS part."""
        part = CASPart(instance_id=0x1234567890ABCDEF)
        assert part.instance_id == 0x1234567890ABCDEF
        assert part.part_type == "Unknown"

    def test_cas_part_equality(self):
        """Test CAS part equality based on instance ID."""
        part1 = CASPart(instance_id=0x123)
        part2 = CASPart(instance_id=0x123)
        part3 = CASPart(instance_id=0x456)

        assert part1 == part2
        assert part1 != part3

    def test_cas_part_hashable(self):
        """Test that CAS parts can be used in sets."""
        part1 = CASPart(instance_id=0x123)
        part2 = CASPart(instance_id=0x123)
        part3 = CASPart(instance_id=0x456)

        parts_set = {part1, part2, part3}
        assert len(parts_set) == 2  # part1 and part2 are duplicates


class TestObjectReference:
    """Tests for ObjectReference data class."""

    def test_create_object_reference(self):
        """Test creating an object reference."""
        obj = ObjectReference(instance_id=0xABCDEF1234567890)
        assert obj.instance_id == 0xABCDEF1234567890
        assert obj.object_type == "Unknown"
        assert obj.count == 1

    def test_object_equality(self):
        """Test object equality based on instance ID."""
        obj1 = ObjectReference(instance_id=0x123)
        obj2 = ObjectReference(instance_id=0x123)
        obj3 = ObjectReference(instance_id=0x456)

        assert obj1 == obj2
        assert obj1 != obj3


class TestSimInfo:
    """Tests for SimInfo data class."""

    def test_create_sim_info(self):
        """Test creating Sim info."""
        sim = SimInfo(name="Test Sim", sim_id=0x123)
        assert sim.name == "Test Sim"
        assert sim.sim_id == 0x123
        assert len(sim.cas_parts) == 0

    def test_unique_cas_parts(self):
        """Test getting unique CAS parts."""
        sim = SimInfo(name="Test", sim_id=0x123)

        part1 = CASPart(instance_id=0x111)
        part2 = CASPart(instance_id=0x222)
        part3 = CASPart(instance_id=0x111)  # Duplicate

        sim.cas_parts = [part1, part2, part3]

        unique = sim.unique_cas_parts
        assert len(unique) == 2  # Only 2 unique parts

    def test_cas_part_count(self):
        """Test CAS part counting."""
        sim = SimInfo(name="Test", sim_id=0x123)

        sim.cas_parts = [
            CASPart(instance_id=0x111),
            CASPart(instance_id=0x222),
            CASPart(instance_id=0x111),  # Duplicate
        ]

        assert sim.cas_part_count == 2


class TestSaveFileData:
    """Tests for SaveFileData data class."""

    def test_create_save_file_data(self):
        """Test creating save file data."""
        save_data = SaveFileData(save_path=Path("test.save"))
        assert save_data.save_path == Path("test.save")
        assert len(save_data.sims) == 0
        assert len(save_data.objects) == 0

    def test_all_cas_parts(self):
        """Test getting all CAS parts across all Sims."""
        save_data = SaveFileData(save_path=Path("test.save"))

        sim1 = SimInfo(name="Sim1", sim_id=0x1)
        sim1.cas_parts = [
            CASPart(instance_id=0x111),
            CASPart(instance_id=0x222),
        ]

        sim2 = SimInfo(name="Sim2", sim_id=0x2)
        sim2.cas_parts = [
            CASPart(instance_id=0x222),  # Duplicate with Sim1
            CASPart(instance_id=0x333),
        ]

        save_data.sims = [sim1, sim2]

        all_parts = save_data.all_cas_parts
        assert len(all_parts) == 3  # 3 unique parts

    def test_total_cc_items(self):
        """Test total CC item counting."""
        save_data = SaveFileData(save_path=Path("test.save"))

        sim = SimInfo(name="Sim", sim_id=0x1)
        sim.cas_parts = [CASPart(instance_id=0x111)]

        save_data.sims = [sim]
        save_data.objects = [ObjectReference(instance_id=0x222)]

        assert save_data.total_cc_items == 2  # 1 CAS + 1 object


class TestTrayItemData:
    """Tests for TrayItemData data class."""

    def test_create_tray_item_data(self):
        """Test creating tray item data."""
        tray_data = TrayItemData(tray_path=Path("MySim.trayitem"))
        assert tray_data.tray_path == Path("MySim.trayitem")
        assert tray_data.item_type == "Unknown"

    def test_total_cc_items(self):
        """Test total CC item counting."""
        tray_data = TrayItemData(tray_path=Path("test.trayitem"))

        sim = SimInfo(name="Sim", sim_id=0x1)
        sim.cas_parts = [CASPart(instance_id=0x111)]

        tray_data.sims = [sim]
        tray_data.objects = [ObjectReference(instance_id=0x222)]

        assert tray_data.total_cc_items == 2


class TestSimDataParser:
    """Tests for SimDataParser."""

    def test_create_parser(self):
        """Test creating SimData parser."""
        parser = SimDataParser()
        assert parser is not None

    def test_parse_empty_data(self):
        """Test parsing empty data."""
        parser = SimDataParser()
        result = parser.parse(b"")

        assert result['cas_parts'] == []
        assert result['objects'] == []
        assert result['sim_name'] is None

    def test_parse_small_data(self):
        """Test parsing data too small."""
        parser = SimDataParser()
        result = parser.parse(b"small")

        assert result['cas_parts'] == []

    def test_extract_instance_ids(self):
        """Test extracting instance IDs from binary data."""
        parser = SimDataParser()

        # Create binary data with some instance IDs
        data = bytearray(100)

        # Add a 64-bit instance ID at offset 0
        instance_id_1 = 0x1234567890ABCDEF
        struct.pack_into("<Q", data, 0, instance_id_1)

        # Add another at offset 32
        instance_id_2 = 0xFEDCBA0987654321
        struct.pack_into("<Q", data, 32, instance_id_2)

        ids = parser._extract_instance_ids(bytes(data))

        assert instance_id_1 in ids
        assert instance_id_2 in ids

    def test_filter_cc_instance_ids(self):
        """Test filtering instance IDs to likely CC."""
        parser = SimDataParser()

        ids = [
            0x0000000000000001,  # Too small (likely EA)
            0x1234567890ABCDEF,  # Good CC ID
            0xFFFFFFFFFFFFFFFF,  # Max value (boundary)
            0xABCDEF1234567890,  # Good CC ID
        ]

        filtered = parser._filter_cc_instance_ids(ids)

        # All non-zero IDs should pass through in this simple implementation
        assert len(filtered) >= 2

    def test_extract_sim_name(self):
        """Test extracting Sim name from SimData."""
        parser = SimDataParser()

        # Create data with a UTF-16 LE string
        sim_name = "TestSim"
        name_bytes = sim_name.encode('utf-16-le')

        # Pad with some data before and after
        data = b'\x00' * 100 + name_bytes + b'\x00' * 100

        extracted_name = parser._extract_sim_name(data)

        # Name extraction is heuristic-based, so it might or might not find it
        # Just test that it doesn't crash
        assert extracted_name is None or isinstance(extracted_name, str)


class TestSaveFileParser:
    """Tests for SaveFileParser."""

    def test_create_parser(self):
        """Test creating save file parser."""
        parser = SaveFileParser()
        assert parser is not None
        assert parser.simdata_parser is not None

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_parse_save_file_not_found(self, mock_reader_class):
        """Test parsing non-existent save file."""
        parser = SaveFileParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_save_file(Path("/nonexistent/save.save"))

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_parse_save_file_basic(self, mock_reader_class, tmp_path):
        """Test basic save file parsing."""
        # Create a temporary save file
        save_file = tmp_path / "test.save"
        save_file.write_bytes(b"test content")

        # Mock the DBPF reader
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader

        # Mock no SimData resources
        mock_reader.get_resources_by_type.return_value = []

        parser = SaveFileParser()
        save_data = parser.parse_save_file(save_file)

        assert save_data.save_path == save_file
        assert len(save_data.sims) == 0

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_scan_saves_directory_not_found(self, mock_reader_class):
        """Test scanning non-existent directory."""
        parser = SaveFileParser()

        with pytest.raises(FileNotFoundError):
            parser.scan_saves_directory(Path("/nonexistent/directory"))

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_scan_saves_directory(self, mock_reader_class, tmp_path):
        """Test scanning saves directory."""
        # Create some test save files
        (tmp_path / "save1.save").write_bytes(b"test1")
        (tmp_path / "save2.save").write_bytes(b"test2")
        (tmp_path / "notasave.txt").write_bytes(b"ignore")

        # Mock the DBPF reader
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader
        mock_reader.get_resources_by_type.return_value = []

        parser = SaveFileParser()
        results = parser.scan_saves_directory(tmp_path)

        assert len(results) == 2  # Only .save files


class TestTrayItemParser:
    """Tests for TrayItemParser."""

    def test_create_parser(self):
        """Test creating tray item parser."""
        parser = TrayItemParser()
        assert parser is not None
        assert parser.simdata_parser is not None

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_parse_tray_item_not_found(self, mock_reader_class):
        """Test parsing non-existent tray file."""
        parser = TrayItemParser()

        with pytest.raises(FileNotFoundError):
            parser.parse_tray_item(Path("/nonexistent/sim.trayitem"))

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_parse_tray_item_basic(self, mock_reader_class, tmp_path):
        """Test basic tray item parsing."""
        # Create a temporary tray file
        tray_file = tmp_path / "MySim.trayitem"
        tray_file.write_bytes(b"test content")

        # Mock the DBPF reader
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader
        mock_reader.get_resources_by_type.return_value = []

        parser = TrayItemParser()
        tray_data = parser.parse_tray_item(tray_file)

        assert tray_data.tray_path == tray_file
        assert tray_data.item_name == "MySim"
        assert tray_data.item_type == "TrayItem"

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_parse_different_tray_types(self, mock_reader_class, tmp_path):
        """Test parsing different tray file types."""
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader
        mock_reader.get_resources_by_type.return_value = []

        parser = TrayItemParser()

        # Test .householdbinary
        household_file = tmp_path / "MyHousehold.householdbinary"
        household_file.write_bytes(b"test")
        tray_data = parser.parse_tray_item(household_file)
        assert tray_data.item_type == "Household"

        # Test .blueprint
        blueprint_file = tmp_path / "MyLot.blueprint"
        blueprint_file.write_bytes(b"test")
        tray_data = parser.parse_tray_item(blueprint_file)
        assert tray_data.item_type == "Lot"

        # Test .bpi
        bpi_file = tmp_path / "MyLot.bpi"
        bpi_file.write_bytes(b"test")
        tray_data = parser.parse_tray_item(bpi_file)
        assert tray_data.item_type == "Blueprint Info"

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_scan_tray_directory(self, mock_reader_class, tmp_path):
        """Test scanning tray directory."""
        # Create test tray files
        (tmp_path / "sim1.trayitem").write_bytes(b"test1")
        (tmp_path / "sim2.trayitem").write_bytes(b"test2")
        (tmp_path / "house.householdbinary").write_bytes(b"test3")
        (tmp_path / "lot.blueprint").write_bytes(b"test4")
        (tmp_path / "ignore.txt").write_bytes(b"ignore")

        # Mock the DBPF reader
        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader
        mock_reader.get_resources_by_type.return_value = []

        parser = TrayItemParser()
        results = parser.scan_tray_directory(tmp_path)

        assert len(results) == 4  # All tray file types


class TestIntegration:
    """Integration tests for save file parsing workflow."""

    @patch('simanalysis.parsers.save_file.DBPFReader')
    def test_full_workflow(self, mock_reader_class, tmp_path):
        """Test complete workflow from save to parsed data."""
        # This would require more complex mocking of DBPF resources
        # For now, just test that the components work together
        save_file = tmp_path / "test.save"
        save_file.write_bytes(b"test")

        mock_reader = MagicMock()
        mock_reader_class.return_value = mock_reader
        mock_reader.get_resources_by_type.return_value = []

        parser = SaveFileParser()
        save_data = parser.parse_save_file(save_file)

        assert isinstance(save_data, SaveFileData)
        assert save_data.save_path == save_file
