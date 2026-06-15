"""Tests for script-family conflict detector."""

from __future__ import annotations

from pathlib import Path

from simanalysis.detectors.script_conflicts import ScriptConflictDetector
from simanalysis.models import ConflictType, Mod, ModType, ScriptModule


def _script_mod(name: str, modules: list[str], file_hash: str | None = None) -> Mod:
    return Mod(
        name=name,
        path=Path("/mods") / name,
        type=ModType.SCRIPT,
        size=1000,
        hash=file_hash,
        scripts=[
            ScriptModule(
                name=module,
                path=module,
                imports=set(),
                hooks=[],
                complexity=1,
            )
            for module in modules
        ],
    )


def test_script_family_conflict_flags_shared_namespace_with_different_archives() -> None:
    detector = ScriptConflictDetector()
    mods = [
        _script_mod("alpha.ts4script", ["shared/core.py"], "hash-alpha"),
        _script_mod("beta.ts4script", ["shared/hooks.py"], "hash-beta"),
    ]

    conflicts = detector.detect(mods)

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.type == ConflictType.NAMESPACE_COLLISION
    assert conflict.details["conflict_kind"] == "script_family_mismatch"
    assert conflict.details["script_family"] == "shared"
    assert conflict.details["executes_code"] is False
    assert conflict.details["recommendation"]["profile_aware"] is True
    assert conflict.details["recommendation"]["action"] == "review_script_family_compatibility"


def test_script_family_conflict_skips_identical_hash_duplicates() -> None:
    detector = ScriptConflictDetector()
    mods = [
        _script_mod("alpha.ts4script", ["shared/core.py"], "same-hash"),
        _script_mod("alpha-copy.ts4script", ["shared/core.py"], "same-hash"),
    ]

    assert detector.detect(mods) == []


def test_script_family_conflict_ignores_single_owner_family() -> None:
    detector = ScriptConflictDetector()
    mods = [
        _script_mod("alpha.ts4script", ["alpha/core.py"], "hash-alpha"),
        _script_mod("beta.ts4script", ["beta/core.py"], "hash-beta"),
    ]

    assert detector.detect(mods) == []
