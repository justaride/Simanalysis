"""Tests for the real-corpus fixture builder."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

from simanalysis.formats.types import TuningResourceType
from tests.fixtures import build_real_corpus

pytestmark = pytest.mark.synthetic


def _write_tuning_package(path: Path) -> None:
    tuning_xml = b"""<?xml version="1.0" encoding="utf-8"?>
    <I c="Buff" i="buff_fixture" m="buffs.buff" s="98765">
        <T n="mood_weight">10</T>
    </I>
    """
    compressed = zlib.compress(tuning_xml)
    index_size = 4 + 32
    resource_offset = 96 + index_size

    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 0)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", index_size)
    header[64:68] = struct.pack("<I", 96)

    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", int(TuningResourceType.Buff))
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 98765)
    index += struct.pack("<I", resource_offset)
    index += struct.pack("<I", len(compressed))
    index += struct.pack("<I", len(tuning_xml))
    index += struct.pack("<H", 0x5A42)
    index += struct.pack("<H", 1)

    path.write_bytes(header + index + compressed)


def test_builder_copies_local_package_and_writes_golden_sidecar(tmp_path: Path) -> None:
    """Builder copies a selected real package and records parser-verifiable goldens."""
    source_dir = tmp_path / "source with spaces"
    source_dir.mkdir()
    source = source_dir / "source package.package"
    _write_tuning_package(source)

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "items": [
                    {
                        "id": "local_tuning_mod",
                        "kind": "package",
                        "path": "packages/local_tuning_mod.package",
                        "roles": ["tuning_mod"],
                        "redistribution": "local-only",
                        "license": "not-for-redistribution",
                        "source_url": "local://packages/local_tuning_mod.package",
                        "golden": "golden/local_tuning_mod.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    local_root = tmp_path / "local"
    build_real_corpus.build_corpus(
        manifest,
        local_root,
        source_overrides={"local_tuning_mod": source},
    )

    copied = local_root / "packages" / "local_tuning_mod.package"
    golden = local_root / "golden" / "local_tuning_mod.json"

    assert copied.read_bytes() == source.read_bytes()
    golden_data = json.loads(golden.read_text(encoding="utf-8"))
    assert golden_data["header"]["index_count"] == 1
    assert golden_data["resource_count"] == 1
    assert golden_data["known_resource_keys"] == [
        f"0x{int(TuningResourceType.Buff):08X}:0x00000000:0x00000000000181CD"
    ]
    assert golden_data["tunings"] == [
        {
            "instance_id": 98765,
            "tuning_class": "Buff",
            "tuning_name": "buff_fixture",
        }
    ]
