from __future__ import annotations

import json
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


def _read_raw_manifest(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict)
    return parsed


@pytest.fixture(autouse=True)
def _allow_file_mutation_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    import simanalysis.operating_table as operating_table

    monkeypatch.setattr(operating_table, "assert_sims_not_running", lambda: None)


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


def test_stage_same_second_operations_preserve_distinct_manifests(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    _write(root / "Mods" / "archive.zip", b"archive")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    first = table.stage_cleanup_plan(
        root,
        _cleanup_plan(root),
        selected_action_ids=["duplicate:1"],
    )
    second = table.stage_cleanup_plan(
        root,
        _cleanup_plan(root),
        selected_action_ids=["inactive_archive:1:Mods/archive.zip"],
    )

    first_path = Path(str(first["manifest_path"]))
    second_path = Path(str(second["manifest_path"]))
    assert first_path == root / "_Simanalysis_Cleanup" / "manifests" / (
        "cleanup-op-20260612-101530.json"
    )
    assert second_path == root / "_Simanalysis_Cleanup" / "manifests" / (
        "cleanup-op-20260612-101530-2.json"
    )
    assert load_manifest(first_path)["actions"][0]["action_id"] == "duplicate:1"
    assert load_manifest(second_path)["actions"][0]["action_id"] == (
        "inactive_archive:1:Mods/archive.zip"
    )


def test_concurrent_same_second_staging_reserves_distinct_manifest_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import threading

    import simanalysis.operating_table as operating_table

    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    _write(root / "Mods" / "archive.zip", b"archive")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")
    barrier = threading.Barrier(2)
    original_unique_manifest_path = operating_table._unique_manifest_path

    def racing_unique_manifest_path(
        manifest_dir: Path,
        base_operation_id: str,
    ) -> tuple[str, Path]:
        result = original_unique_manifest_path(manifest_dir, base_operation_id)
        barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(
        operating_table,
        "_unique_manifest_path",
        racing_unique_manifest_path,
    )
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def stage(action_id: str) -> None:
        try:
            results.append(
                table.stage_cleanup_plan(
                    root,
                    _cleanup_plan(root),
                    selected_action_ids=[action_id],
                )
            )
        except BaseException as exc:  # pragma: no cover - surfaced after thread join
            errors.append(exc)

    threads = [
        threading.Thread(target=stage, args=("duplicate:1",)),
        threading.Thread(target=stage, args=("inactive_archive:1:Mods/archive.zip",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    if errors:
        raise AssertionError("Concurrent staging failed") from errors[0]
    assert len(results) == 2
    manifest_paths = [Path(str(manifest["manifest_path"])) for manifest in results]
    assert {path.name for path in manifest_paths} == {
        "cleanup-op-20260612-101530.json",
        "cleanup-op-20260612-101530-2.json",
    }
    assert {load_manifest(path)["actions"][0]["action_id"] for path in manifest_paths} == {
        "duplicate:1",
        "inactive_archive:1:Mods/archive.zip",
    }


def test_stage_fsyncs_manifest_directory_after_atomic_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    opened_directories: list[Path] = []
    fsynced_fds: list[int] = []
    closed_fds: list[int] = []
    parent_fd = 8675309
    original_open = operating_table.os.open
    original_fsync = operating_table.os.fsync
    original_close = operating_table.os.close

    def fake_open(path: str | Path, flags: int, mode: int = 0o777) -> int:
        path_obj = Path(path)
        if path_obj.is_dir() and flags == operating_table.os.O_RDONLY:
            opened_directories.append(path_obj)
            return parent_fd
        return original_open(path, flags, mode)

    def fake_fsync(fd: int) -> None:
        fsynced_fds.append(fd)
        if fd != parent_fd:
            original_fsync(fd)

    def fake_close(fd: int) -> None:
        closed_fds.append(fd)
        if fd != parent_fd:
            original_close(fd)

    monkeypatch.setattr(operating_table.os, "open", fake_open)
    monkeypatch.setattr(operating_table.os, "fsync", fake_fsync)
    monkeypatch.setattr(operating_table.os, "close", fake_close)
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    manifest = table.stage_cleanup_plan(
        root,
        _cleanup_plan(root),
        selected_action_ids=["duplicate:1"],
    )

    manifest_dir = Path(str(manifest["manifest_path"])).parent
    assert opened_directories == [manifest_dir]
    assert parent_fd in fsynced_fds
    assert parent_fd in closed_fds


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
    manifest_dir = root / "_Simanalysis_Cleanup" / "manifests"
    assert not manifest_dir.exists() or not any(manifest_dir.iterdir())


def test_stage_rejects_malformed_scan_id_without_manifest_reservation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    plan = _cleanup_plan(root)
    plan["scan_id"] = "not-an-int"
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="not-an-int"):
        table.stage_cleanup_plan(root, plan, selected_action_ids=["duplicate:1"])
    manifest_dir = root / "_Simanalysis_Cleanup" / "manifests"
    assert not manifest_dir.exists() or not any(manifest_dir.iterdir())


def test_stage_rejects_symlinked_manifest_directory_without_outside_write(
    tmp_path: Path,
) -> None:
    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    outside = tmp_path / "outside-manifests"
    outside.mkdir()
    cleanup_root = root / "_Simanalysis_Cleanup"
    cleanup_root.mkdir()
    (cleanup_root / "manifests").symlink_to(outside, target_is_directory=True)
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match=r"symlinked.*manifest"):
        table.stage_cleanup_plan(root, _cleanup_plan(root), selected_action_ids=["duplicate:1"])
    assert not any(outside.iterdir())


def test_stage_rejects_symlinked_source(tmp_path: Path) -> None:
    root = tmp_path / "The Sims 4"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "Mods").mkdir(parents=True)
    (root / "Mods" / "B").symlink_to(outside, target_is_directory=True)
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")

    with pytest.raises(ValueError, match="symlinked source"):
        table.stage_cleanup_plan(root, _cleanup_plan(root), selected_action_ids=["duplicate:1"])


def _stage_manifest(tmp_path: Path) -> tuple[OperatingTable, Path, Path]:
    root = tmp_path / "The Sims 4"
    source = _write(root / "Mods" / "B" / "item.package", b"payload")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")
    manifest = table.stage_cleanup_plan(
        root,
        _cleanup_plan(root),
        selected_action_ids=["duplicate:1"],
    )
    return table, Path(str(manifest["manifest_path"])), source


def _stage_two_action_manifest(tmp_path: Path) -> tuple[OperatingTable, Path, Path, Path]:
    root = tmp_path / "The Sims 4"
    package_source = _write(root / "Mods" / "B" / "item.package", b"payload")
    archive_source = _write(root / "Mods" / "archive.zip", b"archive")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")
    manifest = table.stage_cleanup_plan(root, _cleanup_plan(root), all_actions=True)
    return table, Path(str(manifest["manifest_path"])), package_source, archive_source


def test_apply_moves_selected_file_and_updates_manifest(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)

    manifest = table.apply(manifest_path)

    destination = Path(str(manifest["actions"][0]["destination_path"]))
    assert not source.exists()
    assert destination.exists()
    assert destination.read_bytes() == b"payload"
    assert manifest["status"] == "applied"
    assert manifest["actions"][0]["status"] == "moved"
    assert load_manifest(manifest_path)["status"] == "applied"


def test_apply_refuses_running_sims_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    table, manifest_path, source = _stage_manifest(tmp_path)
    monkeypatch.setattr(
        operating_table,
        "assert_sims_not_running",
        lambda: (_ for _ in ()).throw(ValueError("game is running")),
    )

    with pytest.raises(ValueError, match="game is running"):
        table.apply(manifest_path)

    assert source.exists()
    assert load_manifest(manifest_path)["status"] == "planned"


def test_apply_rejects_duplicate_pending_source_paths_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, package_source, archive_source = _stage_two_action_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][1]["source_relative_path"] = manifest["actions"][0]["source_relative_path"]
    manifest["actions"][1]["source_path"] = manifest["actions"][0]["source_path"]
    manifest["actions"][1]["expected"] = dict(manifest["actions"][0]["expected"])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destinations = [Path(str(action["destination_path"])) for action in manifest["actions"]]

    with pytest.raises(ValueError, match="Duplicate cleanup action source path"):
        table.apply(manifest_path)

    assert package_source.exists()
    assert archive_source.exists()
    assert all(not destination.exists() for destination in destinations)
    assert _read_raw_manifest(manifest_path) == before


