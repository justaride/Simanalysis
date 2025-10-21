"""Placeholder for a real DBPF backend integration."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from simanalysis.model import ResourceEntry, ResourceKey

from ..dbpf_reader import DBPFReader


class RealDBPFReader(DBPFReader):
    """Skeleton for a future native DBPF reader implementation."""

    def __init__(self, tool_path: Path | None = None) -> None:
        if tool_path is not None:
            resolved = tool_path.expanduser().resolve()
            if not resolved.exists():
                raise FileNotFoundError(f"DBPF tool not found: {resolved}")
            if not resolved.is_file():
                raise ValueError(f"DBPF tool must be a file: {resolved}")
            self.tool_path = resolved
        else:
            self.tool_path = None

    def iter_resources(self, package_path: Path) -> Iterator[ResourceEntry]:
        raise NotImplementedError("Real DBPF integration is not yet implemented")

    def extract_xml(self, package_path: Path, key: ResourceKey) -> Optional[str]:
        raise NotImplementedError("Real DBPF integration is not yet implemented")
