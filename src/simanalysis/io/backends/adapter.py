"""Backend factory helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Literal, Optional

from simanalysis.model import ResourceEntry, ResourceKey

from ..dbpf_reader import DBPFReader
from .dummy import DummyDBPFReader


class ExternalCLIReader(DBPFReader):
    """Placeholder reader that proxies to an external CLI tool."""

    def __init__(self, cli_path: Path) -> None:
        cli_path = cli_path.expanduser().resolve()
        if not cli_path.exists():
            raise FileNotFoundError(f"External DBPF CLI not found: {cli_path}")
        if not cli_path.is_file():
            raise ValueError(f"External DBPF CLI must be a file: {cli_path}")
        self.cli_path = cli_path

    def iter_resources(self, package_path: Path) -> Iterator[ResourceEntry]:
        raise NotImplementedError("External CLI backend is not implemented yet")

    def extract_xml(self, package_path: Path, key: ResourceKey) -> Optional[str]:
        raise NotImplementedError("External CLI backend is not implemented yet")


def get_dbpf_reader(
    backend: Literal["dummy", "auto", "external"] = "dummy",
    cli_path: Optional[Path] = None,
) -> DBPFReader:
    """Return a DBPF reader implementation for the requested backend."""

    if backend in {"dummy", "auto"}:
        return DummyDBPFReader()
    if backend == "external":
        if cli_path is None:
            raise ValueError("External backend requires --cli-path")
        return ExternalCLIReader(cli_path)
    raise ValueError(f"Unsupported DBPF backend: {backend}")
