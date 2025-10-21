from __future__ import annotations

from pathlib import Path

import pytest

from simanalysis.model import (
    PackageIndex,
    ResourceEntry,
    ResourceKey,
    TuningNode,
    normalize_tuning_id,
)


def test_resource_key_str_and_from_hex() -> None:
    key = ResourceKey(type_id=0x1A2B3C4D, group_id=0x0, instance_id=0x89ABCDEF)
    assert str(key) == "1A2B3C4D:00000000:89ABCDEF"

    parsed = ResourceKey.from_hex("1A2B3C4D:00000000:89ABCDEF")
    assert parsed == key


def test_resource_key_from_hex_invalid() -> None:
    with pytest.raises(ValueError):
        ResourceKey.from_hex("bad-format")


def test_immutable_models() -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    entry = ResourceEntry(key=key, resource_type="xml", size=42, path_in_package="foo.xml")
    index = PackageIndex(package_path=Path("/mods/foo.package"), entries=[entry], sha256="deadbeef")
    node = TuningNode(
        tuning_id="example",
        tuning_type="Interaction",
        references={"other"},
        raw_xml='<I n="example" />',
    )

    with pytest.raises(TypeError):
        object.__setattr__(key, "type_id", 99)
    with pytest.raises(TypeError):
        object.__setattr__(entry, "size", 99)
    with pytest.raises(TypeError):
        object.__setattr__(index, "sha256", "beef")
    with pytest.raises(TypeError):
        object.__setattr__(node, "tuning_id", "changed")


def test_normalize_tuning_id() -> None:
    assert normalize_tuning_id("  My_Tuning  Id ") == "my_tuningid"
