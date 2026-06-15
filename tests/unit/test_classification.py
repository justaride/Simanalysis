"""Tests for conservative Sims mod file classification."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

from simanalysis.classification import classify_file, summarize_classifications
from simanalysis.formats.types import BinaryResourceType, TuningResourceType


def _create_package(path: Path, resource_type: int) -> None:
    """Create a tiny Sims 4 DBPF package with one resource."""
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[12:16] = struct.pack("<I", 0)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", 36)
    header[64:68] = struct.pack("<I", 96)

    resource_data = b'<I c="Buff" i="fixture" m="buffs.buff" s="123" />'
    compressed_data = zlib.compress(resource_data)
    resource_offset = 96 + 36

    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", resource_type)
    index += struct.pack("<I", 0x00000000)
    index += struct.pack("<I", 0x00000000)
    index += struct.pack("<I", 0x0000007B)
    index += struct.pack("<I", resource_offset)
    index += struct.pack("<I", len(compressed_data))
    index += struct.pack("<I", len(resource_data))
    index += struct.pack("<H", 0x5A42)
    index += struct.pack("<H", 1)

    path.write_bytes(bytes(header) + bytes(index) + compressed_data)


def test_classify_ts4script_as_script_without_requiring_archive_read(
    tmp_path: Path,
) -> None:
    script = tmp_path / "Helper.ts4script"
    script.write_bytes(b"not a zip")

    result = classify_file(script)

    assert result["label"] == "script"
    assert result["confidence"] == "high"
    assert {signal["id"] for signal in result["signals"]} == {"ts4script_extension"}


def test_classify_dbpf_resource_families(tmp_path: Path) -> None:
    cases = {
        "hair.package": (BinaryResourceType.CasPart, "cas"),
        "chair.package": (BinaryResourceType.ObjectDefinition, "build_buy"),
        "buff.package": (TuningResourceType.Buff, "gameplay_tuning"),
        "ui.package": (TuningResourceType.UserInterfaceInfo, "ui"),
        "strings.package": (BinaryResourceType.StringTable, "localization"),
        "anim.package": (TuningResourceType.Animation, "animation"),
    }

    for file_name, (resource_type, expected_label) in cases.items():
        package = tmp_path / file_name
        _create_package(package, int(resource_type))

        result = classify_file(package)

        assert result["label"] == expected_label
        assert result["confidence"] == "high"
        assert result["resource_type_counts"][0]["count"] == 1
        assert any(signal["id"] == "resource_type" for signal in result["signals"])


def test_resource_evidence_beats_weak_filename_hints(tmp_path: Path) -> None:
    package = tmp_path / "Required Hair Dependency.package"
    _create_package(package, int(BinaryResourceType.CasPart))

    result = classify_file(package)

    assert result["label"] == "cas"
    assert result["confidence"] == "high"
    assert {signal["label"] for signal in result["signals"]} >= {"cas", "dependency"}


def test_weak_filename_hints_are_low_or_medium_confidence(tmp_path: Path) -> None:
    overrides = tmp_path / "Overrides"
    overrides.mkdir()
    default_replacement = overrides / "eye override.package"
    dependency = tmp_path / "required core.package"
    default_replacement.write_bytes(b"not dbpf")
    dependency.write_bytes(b"not dbpf")

    default_result = classify_file(default_replacement)
    dependency_result = classify_file(dependency)

    assert default_result["label"] == "default_replacement"
    assert default_result["confidence"] == "medium"
    assert dependency_result["label"] == "dependency"
    assert dependency_result["confidence"] == "low"


def test_unknown_fallback_does_not_overclaim(tmp_path: Path) -> None:
    text = tmp_path / "readme.txt"
    package = tmp_path / "mystery.package"
    text.write_text("notes", encoding="utf-8")
    package.write_bytes(b"not dbpf")

    assert classify_file(text)["label"] == "unknown"
    package_result = classify_file(package)
    assert package_result["label"] == "unknown"
    assert package_result["confidence"] == "unknown"
    assert any(signal["id"] == "package_parse_error" for signal in package_result["signals"])


def test_summarize_classifications_counts_labels_and_unknowns(tmp_path: Path) -> None:
    _create_package(tmp_path / "hair.package", int(BinaryResourceType.CasPart))
    (tmp_path / "helper.ts4script").write_bytes(b"script")
    (tmp_path / "readme.txt").write_text("notes", encoding="utf-8")

    summary = summarize_classifications(tmp_path)

    assert summary["status"] == "available"
    assert summary["file_count"] == 3
    assert summary["label_counts"] == {"cas": 1, "script": 1, "unknown": 1}
    assert summary["unknown_count"] == 1
    assert summary["automatic_safe_marking"] is False
