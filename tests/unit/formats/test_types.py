import json
from pathlib import Path

from simanalysis.formats.types import (
    BINARY_TYPE_IDS,
    COBJ,
    OBJD,
    SIMDATA,
    STBL,
    TUNING_GENERIC,
    TUNING_TYPE_IDS,
    BinaryResourceType,
    TuningResourceType,
    is_tuning_type,
    type_name,
)

SNAPSHOT = Path(__file__).parents[2] / "fixtures" / "s4tk_resource_types_snapshot.json"
HALLUCINATED_TYPES = {
    int("545238" + "C9", 16),
    int("545503" + "B2", 16),
    int("627665" + "56", 16),
}
FONT_CONFIG = int("033340" + "6C", 16)


def _snapshot() -> dict[str, dict[str, str]]:
    with SNAPSHOT.open(encoding="utf-8") as handle:
        return json.load(handle)


def test_tuning_registry_matches_s4tk_snapshot() -> None:
    tuning = _snapshot()["tuning"]

    assert {item.name: f"0x{int(item):08X}" for item in TuningResourceType} == tuning
    assert frozenset(int(value, 16) for value in tuning.values()) == TUNING_TYPE_IDS
    assert len(TUNING_TYPE_IDS) == len(tuning)


def test_binary_registry_matches_s4tk_snapshot() -> None:
    binary = _snapshot()["binary"]

    assert {item.name: f"0x{int(item):08X}" for item in BinaryResourceType} == binary
    assert frozenset(int(value, 16) for value in binary.values()) == BINARY_TYPE_IDS


def test_core_resource_aliases_use_verified_values() -> None:
    assert int(TUNING_GENERIC) == 0x03B33DDF
    assert int(SIMDATA) == 0x545AC67A
    assert int(STBL) == 0x220557DA
    assert int(OBJD) == 0xC0DB5AE7
    assert int(COBJ) == 0x319E4F1D


def test_tuning_helper_includes_real_tuning_and_excludes_binary_resources() -> None:
    assert is_tuning_type(TuningResourceType.Buff)
    assert is_tuning_type(0x6017E896)
    assert is_tuning_type(0xB61DE6B4)
    assert not is_tuning_type(BinaryResourceType.StringTable)
    assert not is_tuning_type(0x220557DA)
    assert not is_tuning_type(BinaryResourceType.SimData)


def test_type_name_uses_registry_display_names() -> None:
    assert type_name(0x545AC67A) == "SimData"
    assert type_name(0xC0DB5AE7) == "Object Definition"
    assert type_name(0x034AEECB) == "CAS Part"
    assert type_name(0x6017E896) == "Buff Tuning"
    assert type_name(0xDEADBEEF) == "Unknown"


def test_hallucinated_resource_types_are_not_registered() -> None:
    registered = TUNING_TYPE_IDS | BINARY_TYPE_IDS

    assert HALLUCINATED_TYPES.isdisjoint(registered)
    assert FONT_CONFIG not in registered
