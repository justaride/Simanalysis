"""Parser for Sims 4 STBL string table resources."""

from __future__ import annotations

import struct

from simanalysis.models import StringTableData, StringTableEntry


class STBLParser:
    """Conservative reader for Sims 4 STBL version 5 resources."""

    TYPE_ID = 0x220557DA
    MAGIC = b"STBL"
    SUPPORTED_VERSION = 5
    HEADER_SIZE = 21

    @classmethod
    def parse(cls, data: bytes) -> StringTableData:
        """
        Parse a Sims 4 STBL payload.

        The reader returns a ``StringTableData`` object for all inputs. Unknown
        or damaged resources are marked as ``unsupported`` or ``malformed`` so
        callers can surface partial/uncertain analysis instead of silently
        dropping the resource.
        """
        if len(data) < cls.HEADER_SIZE:
            return StringTableData(
                version=data[4] if len(data) >= 5 and data[:4] == cls.MAGIC else 0,
                parse_status="malformed",
                warnings=["STBL header is truncated"],
            )

        if data[:4] != cls.MAGIC:
            return StringTableData(
                version=0,
                parse_status="malformed",
                warnings=["STBL magic is missing"],
            )

        version = data[4]
        if version != cls.SUPPORTED_VERSION:
            return StringTableData(
                version=version,
                parse_status="unsupported",
                warnings=[f"Unsupported STBL version {version}; only Sims 4 version 5 is parsed"],
            )

        try:
            entry_count = struct.unpack_from("<I", data, 7)[0]
            declared_entry_size = struct.unpack_from("<I", data, 17)[0]
        except struct.error:
            return StringTableData(
                version=version,
                parse_status="malformed",
                warnings=["STBL header is truncated"],
            )

        entries: list[StringTableEntry] = []
        warnings: list[str] = []
        offset = cls.HEADER_SIZE
        parsed_entry_size = 0

        for entry_index in range(entry_count):
            remaining = len(data) - offset
            if remaining < 7:
                return StringTableData(
                    version=version,
                    entries=entries,
                    parse_status="malformed",
                    warnings=[
                        *warnings,
                        f"STBL entry {entry_index} is truncated before its key/length fields",
                    ],
                    declared_entry_size=declared_entry_size,
                )

            key = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            flags = data[offset]
            offset += 1
            string_length = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            if len(data) - offset < string_length:
                return StringTableData(
                    version=version,
                    entries=entries,
                    parse_status="malformed",
                    warnings=[
                        *warnings,
                        f"STBL entry {entry_index} declares {string_length} bytes past EOF",
                    ],
                    declared_entry_size=declared_entry_size,
                )

            raw_text = data[offset : offset + string_length]
            offset += string_length
            parsed_entry_size += string_length + 1

            try:
                text = raw_text.decode("utf-8")
            except UnicodeDecodeError:
                return StringTableData(
                    version=version,
                    entries=entries,
                    parse_status="malformed",
                    warnings=[
                        *warnings,
                        f"STBL entry {entry_index} is not valid UTF-8",
                    ],
                    declared_entry_size=declared_entry_size,
                )

            entries.append(StringTableEntry(key=key, text=text, flags=flags))

        parse_status = "parsed"
        if parsed_entry_size != declared_entry_size:
            parse_status = "malformed"
            warnings.append(
                "STBL entry payload size mismatch: "
                f"declared {declared_entry_size}, parsed {parsed_entry_size}"
            )

        trailing = len(data) - offset
        if trailing > 0:
            warnings.append(f"STBL has {trailing} trailing bytes after declared entries")

        return StringTableData(
            version=version,
            entries=entries,
            parse_status=parse_status,
            warnings=warnings,
            declared_entry_size=declared_entry_size,
        )
