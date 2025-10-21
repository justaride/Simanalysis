from __future__ import annotations

import hashlib
import logging
import sys
import zlib
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from simanalysis.io import get_dbpf_reader
from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey

LOGGER = logging.getLogger(__name__)


def _compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _loose_file_entry(path: Path, resource_type: str) -> ResourceEntry:
    crc = zlib.crc32(path.as_posix().encode("utf-8")) & 0xFFFFFFFF
    key = ResourceKey(type_id=0, group_id=0, instance_id=crc)
    size = path.stat().st_size
    return ResourceEntry(key=key, resource_type=resource_type, size=size, path_in_package=path.name)


def scan_mods_dir(
    path: Path, dbpf_backend: str = "dummy", cli_path: Path | None = None
) -> list[PackageIndex]:
    """Scan ``path`` for mods and build lightweight indexes."""

    if not path.exists():
        raise FileNotFoundError(f"Mods directory not found: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Mods path must be a directory: {path}")

    reader = get_dbpf_reader(dbpf_backend, cli_path=cli_path)
    package_indexes: list[PackageIndex] = []

    files = sorted(p for p in path.rglob("*") if p.is_file())
    if not files:
        LOGGER.info("No files found under %s", path)
        return package_indexes

    disable_progress = not sys.stderr.isatty()
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        transient=True,
        disable=disable_progress,
    ) as progress:
        task_id = progress.add_task("Scanning mods", total=len(files))
        for file_path in files:
            LOGGER.debug("Indexing file %s", file_path)
            suffix = file_path.suffix.lower()
            if suffix == ".package":
                entries = list(reader.iter_resources(file_path))
            elif suffix in {".xml", ".py"}:
                resource_type = suffix.lstrip(".")
                entries = [_loose_file_entry(file_path, resource_type)]
            else:
                progress.advance(task_id)
                continue

            package_indexes.append(
                PackageIndex(
                    package_path=file_path,
                    entries=entries,
                    sha256=_compute_sha256(file_path),
                )
            )
            progress.advance(task_id)

    return package_indexes