def test_apply_rejects_duplicate_pending_destination_paths_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, package_source, archive_source = _stage_two_action_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][1]["destination_relative_path"] = manifest["actions"][0][
        "destination_relative_path"
    ]
    manifest["actions"][1]["destination_path"] = manifest["actions"][0]["destination_path"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))

    with pytest.raises(ValueError, match="Duplicate cleanup action destination path"):
        table.apply(manifest_path)

    assert package_source.exists()
    assert archive_source.exists()
    assert not destination.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_apply_refuses_hash_mismatch_without_moving(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    source.write_bytes(b"changed")

    with pytest.raises(ValueError, match="no longer matches cleanup plan evidence"):
        table.apply(manifest_path)

    assert source.exists()
    assert load_manifest(manifest_path)["status"] == "planned"


def test_apply_preflight_blocks_destination_collision_before_any_move(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))
    _write(destination, b"collision")

    with pytest.raises(ValueError, match="Destination already exists"):
        table.apply(manifest_path)

    assert source.exists()
    assert destination.read_bytes() == b"collision"
    assert load_manifest(manifest_path)["status"] == "planned"


def test_apply_rejects_symlinked_destination_component_race_without_outside_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))
    operation_dir = (
        Path(str(manifest["root_path"])) / "_Simanalysis_Cleanup" / "cleanup-20260612-101400"
    )
    outside = tmp_path / "outside-target"
    outside.mkdir()
    original_mkdir = operating_table.Path.mkdir
    raced = False

    def racing_mkdir(
        self: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        nonlocal raced
        if self == operation_dir and not raced:
            raced = True
            self.symlink_to(outside, target_is_directory=True)
        original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(operating_table.Path, "mkdir", racing_mkdir)

    with pytest.raises(ValueError, match="symlinked destination"):
        table.apply(manifest_path)

    assert raced
    assert source.exists()
    assert not destination.exists()
    assert not any(outside.rglob("*"))


def test_apply_records_partial_progress_when_later_move_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    root = tmp_path / "The Sims 4"
    _write(root / "Mods" / "B" / "item.package", b"payload")
    _write(root / "Mods" / "archive.zip", b"archive")
    table = OperatingTable(clock=lambda: "2026-06-12T10:15:30Z")
    staged = table.stage_cleanup_plan(root, _cleanup_plan(root), all_actions=True)
    manifest_path = Path(str(staged["manifest_path"]))
    first_destination = Path(str(staged["actions"][0]["destination_path"]))
    original_move = operating_table.shutil.move

    def fail_second_move(source: str, destination: str) -> str:
        if source.endswith("archive.zip"):
            raise OSError("move exploded")
        return original_move(source, destination)

    monkeypatch.setattr(operating_table.shutil, "move", fail_second_move)

    with pytest.raises(OSError, match="move exploded"):
        table.apply(manifest_path)

    saved = load_manifest(manifest_path)
    assert saved["status"] == "partial"
    assert saved["actions"][0]["status"] == "moved"
    assert saved["actions"][1]["status"] == "blocked"
    assert first_destination.exists()


def test_apply_keeps_action_restorable_when_persisting_moved_state_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import copy

    import simanalysis.operating_table as operating_table

    table, manifest_path, source = _stage_manifest(tmp_path)
    staged = load_manifest(manifest_path)
    destination = Path(str(staged["actions"][0]["destination_path"]))
    original_save_manifest = operating_table._save_manifest
    snapshots: list[dict[str, Any]] = []

    def fail_after_physical_move(manifest: dict[str, Any]) -> dict[str, Any]:
        snapshots.append(copy.deepcopy(manifest))
        if not source.exists() and destination.exists():
            raise OSError("manifest write failed after move")
        return original_save_manifest(manifest)

    monkeypatch.setattr(operating_table, "_save_manifest", fail_after_physical_move)

    with pytest.raises(OSError, match="manifest write failed after move"):
        table.apply(manifest_path)

    assert not source.exists()
    assert destination.exists()
    assert snapshots[-1]["actions"][0]["status"] in {
        "moving",
        "moved",
        "restore_pending",
        "restoring",
    }
    saved = load_manifest(manifest_path)
    assert saved["actions"][0]["status"] in {"moving", "moved", "restore_pending"}


def test_apply_rejects_invalid_action_status_before_any_move(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][0]["status"] = "surprise"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))

    with pytest.raises(ValueError, match="Unsupported cleanup action status"):
        table.apply(manifest_path)

    assert source.exists()
    assert not destination.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_apply_rejects_non_string_manifest_status_before_any_move(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["status"] = ["planned"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))

    with pytest.raises(ValueError, match="Cleanup operation status must be a string"):
        table.apply(manifest_path)

    assert source.exists()
    assert not destination.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_apply_rejects_non_string_action_status_before_any_move(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][0]["status"] = ["pending"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))

    with pytest.raises(ValueError, match="Cleanup action status must be a string"):
        table.apply(manifest_path)

    assert source.exists()
    assert not destination.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_apply_rejects_destination_relative_path_mismatch_before_any_move(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][0]["destination_relative_path"] = (
        "_Simanalysis_Cleanup/other-op/duplicates/Mods/B/item.package"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))

    with pytest.raises(ValueError, match="Destination path does not match relative path"):
        table.apply(manifest_path)

    assert source.exists()
    assert not destination.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_restore_moves_file_back_from_manifest(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    destination = Path(str(applied["actions"][0]["destination_path"]))

    restored = table.restore(manifest_path)

    assert source.exists()
    assert source.read_bytes() == b"payload"
    assert not destination.exists()
    assert restored["status"] == "restored"
    assert restored["actions"][0]["status"] == "restored"


def test_restore_refuses_destination_collision_and_preserves_state(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    destination = Path(str(applied["actions"][0]["destination_path"]))
    source.write_bytes(b"collision")

    with pytest.raises(ValueError, match="Restore destination already exists"):
        table.restore(manifest_path)

    saved = load_manifest(manifest_path)
    assert saved["status"] == "blocked"
    assert saved["actions"][0]["status"] == "blocked"
    assert source.read_bytes() == b"collision"
    assert destination.read_bytes() == b"payload"


def test_restore_refuses_running_sims_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    destination = Path(str(applied["actions"][0]["destination_path"]))
    monkeypatch.setattr(
        operating_table,
        "assert_sims_not_running",
        lambda: (_ for _ in ()).throw(ValueError("game is running")),
    )

    with pytest.raises(ValueError, match="game is running"):
        table.restore(manifest_path)

    assert destination.exists()
    assert not source.exists()
    assert load_manifest(manifest_path)["status"] == "applied"


def test_stage_apply_restore_returns_mods_to_original_file_set(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    mods = source.parents[1]
    before = sorted(path.relative_to(mods) for path in mods.rglob("*") if path.is_file())

    table.apply(manifest_path)
    table.restore(manifest_path)

    after = sorted(path.relative_to(mods) for path in mods.rglob("*") if path.is_file())
    assert after == before


def test_restore_runs_restorable_actions_in_reverse_manifest_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    table, manifest_path, _package_source, _archive_source = _stage_two_action_manifest(tmp_path)
    applied = table.apply(manifest_path)
    restore_sources = [Path(str(action["destination_path"])) for action in applied["actions"]]
    original_move = operating_table.shutil.move
    moved_sources: list[Path] = []

    def recording_move(source: str, destination: str) -> str:
        moved_sources.append(Path(source))
        return original_move(source, destination)

    monkeypatch.setattr(operating_table.shutil, "move", recording_move)

    table.restore(manifest_path)

    assert moved_sources == list(reversed(restore_sources))


def test_restore_rejects_duplicate_restorable_source_paths_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, package_source, archive_source = _stage_two_action_manifest(tmp_path)
    applied = table.apply(manifest_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][1]["destination_relative_path"] = manifest["actions"][0][
        "destination_relative_path"
    ]
    manifest["actions"][1]["destination_path"] = manifest["actions"][0]["destination_path"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    cleanup_sources = [Path(str(action["destination_path"])) for action in applied["actions"]]

    with pytest.raises(ValueError, match="Duplicate cleanup action restore source path"):
        table.restore(manifest_path)

    assert not package_source.exists()
    assert not archive_source.exists()
    assert all(path.exists() for path in cleanup_sources)
    assert _read_raw_manifest(manifest_path) == before


def test_restore_rejects_duplicate_restorable_destination_paths_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, package_source, archive_source = _stage_two_action_manifest(tmp_path)
    applied = table.apply(manifest_path)
    manifest = load_manifest(manifest_path)
    manifest["actions"][1]["source_relative_path"] = manifest["actions"][0]["source_relative_path"]
    manifest["actions"][1]["source_path"] = manifest["actions"][0]["source_path"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)
    cleanup_sources = [Path(str(action["destination_path"])) for action in applied["actions"]]

    with pytest.raises(ValueError, match="Duplicate cleanup action restore destination path"):
        table.restore(manifest_path)

    assert not package_source.exists()
    assert not archive_source.exists()
    assert all(path.exists() for path in cleanup_sources)
    assert _read_raw_manifest(manifest_path) == before


def test_restore_rejects_symlinked_mods_component_without_outside_write(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    cleanup_source = Path(str(applied["actions"][0]["destination_path"]))
    outside = tmp_path / "outside-target"
    outside.mkdir()
    source.parent.rmdir()
    source.parent.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked restore destination"):
        table.restore(manifest_path)

    assert cleanup_source.exists()
    assert not (outside / source.name).exists()


def test_restore_rejects_destination_outside_sims_root_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    cleanup_source = Path(str(applied["actions"][0]["destination_path"]))
    manifest = load_manifest(manifest_path)
    outside_destination = tmp_path / "outside-root" / "item.package"
    manifest["actions"][0]["source_relative_path"] = "../outside-root/item.package"
    manifest["actions"][0]["source_path"] = str(outside_destination)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)

    with pytest.raises(ValueError, match="Cleanup source must be under Mods"):
        table.restore(manifest_path)

    assert not source.exists()
    assert cleanup_source.exists()
    assert not outside_destination.parent.exists()
    assert _read_raw_manifest(manifest_path) == before


def test_restore_rejects_non_string_action_status_before_any_mutation(
    tmp_path: Path,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    cleanup_source = Path(str(applied["actions"][0]["destination_path"]))
    manifest = load_manifest(manifest_path)
    manifest["actions"][0]["status"] = ["moved"]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    before = _read_raw_manifest(manifest_path)

    with pytest.raises(ValueError, match="Cleanup action status must be a string"):
        table.restore(manifest_path)

    assert not source.exists()
    assert cleanup_source.exists()
    assert _read_raw_manifest(manifest_path) == before


@pytest.mark.parametrize("recoverable_status", ["moving", "restore_pending"])
def test_restore_recovers_apply_persistence_states_when_cleanup_file_exists(
    tmp_path: Path,
    recoverable_status: str,
) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    cleanup_source = Path(str(applied["actions"][0]["destination_path"]))
    manifest = load_manifest(manifest_path)
    manifest["status"] = "partial"
    manifest["actions"][0]["status"] = recoverable_status
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    restored = table.restore(manifest_path)

    assert source.exists()
    assert source.read_bytes() == b"payload"
    assert not cleanup_source.exists()
    assert restored["status"] == "restored"
    assert restored["actions"][0]["status"] == "restored"


def test_restore_does_not_mark_action_blocked_when_persisting_after_move_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import simanalysis.operating_table as operating_table

    table, manifest_path, source = _stage_manifest(tmp_path)
    applied = table.apply(manifest_path)
    cleanup_source = Path(str(applied["actions"][0]["destination_path"]))
    original_save_manifest = operating_table._save_manifest

    def fail_after_physical_restore(manifest: dict[str, Any]) -> dict[str, Any]:
        if source.exists() and not cleanup_source.exists():
            raise OSError("manifest write failed after restore")
        return original_save_manifest(manifest)

    monkeypatch.setattr(operating_table, "_save_manifest", fail_after_physical_restore)

    with pytest.raises(OSError, match="manifest write failed after restore"):
        table.restore(manifest_path)

    assert source.exists()
    assert not cleanup_source.exists()
    saved = load_manifest(manifest_path)
    assert saved["status"] != "blocked"
    assert saved["actions"][0]["status"] != "blocked"
