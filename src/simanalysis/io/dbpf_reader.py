"""DBPF reader abstractions."""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Iterator, Optional

from simanalysis.model import ResourceEntry, ResourceKey


class DBPFReader(abc.ABC):
    """Abstract interface for reading DBPF package contents."""

    @abc.abstractmethod
    def iter_resources(self, package_path: Path) -> Iterator[ResourceEntry]:
        """Yield :class:`ResourceEntry` records for ``package_path``."""

    @abc.abstractmethod
    def extract_xml(self, package_path: Path, key: ResourceKey) -> Optional[str]:
        """Return the XML payload for ``key`` inside ``package_path`` if available."""
