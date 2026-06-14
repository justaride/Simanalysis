"""Tests for Sims 4 STBL string table parsing."""

import struct

import pytest

from simanalysis.parsers.stbl import STBLParser

pytestmark = pytest.mark.synthetic


def make_stbl(entries: list[tuple[int, str]], version: int = 5) -> bytes:
    """Build a minimal TS4 STBL v5 payload."""
    encoded_entries = [(key, text.encode("utf-8")) for key, text in entries]
    declared_entry_size = sum(len(text_bytes) + 1 for _, text_bytes in encoded_entries)

    payload = bytearray(b"STBL")
    payload.append(version)
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


def test_parse_sims4_v5_stbl_entries() -> None:
    table = STBLParser.parse(
        make_stbl(
            [
                (0x12345678, "Hello Build/Buy"),
                (0x0000002A, "Cafe creme"),
            ]
        )
    )

    assert table.parse_status == "parsed"
    assert table.version == 5
    assert table.warnings == []
    assert table.strings == {
        0x12345678: "Hello Build/Buy",
        0x0000002A: "Cafe creme",
    }
    assert table.entries[0].key_hex == "0x12345678"


def test_parse_unsupported_stbl_version_degrades_honestly() -> None:
    table = STBLParser.parse(make_stbl([(0x12345678, "TS3 style")], version=2))

    assert table.parse_status == "unsupported"
    assert table.version == 2
    assert table.entries == []
    assert table.warnings == ["Unsupported STBL version 2; only Sims 4 version 5 is parsed"]


def test_parse_malformed_stbl_returns_status_instead_of_raising() -> None:
    table = STBLParser.parse(b"STBL\x05\x00")

    assert table.parse_status == "malformed"
    assert table.entries == []
    assert table.warnings == ["STBL header is truncated"]


def test_declared_entry_size_mismatch_marks_table_malformed() -> None:
    data = bytearray(make_stbl([(0x12345678, "short")]))
    data[17:21] = struct.pack("<I", 999)

    table = STBLParser.parse(bytes(data))

    assert table.parse_status == "malformed"
    assert table.strings == {0x12345678: "short"}
    assert table.warnings == ["STBL entry payload size mismatch: declared 999, parsed 6"]
