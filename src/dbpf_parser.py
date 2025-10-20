"""Utilities for parsing Sims 4 DBPF package files."""
from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


class DBPFParsingError(Exception):
    """Raised when a DBPF package cannot be parsed."""


@dataclass(frozen=True)
class DBPFResourceEntry:
    """Metadata for a single resource contained in a DBPF package."""

    type_id: int
    group_id: int
    instance_id: int
    offset: int
    size: int
    uncompressed_size: int
    compressed: bool

    @property
    def type_name(self) -> str:
        """Return a human-friendly representation of the resource type."""

        return RESOURCE_TYPE_NAMES.get(self.type_id, f"0x{self.type_id:08X}")


@dataclass
class DBPFPackage:
    """Represents a Sims 4 `.package` file."""

    path: Path
    header: "DBPFHeader"
    resources: List[DBPFResourceEntry]

    @classmethod
    def from_file(cls, path: Path) -> "DBPFPackage":
        with path.open("rb") as handle:
            header = DBPFHeader.read(handle)
            resources = _read_index(handle, header)
        return cls(path=path, header=header, resources=resources)


@dataclass(frozen=True)
class DBPFHeader:
    magic: bytes
    major_version: int
    minor_version: int
    index_count: int
    index_offset: int
    index_size: int
    index_version: int

    @classmethod
    def read(cls, handle: io.BufferedReader) -> "DBPFHeader":
        header_struct = struct.Struct("<4sIIIIIIIIIIIIIIII")
        header_bytes = handle.read(header_struct.size)
        if len(header_bytes) != header_struct.size:
            raise DBPFParsingError("File too small to contain DBPF header")

        (
            magic,
            major_version,
            minor_version,
            _user_major,
            _user_minor,
            _date_created,
            _date_modified,
            _index_major,
            _index_minor,
            index_count,
            index_offset,
            index_size,
            _hole_count,
            _hole_offset,
            _hole_size,
            index_version,
        ) = header_struct.unpack(header_bytes)

        if magic != b"DBPF":
            raise DBPFParsingError("Invalid DBPF magic header")

        return cls(
            magic=magic,
            major_version=major_version,
            minor_version=minor_version,
            index_count=index_count,
            index_offset=index_offset,
            index_size=index_size,
            index_version=index_version,
        )


RESOURCE_TYPE_NAMES = {
    0x545AC67A: "XML",
    0x626F626A: "OBJD",
    0x2F7D0004: "STBL",
    0xEB61E4F7: "ITUN",
    0x00B2D882: "IMG",
    0x2F7D0002: "DATA",
}


def _read_index(handle: io.BufferedReader, header: DBPFHeader) -> List[DBPFResourceEntry]:
    if header.index_count == 0:
        return []

    handle.seek(header.index_offset)

    if header.index_size % header.index_count != 0:
        raise DBPFParsingError(
            "Index size is not evenly divisible by entry count; unsupported format"
        )

    entry_size = header.index_size // header.index_count
    if entry_size < 24:
        raise DBPFParsingError(f"Unsupported DBPF index entry size: {entry_size}")

    entry_struct = struct.Struct("<" + "I" * (entry_size // 4))

    entries: List[DBPFResourceEntry] = []

    for _ in range(header.index_count):
        entry_data = handle.read(entry_size)
        if len(entry_data) != entry_size:
            raise DBPFParsingError("Unexpected end of file while reading index")

        values = entry_struct.unpack(entry_data)
        type_id = values[0]
        group_id = values[1]
        instance_high = values[2]
        instance_low = values[3]
        offset = values[4]
        size = values[5]
        uncompressed_size = size
        compressed = False

        if len(values) >= 7:
            uncompressed_size = values[6]
            compressed = uncompressed_size != size and uncompressed_size != 0
        if len(values) >= 8:
            compression_type = values[7]
            compressed = compressed or compression_type != 0

        instance_id = (instance_high << 32) | instance_low

        entries.append(
            DBPFResourceEntry(
                type_id=type_id,
                group_id=group_id,
                instance_id=instance_id,
                offset=offset,
                size=size,
                uncompressed_size=uncompressed_size or size,
                compressed=compressed,
            )
        )

    return entries


def load_package(path: Path) -> DBPFPackage:
    """Convenience wrapper that loads and parses a `.package` file."""

    path = Path(path)
    if not path.exists():
        raise DBPFParsingError(f"Package file not found: {path}")
    return DBPFPackage.from_file(path)


def batch_load(packages: Iterable[Path]) -> List[DBPFPackage]:
    """Parse a collection of packages, skipping those that fail to load."""

    parsed: List[DBPFPackage] = []
    for package in packages:
        try:
            parsed.append(load_package(package))
        except DBPFParsingError:
            continue
    return parsed
