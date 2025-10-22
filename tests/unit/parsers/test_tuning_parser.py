"""Tests for XML Tuning parser."""

import pytest

from simanalysis.exceptions import TuningError
from simanalysis.models import TuningData
from simanalysis.parsers.tuning import TuningParser


class TestTuningParser:
    """Tests for TuningParser class."""

    @pytest.fixture
    def parser(self) -> TuningParser:
        """Create a TuningParser instance."""
        return TuningParser()

    @pytest.fixture
    def simple_tuning_xml(self) -> bytes:
        """Create a simple valid tuning XML."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Buff" i="buff_Confident" m="buffs.buff" s="12345">
            <T n="mood_type">15</T>
            <T n="mood_weight">10</T>
        </I>
        """

    @pytest.fixture
    def complex_tuning_xml(self) -> bytes:
        """Create a complex tuning XML with references and pack requirements."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Trait" i="trait_Active" m="traits.trait" s="0x00012E75">
            <T n="display_name">0x8B3A7A89</T>
            <T n="description">0x8B3A7A8A</T>
            <L n="buffs">
                <T>buff_Energized<!--12346--></T>
                <T t="0x00ABCDEF">buff_Happy</T>
            </L>
            <T n="special_text">Requires EP01:Get to Work</T>
            <U n="ages">
                <T>TEEN</T>
                <T>YOUNGADULT</T>
                <T>ADULT</T>
                <T>ELDER</T>
            </U>
        </I>
        """

    @pytest.fixture
    def hex_instance_xml(self) -> bytes:
        """Create tuning with hex instance ID."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Object" i="object_table" m="objects" s="0x1234ABCD">
            <T n="price">500</T>
        </I>
        """

    @pytest.fixture
    def decimal_instance_xml(self) -> bytes:
        """Create tuning with decimal instance ID."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Interaction" i="interaction_sit" m="interactions" s="98765">
            <T n="target">SIM</T>
        </I>
        """

    @pytest.fixture
    def pack_requirement_xml(self) -> bytes:
        """Create tuning with pack requirements."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Buff" i="buff_vampire" m="EP04.buffs.vampire_buffs" s="11111">
            <T n="description">Vampire buff from EP04:Cats and Dogs</T>
            <T n="icon">EP04/UI/icon.png</T>
            <T n="related">GP04.Vampires.buff</T>
        </I>
        """

    @pytest.fixture
    def invalid_xml(self) -> bytes:
        """Create invalid XML."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Buff" i="broken"
            <T n="incomplete
        """

    @pytest.fixture
    def missing_instance_xml(self) -> bytes:
        """Create XML without instance ID."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
        <I c="Buff" n="buff_test" m="buffs">
            <T n="test">value</T>
        </I>
        """

    def test_parse_simple_tuning(
        self, parser: TuningParser, simple_tuning_xml: bytes
    ) -> None:
        """Test parsing simple tuning XML."""
        tuning = parser.parse(simple_tuning_xml)

        assert isinstance(tuning, TuningData)
        assert tuning.instance_id == 12345
        assert tuning.tuning_name == "buff_Confident"
        assert tuning.tuning_class == "Buff"
        assert tuning.module == "buffs.buff"

    def test_parse_complex_tuning(
        self, parser: TuningParser, complex_tuning_xml: bytes
    ) -> None:
        """Test parsing complex tuning XML."""
        tuning = parser.parse(complex_tuning_xml)

        assert tuning.instance_id == 0x00012E75
        assert tuning.tuning_name == "trait_Active"
        assert tuning.tuning_class == "Trait"
        assert tuning.module == "traits.trait"

        # Check modifications
        assert len(tuning.modified_attributes) > 0
        assert "display_name" in tuning.modified_attributes

    def test_parse_hex_instance_id(
        self, parser: TuningParser, hex_instance_xml: bytes
    ) -> None:
        """Test parsing hex instance ID."""
        tuning = parser.parse(hex_instance_xml)

        assert tuning.instance_id == 0x1234ABCD

    def test_parse_decimal_instance_id(
        self, parser: TuningParser, decimal_instance_xml: bytes
    ) -> None:
        """Test parsing decimal instance ID."""
        tuning = parser.parse(decimal_instance_xml)

        assert tuning.instance_id == 98765

    def test_extract_modifications(
        self, parser: TuningParser, simple_tuning_xml: bytes
    ) -> None:
        """Test extracting modified attributes."""
        tuning = parser.parse(simple_tuning_xml)

        assert "mood_type" in tuning.modified_attributes
        assert tuning.modified_attributes["mood_type"] == "15"
        assert "mood_weight" in tuning.modified_attributes
        assert tuning.modified_attributes["mood_weight"] == "10"

    def test_find_references(
        self, parser: TuningParser, complex_tuning_xml: bytes
    ) -> None:
        """Test finding references to other tunings."""
        tuning = parser.parse(complex_tuning_xml)

        assert len(tuning.references) > 0
        # Should find the reference 0x00ABCDEF
        assert 0x00ABCDEF in tuning.references
        # Should find display_name reference
        assert 0x8B3A7A89 in tuning.references

    def test_detect_pack_requirements(
        self, parser: TuningParser, pack_requirement_xml: bytes
    ) -> None:
        """Test detecting pack requirements."""
        tuning = parser.parse(pack_requirement_xml)

        assert len(tuning.pack_requirements) > 0
        # Should detect EP04 from multiple sources
        assert "EP04" in tuning.pack_requirements
        # Should detect GP04
        assert "GP04" in tuning.pack_requirements

    def test_detect_pack_from_module(
        self, parser: TuningParser, pack_requirement_xml: bytes
    ) -> None:
        """Test detecting pack from module path."""
        tuning = parser.parse(pack_requirement_xml)

        # Module is "EP04.buffs.vampire_buffs"
        assert "EP04" in tuning.pack_requirements

    def test_invalid_xml_raises_error(
        self, parser: TuningParser, invalid_xml: bytes
    ) -> None:
        """Test that invalid XML raises TuningError."""
        with pytest.raises(TuningError, match="Invalid XML syntax"):
            parser.parse(invalid_xml)

    def test_missing_instance_id_raises_error(
        self, parser: TuningParser, missing_instance_xml: bytes
    ) -> None:
        """Test that missing instance ID raises TuningError."""
        with pytest.raises(TuningError, match="Instance ID not found"):
            parser.parse(missing_instance_xml)

    def test_get_tuning_name_fallback(self, parser: TuningParser) -> None:
        """Test tuning name fallback to tag name."""
        xml = b'<Buff c="Buff" s="123"><T n="test">value</T></Buff>'

        tuning = parser.parse(xml)
        # Should use tag name as fallback
        assert tuning.tuning_name == "Buff"

    def test_get_module_default(self, parser: TuningParser) -> None:
        """Test module defaults to 'unknown'."""
        xml = b'<I c="Buff" i="test" s="123"><T n="test">value</T></I>'

        tuning = parser.parse(xml)
        assert tuning.module == "unknown"

    def test_parse_tuning_file_alias(
        self, parser: TuningParser, simple_tuning_xml: bytes
    ) -> None:
        """Test parse_tuning_file is an alias for parse."""
        tuning1 = parser.parse(simple_tuning_xml)
        tuning2 = parser.parse_tuning_file(simple_tuning_xml)

        assert tuning1.instance_id == tuning2.instance_id
        assert tuning1.tuning_name == tuning2.tuning_name

    def test_empty_modifications(self, parser: TuningParser) -> None:
        """Test tuning with no modifications."""
        xml = b'<I c="Buff" i="test" s="123" m="buffs"></I>'

        tuning = parser.parse(xml)
        assert tuning.modified_attributes == {}

    def test_no_references(self, parser: TuningParser) -> None:
        """Test tuning with no references."""
        xml = b'<I c="Buff" i="test" s="123" m="buffs"><T n="test">plain text</T></I>'

        tuning = parser.parse(xml)
        assert len(tuning.references) == 0

    def test_no_pack_requirements(
        self, parser: TuningParser, simple_tuning_xml: bytes
    ) -> None:
        """Test tuning with no pack requirements."""
        tuning = parser.parse(simple_tuning_xml)

        assert len(tuning.pack_requirements) == 0

    def test_multiple_references(self, parser: TuningParser) -> None:
        """Test extracting multiple references."""
        xml = b"""<I c="Trait" i="test" s="123" m="traits">
            <T t="0x11111111">ref1</T>
            <T t="0x22222222">ref2</T>
            <T>0x33333333</T>
        </I>"""

        tuning = parser.parse(xml)

        assert 0x11111111 in tuning.references
        assert 0x22222222 in tuning.references
        assert 0x33333333 in tuning.references
        assert len(tuning.references) == 3

    def test_extract_tuning_id_from_text(self, parser: TuningParser) -> None:
        """Test _extract_tuning_id helper method."""
        # Valid hex ID
        tuning_id = parser._extract_tuning_id("0x12345678")
        assert tuning_id == 0x12345678

        # Valid hex ID without 0x prefix
        tuning_id = parser._extract_tuning_id("ABCD1234")
        assert tuning_id == 0xABCD1234

        # Invalid text
        tuning_id = parser._extract_tuning_id("not a tuning id")
        assert tuning_id is None

        # Too short
        tuning_id = parser._extract_tuning_id("0x123")
        assert tuning_id is None

    def test_modified_attributes_with_various_types(
        self, parser: TuningParser
    ) -> None:
        """Test extracting modifications with various attribute types."""
        xml = b"""<I c="Buff" i="test" s="123" m="buffs">
            <T n="text_value">some text</T>
            <T n="type_attr" t="SomeType"></T>
            <T n="class_attr" c="SomeClass"></T>
            <T n="module_attr" m="some.module"></T>
            <T n="path_attr" p="some/path"></T>
        </I>"""

        tuning = parser.parse(xml)

        assert "text_value" in tuning.modified_attributes
        assert tuning.modified_attributes["text_value"] == "some text"
        assert "type_attr" in tuning.modified_attributes
        assert tuning.modified_attributes["type_attr"] == "SomeType"
