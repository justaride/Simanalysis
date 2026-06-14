"""Conservative parser for Sims 4 SimData resources."""

from __future__ import annotations

import struct
from typing import ClassVar

from simanalysis.models import SimDataColumn, SimDataData, SimDataSchema, SimDataTable


class SimDataParser:
    """Read SimData table/schema metadata without decoding row values."""

    TYPE_ID = 0x545AC67A
    MAGIC = b"DATA"
    SUPPORTED_VERSIONS: ClassVar[set[int]] = {0x100, 0x101}
    HEADER_SIZE_V100 = 24
    HEADER_SIZE_V101 = 28
    TABLE_INFO_SIZE = 28
    SCHEMA_HEADER_SIZE = 24
    COLUMN_SIZE = 20
    RELOFFSET_NULL = -0x80000000

    @classmethod
    def parse(cls, data: bytes) -> SimDataData:
        """
        Parse high-level SimData metadata.

        This v0 reader intentionally stops at tables, schemas, columns, and
        names. Row values require type-specific decoding and are left for a
        later True Engine slice.
        """
        if len(data) < 8:
            return cls._malformed(0, "SimData header is truncated")

        if data[:4] != cls.MAGIC:
            return cls._malformed(0, "SimData magic is missing")

        version = struct.unpack_from("<I", data, 4)[0]
        if version not in cls.SUPPORTED_VERSIONS:
            return SimDataData(
                version=version,
                parse_status="unsupported",
                warnings=[
                    f"Unsupported SimData version {version:#x}; only 0x100 and 0x101 are parsed"
                ],
            )

        header_size = cls.HEADER_SIZE_V101 if version >= 0x101 else cls.HEADER_SIZE_V100
        if len(data) < header_size:
            return cls._malformed(version, "SimData header is truncated")

        try:
            table_header_offset = struct.unpack_from("<i", data, 8)[0]
            table_count = struct.unpack_from("<i", data, 12)[0]
            schema_offset = struct.unpack_from("<i", data, 16)[0]
            schema_count = struct.unpack_from("<i", data, 20)[0]
        except struct.error:
            return cls._malformed(version, "SimData header is truncated")

        if table_count < 0 or schema_count < 0:
            return cls._malformed(version, "SimData table or schema count is negative")

        table_start = 8 + table_header_offset
        schema_start = 16 + schema_offset
        if not cls._range_in_bounds(data, table_start, table_count * cls.TABLE_INFO_SIZE):
            return cls._malformed(version, "SimData table header block is out of bounds")
        if not cls._range_in_bounds(data, schema_start, schema_count * cls.SCHEMA_HEADER_SIZE):
            return cls._malformed(version, "SimData schema header block is out of bounds")

        try:
            tables = cls._parse_tables(data, table_start, table_count)
            schemas, schema_offsets = cls._parse_schemas(data, schema_start, schema_count)
        except struct.error as e:
            return cls._malformed(version, f"SimData metadata is truncated: {e}")

        for table in tables:
            if table.schema_offset is not None:
                table.schema_index = schema_offsets.get(table.schema_offset)

        warnings: list[str] = []
        if any(table.row_count > 0 for table in tables):
            warnings.append("SimData row values are not decoded by parser v0")

        return SimDataData(
            version=version,
            tables=tables,
            schemas=schemas,
            parse_status="parsed",
            warnings=warnings,
        )

    @classmethod
    def _parse_tables(cls, data: bytes, table_start: int, table_count: int) -> list[SimDataTable]:
        tables: list[SimDataTable] = []
        for index in range(table_count):
            pos = table_start + index * cls.TABLE_INFO_SIZE
            (
                name_rel,
                name_hash,
                schema_rel,
                data_type,
                row_size,
                row_rel,
                row_count,
            ) = struct.unpack_from("<iIiIIiI", data, pos)

            tables.append(
                SimDataTable(
                    name=cls._read_relative_string(data, pos, name_rel),
                    name_hash=name_hash,
                    data_type=data_type,
                    row_size=row_size,
                    row_count=row_count,
                    row_offset=cls._relative_offset(pos + 20, row_rel),
                    schema_offset=cls._relative_offset(pos + 8, schema_rel),
                )
            )

        return tables

    @classmethod
    def _parse_schemas(
        cls, data: bytes, schema_start: int, schema_count: int
    ) -> tuple[list[SimDataSchema], dict[int, int]]:
        schemas: list[SimDataSchema] = []
        schema_offsets: dict[int, int] = {}

        for index in range(schema_count):
            pos = schema_start + index * cls.SCHEMA_HEADER_SIZE
            (
                name_rel,
                name_hash,
                schema_hash,
                schema_size,
                column_rel,
                column_count,
            ) = struct.unpack_from("<iIIIiI", data, pos)

            column_start = cls._relative_offset(pos + 16, column_rel)
            columns: list[SimDataColumn] = []
            if column_start is not None:
                if not cls._range_in_bounds(data, column_start, column_count * cls.COLUMN_SIZE):
                    raise struct.error("schema column block is out of bounds")
                columns = cls._parse_columns(data, column_start, column_count)

            schemas.append(
                SimDataSchema(
                    name=cls._read_relative_string(data, pos, name_rel),
                    name_hash=name_hash,
                    schema_hash=schema_hash,
                    schema_size=schema_size,
                    columns=columns,
                )
            )
            schema_offsets[pos] = index

        return schemas, schema_offsets

    @classmethod
    def _parse_columns(
        cls, data: bytes, column_start: int, column_count: int
    ) -> list[SimDataColumn]:
        columns: list[SimDataColumn] = []
        for index in range(column_count):
            pos = column_start + index * cls.COLUMN_SIZE
            name_rel, name_hash, data_type, flags, offset, schema_rel = struct.unpack_from(
                "<iIHHIi", data, pos
            )
            columns.append(
                SimDataColumn(
                    name=cls._read_relative_string(data, pos, name_rel),
                    name_hash=name_hash,
                    data_type=data_type,
                    flags=flags,
                    offset=offset,
                    schema_offset=cls._relative_offset(pos + 16, schema_rel),
                )
            )
        return columns

    @classmethod
    def _read_relative_string(cls, data: bytes, field_pos: int, relative_offset: int) -> str | None:
        absolute = cls._relative_offset(field_pos, relative_offset)
        if absolute is None or absolute < 0 or absolute >= len(data):
            return None

        end = data.find(b"\0", absolute)
        if end < 0:
            return None

        try:
            return data[absolute:end].decode("utf-8")
        except UnicodeDecodeError:
            return None

    @classmethod
    def _relative_offset(cls, field_pos: int, relative_offset: int) -> int | None:
        if relative_offset == cls.RELOFFSET_NULL:
            return None
        return field_pos + relative_offset

    @staticmethod
    def _range_in_bounds(data: bytes, start: int, size: int) -> bool:
        return start >= 0 and size >= 0 and start + size <= len(data)

    @staticmethod
    def _malformed(version: int, warning: str) -> SimDataData:
        return SimDataData(
            version=version,
            parse_status="malformed",
            warnings=[warning],
        )
