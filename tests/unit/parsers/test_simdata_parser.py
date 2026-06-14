"""Tests for conservative Sims 4 SimData parsing."""

import struct

import pytest

from simanalysis.parsers.simdata import SimDataParser

pytestmark = pytest.mark.synthetic


def make_simdata() -> bytes:
    """Build a minimal SimData v0x101 payload with one table/schema/column."""
    table_name = b"objects\0"
    schema_name = b"ObjectSchema\0"
    column_name = b"price\0"

    header_size = 28
    table_start = header_size
    table_size = 28
    schema_start = table_start + table_size
    schema_size = 24
    column_start = schema_start + schema_size
    column_size = 20
    string_start = column_start + column_size

    payload = bytearray()
    payload += b"DATA"
    payload += struct.pack("<I", 0x101)
    payload += struct.pack("<i", table_start - 8)
    payload += struct.pack("<i", 1)
    payload += struct.pack("<i", schema_start - 16)
    payload += struct.pack("<i", 1)
    payload += struct.pack("<I", 0xFFFFFFFF)

    payload += struct.pack("<i", string_start - table_start)
    payload += struct.pack("<I", 0x11111111)
    payload += struct.pack("<i", schema_start - (table_start + 8))
    payload += struct.pack("<I", 6)
    payload += struct.pack("<I", 4)
    payload += struct.pack("<i", 0)
    payload += struct.pack("<I", 0)

    payload += struct.pack("<i", string_start + len(table_name) - schema_start)
    payload += struct.pack("<I", 0x22222222)
    payload += struct.pack("<I", 0x33333333)
    payload += struct.pack("<I", 4)
    payload += struct.pack("<i", column_start - (schema_start + 16))
    payload += struct.pack("<I", 1)

    payload += struct.pack("<i", string_start + len(table_name) + len(schema_name) - column_start)
    payload += struct.pack("<I", 0x44444444)
    payload += struct.pack("<H", 6)
    payload += struct.pack("<H", 0)
    payload += struct.pack("<I", 0)
    payload += struct.pack("<i", -0x80000000)

    payload += table_name
    payload += schema_name
    payload += column_name

    return bytes(payload)


def test_parse_simdata_table_schema_and_column_metadata() -> None:
    simdata = SimDataParser.parse(make_simdata())

    assert simdata.parse_status == "parsed"
    assert simdata.version == 0x101
    assert simdata.table_count == 1
    assert simdata.schema_count == 1
    assert simdata.warnings == []

    assert simdata.tables[0].name == "objects"
    assert simdata.tables[0].name_hash == 0x11111111
    assert simdata.tables[0].schema_index == 0
    assert simdata.tables[0].data_type == 6
    assert simdata.tables[0].data_type_name == "int32"
    assert simdata.tables[0].row_size == 4
    assert simdata.tables[0].row_count == 0

    assert simdata.schemas[0].name == "ObjectSchema"
    assert simdata.schemas[0].schema_hash == 0x33333333
    assert simdata.schemas[0].columns[0].name == "price"
    assert simdata.schemas[0].columns[0].data_type_name == "int32"


def test_parse_unsupported_version_degrades_without_tables() -> None:
    data = bytearray(make_simdata())
    data[4:8] = struct.pack("<I", 0x200)

    simdata = SimDataParser.parse(bytes(data))

    assert simdata.parse_status == "unsupported"
    assert simdata.version == 0x200
    assert simdata.tables == []
    assert simdata.warnings == [
        "Unsupported SimData version 0x200; only 0x100 and 0x101 are parsed"
    ]


def test_parse_malformed_simdata_returns_status_instead_of_raising() -> None:
    simdata = SimDataParser.parse(b"DATA\x01")

    assert simdata.parse_status == "malformed"
    assert simdata.tables == []
    assert simdata.warnings == ["SimData header is truncated"]
