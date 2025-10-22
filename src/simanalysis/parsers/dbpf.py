"""DBPF (Database Packed File) parser for Sims 4 .package files.

The DBPF format is used by The Sims 4 to store game resources in package files.
This module provides tools to read and extract resources from these files.

Format specification: https://simswiki.info/DatabasePackedFile
"""

import struct
import zlib
from pathlib import Path
from typing import BinaryIO, List, Optional

from simanalysis.exceptions import DBPFError
from simanalysis.models import DBPFHeader, DBPFResource


class DBPFReader:
    """
    Reader for DBPF package files.

    The DBPF format consists of:
    - Header (96 bytes) containing metadata
    - Index table with resource entries
    - Resource data (may be compressed)

    Example:
        >>> reader = DBPFReader("my_mod.package")
        >>> header = reader.read_header()
        >>> resources = reader.read_index()
        >>> xml_resources = reader.get_resources_by_type(0x545238C9)
    """

    # DBPF format constants
    HEADER_SIZE = 96
    HEADER_MAGIC = b"DBPF"
    MAJOR_VERSION = 2
    INDEX_ENTRY_SIZE = 32  # Size of each index entry

    def __init__(self, package_path: Path | str) -> None:
        """
        Initialize DBPF reader.

        Args:
            package_path: Path to .package file

        Raises:
            FileNotFoundError: If package file doesn't exist
            DBPFError: If file is not a valid DBPF package
        """
        self.path = Path(package_path)

        if not self.path.exists():
            raise FileNotFoundError(f"Package file not found: {self.path}")

        if not self.path.is_file():
            raise DBPFError(f"Path is not a file: {self.path}")

        self._header: Optional[DBPFHeader] = None
        self._resources: Optional[List[DBPFResource]] = None

    def read_header(self) -> DBPFHeader:
        """
        Read and parse DBPF header.

        Returns:
            DBPFHeader with parsed metadata

        Raises:
            DBPFError: If header is invalid or corrupted
        """
        with open(self.path, "rb") as f:
            header_data = f.read(self.HEADER_SIZE)

            if len(header_data) < self.HEADER_SIZE:
                raise DBPFError(
                    f"File too small: expected at least {self.HEADER_SIZE} bytes, "
                    f"got {len(header_data)}"
                )

            try:
                # Parse header fields
                # Format: 4s = magic (4 bytes)
                #         I = major_version (4 bytes unsigned)
                #         I = minor_version (4 bytes unsigned)
                #         I = user_version (4 bytes unsigned)
                #         I = flags (4 bytes, skip)
                #         I = created_date (4 bytes, skip)
                #         I = modified_date (4 bytes, skip)
                #         I = index_version (4 bytes, skip)
                #         I = index_count (4 bytes unsigned)
                #         I = index_offset (4 bytes unsigned)
                #         I = index_size (4 bytes unsigned)
                #         ... (rest of header)

                magic = header_data[0:4]
                major_version = struct.unpack("<I", header_data[4:8])[0]
                minor_version = struct.unpack("<I", header_data[8:12])[0]
                user_version = struct.unpack("<I", header_data[12:16])[0]

                # Skip flags, dates, index_version (24 bytes)
                index_count = struct.unpack("<I", header_data[40:44])[0]
                index_offset = struct.unpack("<I", header_data[44:48])[0]
                index_size = struct.unpack("<I", header_data[48:52])[0]

                # Get file size
                file_size = self.path.stat().st_size

                header = DBPFHeader(
                    magic=magic,
                    major_version=major_version,
                    minor_version=minor_version,
                    user_version=user_version,
                    index_count=index_count,
                    index_offset=index_offset,
                    index_size=index_size,
                    file_size=file_size,
                )

                self._header = header
                return header

            except struct.error as e:
                raise DBPFError(f"Failed to parse DBPF header: {e}") from e
            except ValueError as e:
                # Raised by DBPFHeader validation
                raise DBPFError(f"Invalid DBPF header: {e}") from e

    def read_index(self) -> List[DBPFResource]:
        """
        Read and parse the resource index table.

        Returns:
            List of DBPFResource entries

        Raises:
            DBPFError: If index cannot be read or is corrupted
        """
        if self._header is None:
            self._header = self.read_header()

        with open(self.path, "rb") as f:
            # Seek to index table
            f.seek(self._header.index_offset)

            # Read entire index table
            index_data = f.read(self._header.index_size)

            if len(index_data) < self._header.index_size:
                raise DBPFError(
                    f"Could not read complete index table: "
                    f"expected {self._header.index_size} bytes, "
                    f"got {len(index_data)}"
                )

            resources = []
            offset = 0

            for i in range(self._header.index_count):
                if offset + self.INDEX_ENTRY_SIZE > len(index_data):
                    raise DBPFError(
                        f"Index entry {i} extends beyond index table "
                        f"(offset {offset} + {self.INDEX_ENTRY_SIZE} > {len(index_data)})"
                    )

                entry_data = index_data[offset : offset + self.INDEX_ENTRY_SIZE]

                try:
                    # Parse index entry
                    # Format: I = type (4 bytes)
                    #         I = group (4 bytes)
                    #         Q = instance (8 bytes)
                    #         I = offset (4 bytes)
                    #         I = size (4 bytes)
                    #         I = compressed_size (4 bytes)
                    #         I = flags (4 bytes, skip)

                    res_type = struct.unpack("<I", entry_data[0:4])[0]
                    res_group = struct.unpack("<I", entry_data[4:8])[0]
                    res_instance = struct.unpack("<Q", entry_data[8:16])[0]
                    res_offset = struct.unpack("<I", entry_data[16:20])[0]
                    res_size = struct.unpack("<I", entry_data[20:24])[0]
                    res_compressed_size = struct.unpack("<I", entry_data[24:28])[0]

                    resource = DBPFResource(
                        type=res_type,
                        group=res_group,
                        instance=res_instance,
                        offset=res_offset,
                        size=res_size,
                        compressed_size=res_compressed_size,
                    )

                    resources.append(resource)

                except struct.error as e:
                    raise DBPFError(f"Failed to parse index entry {i}: {e}") from e

                offset += self.INDEX_ENTRY_SIZE

            self._resources = resources
            return resources

    def get_resource(self, resource: DBPFResource) -> bytes:
        """
        Extract resource data from package.

        Args:
            resource: DBPFResource to extract

        Returns:
            Raw resource data (decompressed if necessary)

        Raises:
            DBPFError: If resource cannot be read
        """
        with open(self.path, "rb") as f:
            # Seek to resource offset
            f.seek(resource.offset)

            # Determine how much to read
            read_size = (
                resource.compressed_size if resource.is_compressed else resource.size
            )

            # Read resource data
            data = f.read(read_size)

            if len(data) < read_size:
                raise DBPFError(
                    f"Could not read complete resource: "
                    f"expected {read_size} bytes, got {len(data)}"
                )

            # Decompress if necessary
            if resource.is_compressed:
                try:
                    # DBPF uses zlib compression
                    data = zlib.decompress(data)

                    if len(data) != resource.size:
                        raise DBPFError(
                            f"Decompressed size mismatch: "
                            f"expected {resource.size}, got {len(data)}"
                        )

                except zlib.error as e:
                    raise DBPFError(f"Failed to decompress resource: {e}") from e

            return data

    def get_resources_by_type(self, type_id: int) -> List[DBPFResource]:
        """
        Get all resources of a specific type.

        Args:
            type_id: Resource type ID (e.g., 0x545238C9 for XML tuning)

        Returns:
            List of matching resources
        """
        if self._resources is None:
            self._resources = self.read_index()

        return [r for r in self._resources if r.type == type_id]

    def get_resource_count(self) -> int:
        """
        Get total number of resources in package.

        Returns:
            Resource count
        """
        if self._header is None:
            self._header = self.read_header()

        return self._header.index_count

    @property
    def resources(self) -> List[DBPFResource]:
        """
        Get all resources (lazy loaded).

        Returns:
            List of all resources in package
        """
        if self._resources is None:
            self._resources = self.read_index()

        return self._resources

    @property
    def header(self) -> DBPFHeader:
        """
        Get header (lazy loaded).

        Returns:
            DBPF header
        """
        if self._header is None:
            self._header = self.read_header()

        return self._header
