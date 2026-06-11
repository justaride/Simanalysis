"""Contract tests for the real-file fixture corpus."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.scanners.mod_scanner import ModScanner

REAL_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "real"
LOCAL_FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "local"
MANIFEST_PATH = REAL_FIXTURES_DIR / "corpus-manifest.json"


def _manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def _fixture_path(item: dict[str, Any]) -> Path:
    root = LOCAL_FIXTURES_DIR if item["redistribution"] == "local-only" else REAL_FIXTURES_DIR
    return root / item["path"]


def _golden_path(item: dict[str, Any]) -> Path:
    root = LOCAL_FIXTURES_DIR if item["redistribution"] == "local-only" else REAL_FIXTURES_DIR
    return root / item["golden"]


@pytest.mark.real
def test_real_corpus_manifest_is_well_formed_and_documented() -> None:
    """The real corpus must declare provenance before any file becomes a test source."""
    assert (REAL_FIXTURES_DIR / "README.md").is_file()

    manifest = _manifest()
    assert manifest["schema_version"] == 1
    assert isinstance(manifest["items"], list)

    seen_ids: set[str] = set()
    for item in manifest["items"]:
        assert item["id"] not in seen_ids
        seen_ids.add(item["id"])
        assert item["kind"] in {
            "package",
            "ts4script",
            "last_exception",
            "save",
            "tray",
        }
        assert item["redistribution"] in {"committed", "local-only"}
        assert item["license"]
        assert item["source_url"]
        assert item["path"]

        if item["kind"] == "package":
            assert item.get("golden"), f"{item['id']} is missing a golden sidecar"


@pytest.mark.real
def test_real_package_goldens_match_available_files() -> None:
    """Available real packages must match their golden DBPF metadata."""
    package_items = [item for item in _manifest()["items"] if item["kind"] == "package"]
    if not package_items:
        pytest.skip("No real package fixtures declared yet")

    checked = 0
    for item in package_items:
        package_path = _fixture_path(item)
        if not package_path.exists():
            if item["redistribution"] == "committed":
                pytest.fail(f"Committed real package fixture is missing: {package_path}")
            continue

        golden_path = _golden_path(item)
        if not golden_path.exists():
            pytest.fail(f"Golden sidecar is missing for {item['id']}: {golden_path}")
        with golden_path.open(encoding="utf-8") as handle:
            golden = json.load(handle)

        reader = DBPFReader(package_path)
        header = reader.read_header()
        resources = reader.read_index()

        assert header.index_count == golden["header"]["index_count"]
        assert len(resources) == golden["resource_count"]
        assert {
            f"0x{resource.type:08X}:0x{resource.group:08X}:0x{resource.instance:016X}"
            for resource in resources
        }.issuperset(golden["known_resource_keys"])
        checked += 1

    if checked == 0:
        pytest.skip("Declared real package fixtures are local-only or not installed")


@pytest.mark.real
def test_real_tuning_package_extracts_nonzero_tunings() -> None:
    """A real tuning package must prove tuning extraction is not circular."""
    tuning_items = [
        item
        for item in _manifest()["items"]
        if item["kind"] == "package" and "tuning_mod" in item.get("roles", [])
    ]
    if not tuning_items:
        pytest.fail("Real corpus must declare at least one tuning_mod package")

    for item in tuning_items:
        package_path = _fixture_path(item)
        if not package_path.exists():
            if item["redistribution"] == "committed":
                pytest.fail(f"Committed tuning package fixture is missing: {package_path}")
            continue

        mod = ModScanner(parse_tunings=True, calculate_hashes=False).scan_file(package_path)
        assert mod is not None
        assert mod.tunings, f"{item['id']} extracted zero tunings"
        golden_path = _golden_path(item)
        if golden_path.exists():
            golden = json.loads(golden_path.read_text(encoding="utf-8"))
            assert [
                {
                    "instance_id": tuning.instance_id,
                    "tuning_class": tuning.tuning_class,
                    "tuning_name": tuning.tuning_name,
                }
                for tuning in mod.tunings
            ] == golden["tunings"]
        return

    pytest.skip("Declared real tuning package is local-only or not installed")
