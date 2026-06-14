"""Build committed save-like and Tray real fixtures from deterministic bytes."""

from __future__ import annotations

import struct
from pathlib import Path

REAL_FIXTURES_DIR = Path(__file__).parents[1]
SAVE_PATH = REAL_FIXTURES_DIR / "saves" / "minimal_resource_refs.save"
TRAY_DIR = REAL_FIXTURES_DIR / "tray" / "minimal_household"


def _build_dbpf_save() -> None:
    resources = [
        (0x034A_EECB, 0x0000_0000, 0x0000_0000_0000_1111, b"cas fixture ref"),
        (0x515C_A4CD, 0x0000_0000, 0x0000_0000_0000_2222, b"build buy fixture ref"),
        (0x545A_C67A, 0x0000_0000, 0x0000_0000_0000_3333, b"other fixture ref"),
    ]

    index_size = 4 + 32 * len(resources)
    index_offset = 96
    data_offset = index_offset + index_size

    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[36:40] = struct.pack("<I", len(resources))
    header[44:48] = struct.pack("<I", index_size)
    header[64:68] = struct.pack("<I", index_offset)

    index = bytearray(struct.pack("<I", 0))
    blobs: list[bytes] = []
    current_offset = data_offset
    for resource_type, group, instance, data in resources:
        index += struct.pack("<I", resource_type)
        index += struct.pack("<I", group)
        index += struct.pack("<I", instance >> 32)
        index += struct.pack("<I", instance & 0xFFFF_FFFF)
        index += struct.pack("<I", current_offset)
        index += struct.pack("<I", len(data))
        index += struct.pack("<I", len(data))
        index += struct.pack("<H", 0)
        index += struct.pack("<H", 1)
        blobs.append(data)
        current_offset += len(data)

    SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAVE_PATH.open("wb") as handle:
        handle.write(header)
        handle.write(index)
        for blob in blobs:
            handle.write(blob)


def _build_tray() -> None:
    TRAY_DIR.mkdir(parents=True, exist_ok=True)
    base = TRAY_DIR / "fixture_household"
    name = "Fixture Household".encode("utf-16le") + b"\x00\x00"
    (base.with_suffix(".trayitem")).write_bytes(b"TRAY" + name + b"END")
    (base.with_suffix(".hhi")).write_bytes(b"HHI\x01fixture household companion")


def main() -> None:
    """Build both deterministic fixture families."""
    _build_dbpf_save()
    _build_tray()
    print(SAVE_PATH)
    print(TRAY_DIR)


if __name__ == "__main__":
    main()
