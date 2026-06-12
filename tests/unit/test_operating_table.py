from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from simanalysis.operating_table import OperatingTable, load_manifest


def _write(path: Path, body: bytes = b"payload") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _sha256_hex(body: bytes) -> str:
    import hashlib

    return hashlib.sha256(body).hexdigest()


def _cleanup_plan(root: Path, body: bytes = b"payload") -> dict[str, Any]:
    sha = _sha256_hex(body)
    return {
        "version": 1,
        "plan_id": "cleanup-20260612-101400",
        "created_at": "2026-06-12T10:14:00Z",
        "root_path": str(root),
        "mods_path": str(root / "Mods"),
        "scan_id": 42,
        "summary": {"action_count": 2},
        "warnings": [],
        "findings": [
            {
                "finding_id": "duplicate:sha256:" + sha,
                "category": "exact_duplicate",
                "severity": "review",
                "title": "Exact duplicate files",
                "explanation": "These files have identical SHA-256 and size in Mods.",
                "evidence": {
                    "sha256": sha,
                    "size": len(body),
                    "paths": ["Mods/A/item.package", "Mods/B/item.package"],
                    "keep_candidate": "Mods/A/item.package",
                },
                "actions": [
                    {
                        "action_id": "duplicate:1",
                        "kind": "review_duplicate",
                        "source_relative_path": "Mods/B/item.package",
                        "proposed_destination": (
                            "_Simanalysis_Cleanup/cleanup-20260612-101400/"
                            "duplicates/Mods/B/item.package"
                        ),
                        "reason": "Exact duplicate of Mods/A/item.package",
                    }
                ],
            },
            {
                "finding_id": "inactive_archive:Mods/archive.zip",
                "category": "inactive_archive",
                "severity": "review",
                "title": "Archive file inside Mods",
                "explanation": "The Sims 4 does not load this archive directly from Mods.",
                "evidence": {
                    "path": "Mods/archive.zip",
                    "extension": ".zip",
                    "sha256": _sha256_hex(b"archive"),
                    "size": 7,
                },
                "actions": [
                    {
                        "action_id": "inactive_archive:1:Mods/archive.zip",
                        "kind": "review_archive",
                        "source_relative_path": "Mods/archive.zip",
                        "proposed_destination": (
                            "_Simanalysis_Cleanup/cleanup-20260612-101400/archives/Mods/archive.zip"
                        ),
                        "reason": "The Sims 4 does not load this archive directly from Mods.",
                    }
                ],
            },
        ],
    }


def test_stage_selected_action_writes_manifest_without_moving_source(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    source = _write(root / "Mods" / "B" / "item.package", b"payload")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    manifest = table.stage_cleanup_plan(
        root,
        _cleanup_plan(root),
        selected_action_ids=["duplicate:1"],
    )

    manifest_path = Path(str(manifest["manifest_path"]))
    assert manifest_path == root / "_Simanalysis_Cleanup" / "manifests" / (
        "cleanup-op-20260612-101530.json"
    )
    assert manifest_path.exists()
    assert source.exists()
    assert not (
        root
        / "_Simanalysis_Cleanup"
        / "cleanup-20260612-101400"
        / "duplicates"
        / "Mods"
        / "B"
        / "item.package"
    ).exists()
    assert manifest["status"] == "planned"
    assert manifest["source_plan"] == {
        "version": 1,
        "plan_id": "cleanup-20260612-101400",
        "scan_id": 42,
        "created_at": "2026-06-12T10:14:00Z",
    }
    assert manifest["actions"][0]["finding_id"].startswith("duplicate:sha256:")
    assert manifest["actions"][0]["expected"]["sha256"] == _sha256_hex(b"payload")
    assert manifest["actions"][0]["expected"]["size"] == 7
    assert manifest["actions"][0]["expected"]["keep_candidate"] == "Mods/A/item.package"
    assert load_manifest(manifest_path)["operation_id"] == "cleanup-op-20260612-101530"


def test_stage_requires_explicit_action_selection(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    root.mkdir()
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="Choose at least one cleanup action"):
        table.stage_cleanup_plan(root, _cleanup_plan(root))


def test_stage_all_actions_requires_explicit_flag(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    _write(root / "Mods" / "archive.zip", b"archive")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    manifest = table.stage_cleanup_plan(root, _cleanup_plan(root), all_actions=True)

    assert [action["action_id"] for action in manifest["actions"]] == [
        "duplicate:1",
        "inactive_archive:1:Mods/archive.zip",
    ]


def test_stage_rejects_unknown_and_duplicate_action_ids(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    root.mkdir()
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="Unknown cleanup action"):
        table.stage_cleanup_plan(root, _cleanup_plan(root), selected_action_ids=["missing"])

    with pytest.raises(ValueError, match="Duplicate cleanup action"):
        table.stage_cleanup_plan(
            root,
            _cleanup_plan(root),
            selected_action_ids=["duplicate:1", "duplicate:1"],
        )


def test_stage_rejects_destination_outside_cleanup_root(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    root.mkdir()
    plan = _cleanup_plan(root)
    plan["findings"][0]["actions"][0]["proposed_destination"] = "../escape.package"
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="destination must be under _Simanalysis_Cleanup"):
        table.stage_cleanup_plan(root, plan, selected_action_ids=["duplicate:1"])


def test_stage_rejects_symlinked_source(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "Mods").mkdir(parents=True)
    (root / "Mods" / "B").symlink_to(outside, target_is_directory=True)
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="symlinked source"):
        table.stage_cleanup_plan(root, _cleanup_plan(root), selected_action_ids=["duplicate:1"])
