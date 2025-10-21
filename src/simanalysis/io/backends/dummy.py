"""Dummy backend for DBPF reading."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

from simanalysis.model import ResourceEntry, ResourceKey

from ..dbpf_reader import DBPFReader

LOGGER = logging.getLogger(__name__)


class DummyDBPFReader(DBPFReader):
    """No-op DBPF reader that returns no resources."""

    def iter_resources(self, package_path: Path) -> Iterator[ResourceEntry]:
        LOGGER.warning("Using dummy DBPF reader for %s", package_path)
        return iter(())

    def extract_xml(self, package_path: Path, key: ResourceKey) -> Optional[str]:
        LOGGER.warning("Dummy DBPF reader cannot extract XML for %s in %s", key, package_path)
        return None
