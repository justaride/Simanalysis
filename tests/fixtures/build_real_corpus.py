"""Populate git-ignored real fixture files from explicit local sources."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.scanners.mod_scanner import ModScanner


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError("Real corpus manifest schema_version must be 1")
    return manifest


def _source_path(source_url: str) -> Path:
    parsed = urlparse(source_url)
    if parsed.scheme != "file":
        raise ValueError(f"Only explicit file:// sources can be copied: {source_url}")
    return Path(unquote(parsed.path))


def _package_golden(package_path: Path) -> dict[str, Any]:
    reader = DBPFReader(package_path)
    header = reader.read_header()
    resources = reader.read_index()
    mod = ModScanner(parse_tunings=True, calculate_hashes=False).scan_file(package_path)

    tunings = []
    if mod is not None:
        tunings = [
            {
                "instance_id": tuning.instance_id,
                "tuning_class": tuning.tuning_class,
                "tuning_name": tuning.tuning_name,
            }
            for tuning in mod.tunings
        ]

    return {
        "header": {
            "magic": header.magic.decode("ascii"),
            "major_version": header.major_version,
            "minor_version": header.minor_version,
            "index_count": header.index_count,
            "index_offset": header.index_offset,
            "index_size": header.index_size,
        },
        "resource_count": len(resources),
        "known_resource_keys": [
            f"0x{resource.type:08X}:0x{resource.group:08X}:0x{resource.instance:016X}"
            for resource in resources
        ],
        "tunings": tunings,
    }


def build_corpus(
    manifest_path: Path,
    local_root: Path,
    source_overrides: dict[str, Path] | None = None,
) -> list[Path]:
    """Copy local-only real fixtures and generate golden sidecars."""
    manifest = _load_manifest(manifest_path)
    overrides = source_overrides or {}
    written: list[Path] = []

    for item in manifest["items"]:
        if item["redistribution"] != "local-only":
            continue

        source = (
            overrides[item["id"]] if item["id"] in overrides else _source_path(item["source_url"])
        )
        target = local_root / item["path"]
        if not source.is_file():
            raise FileNotFoundError(f"Real fixture source not found: {source}")

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        written.append(target)

        if item["kind"] == "package":
            golden_target = local_root / item["golden"]
            golden_target.parent.mkdir(parents=True, exist_ok=True)
            golden_target.write_text(
                json.dumps(_package_golden(target), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            written.append(golden_target)

    return written


def _parse_source_override(value: str) -> tuple[str, Path]:
    item_id, separator, path = value.partition("=")
    if not separator or not item_id or not path:
        raise argparse.ArgumentTypeError("source overrides must look like ITEM_ID=/path/to/file")
    return item_id, Path(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).parent / "real" / "corpus-manifest.json",
    )
    parser.add_argument(
        "--local-root",
        type=Path,
        default=Path(__file__).parent / "local",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        type=_parse_source_override,
        metavar="ITEM_ID=PATH",
        help="Override a local-only manifest source_url with an explicit file path.",
    )
    args = parser.parse_args()

    written = build_corpus(args.manifest, args.local_root, dict(args.source))
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
