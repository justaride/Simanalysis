# Operating Table v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first general manifest-first cleanup apply/restore engine for Simanalysis, starting from Cleanup Planner v1 actions.

**Architecture:** Add a focused `simanalysis.operating_table` service that stages selected cleanup-plan actions into an operation manifest, applies selected file moves into `_Simanalysis_Cleanup`, and restores from that manifest. Expose it through bridge commands first, then add thin Tauri/web argument wrappers without adding a visual cleanup route.

**Tech Stack:** Python 3.11, pytest, Ruff, MyPy, existing NDJSON bridge, Rust/Tauri argument builder tests, Node built-in test runner for web API model helpers.

---

## File Map

- Create `src/simanalysis/operating_table.py`
  - Owns manifest staging, validation, apply, restore, status loading, atomic writes, source hashing, and path guards.
  - Reuses `simanalysis.treatment.assert_sims_not_running` for mutation guard.
- Create `tests/unit/test_operating_table.py`
  - Covers staging, safety validation, apply, partial apply, restore, and synthetic end-to-end behavior.
- Modify `src/simanalysis/bridge/__init__.py`
  - Adds `cleanup-stage`, `cleanup-apply`, `cleanup-restore`, and `cleanup-status` parsers.
- Modify `src/simanalysis/bridge/commands.py`
  - Dispatches bridge commands to `OperatingTable`.
- Modify `tests/unit/test_bridge_main.py`
  - Adds parser/dispatch tests for the four bridge commands.
- Modify `tests/unit/test_bridge_commands.py`
  - Adds command handler tests with monkeypatched `OperatingTable`.
- Modify `src-tauri/src/lib.rs`
  - Adds non-visual argument plumbing for the four cleanup operation commands.
- Create `web/src/operatingTableApiModel.js`
  - Builds options for cleanup staging.
- Create `web/src/operatingTableApiModel.test.js`
  - Covers default, selected-action, all-action, and plan-path options.
- Modify `web/src/api.js`
  - Adds `cleanupStage`, `cleanupApply`, `cleanupRestore`, and `cleanupStatus` wrappers.
- Modify `CHANGELOG.md`, `IMPLEMENTATION_STATUS.md`, and `docs/STATUS.md`
  - Marks Operating Table v1 implementation progress once verified.

## Manifest Contract

The service should produce manifests shaped like the approved spec:

```json
{
  "version": 1,
  "operation_id": "cleanup-op-20260612-101530",
  "created_at": "2026-06-12T10:15:30Z",
  "updated_at": "2026-06-12T10:15:30Z",
  "root_path": "/Sims/The Sims 4",
  "mods_path": "/Sims/The Sims 4/Mods",
  "source_plan": {
    "version": 1,
    "plan_id": "cleanup-20260612-101400",
    "scan_id": 42,
    "created_at": "2026-06-12T10:14:00Z"
  },
  "manifest_path": "/Sims/The Sims 4/_Simanalysis_Cleanup/manifests/cleanup-op-20260612-101530.json",
  "status": "planned",
  "actions": [],
  "warnings": [],
  "blockers": []
}
```

Valid action kinds in v1:

```python
{
    "review_duplicate",
    "review_archive",
    "review_resource_cfg",
    "review_support_file",
    "review_misplaced_tray",
}
```

Use these command groups while executing:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
COVERAGE_FILE=/tmp/simanalysis-operating-table-bridge.coverage .venv/bin/python -m pytest tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/ruff check src/simanalysis/operating_table.py tests/unit/test_operating_table.py src/simanalysis/bridge tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
.venv/bin/ruff format --check src/simanalysis/operating_table.py tests/unit/test_operating_table.py src/simanalysis/bridge tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
.venv/bin/mypy src
cargo test --manifest-path src-tauri/Cargo.toml
node --test web/src/operatingTableApiModel.test.js web/src/cleanupApiModel.test.js web/src/inventoryApiModel.test.js web/src/liveMonitorModel.test.js
npm --prefix web run lint
npm --prefix web run build
```

---

### Task 1: Stage Cleanup Actions Into A Manifest

**Files:**
- Create: `src/simanalysis/operating_table.py`
- Create: `tests/unit/test_operating_table.py`

- [ ] **Step 1: Write failing staging tests**

Create `tests/unit/test_operating_table.py` with this initial content:

```python
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
                            "_Simanalysis_Cleanup/cleanup-20260612-101400/"
                            "archives/Mods/archive.zip"
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
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-red.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: fail with `ModuleNotFoundError: No module named 'simanalysis.operating_table'`.

- [ ] **Step 3: Implement staging service**

Create `src/simanalysis/operating_table.py` with this implementation:

```python
"""Manifest-first cleanup operation staging, apply, and restore."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, cast

from simanalysis.treatment import assert_sims_not_running

MANIFEST_VERSION = 1
SESSION_ROOT_NAME = "_Simanalysis_Cleanup"
MANIFEST_DIR_NAME = "manifests"
VALID_ACTION_KINDS = {
    "review_duplicate",
    "review_archive",
    "review_resource_cfg",
    "review_support_file",
    "review_misplaced_tray",
}
VALID_MANIFEST_STATUSES = {
    "planned",
    "applying",
    "applied",
    "partial",
    "blocked",
    "restoring",
    "restored",
}
RESTORABLE_ACTION_STATUSES = {"moving", "moved", "restore_pending", "restoring"}


class OperatingTable:
    """Stage and execute cleanup operations from review-only cleanup plans."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now

    def stage_cleanup_plan(
        self,
        root_path: Path | str,
        plan: dict[str, Any],
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Invalid Sims 4 directory path: {root_path}")
        _validate_plan_for_root(plan, root)

        selected_ids = _selected_action_ids(plan, selected_action_ids, all_actions)
        created_at = self._clock()
        operation_id = _operation_id(created_at)
        manifest_path = root / SESSION_ROOT_NAME / MANIFEST_DIR_NAME / f"{operation_id}.json"
        actions = [
            _manifest_action(root, plan, action_id)
            for action_id in selected_ids
        ]
        manifest: dict[str, Any] = {
            "version": MANIFEST_VERSION,
            "operation_id": operation_id,
            "created_at": created_at,
            "updated_at": created_at,
            "root_path": str(root),
            "mods_path": str(root / "Mods"),
            "source_plan": {
                "version": int(plan["version"]),
                "plan_id": str(plan["plan_id"]),
                "scan_id": int(plan["scan_id"]),
                "created_at": str(plan["created_at"]),
            },
            "manifest_path": str(manifest_path),
            "status": "planned",
            "actions": actions,
            "warnings": [],
            "blockers": [],
        }
        return _write_manifest(manifest)

    def stage_cleanup_plan_file(
        self,
        root_path: Path | str,
        plan_path: Path | str,
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        plan = _load_plan_file(plan_path)
        return self.stage_cleanup_plan(
            root_path,
            plan,
            selected_action_ids=selected_action_ids,
            all_actions=all_actions,
        )

    def load_status(self, manifest_path: Path | str) -> dict[str, Any]:
        return load_manifest(manifest_path)

    def apply(self, manifest_path: Path | str) -> dict[str, Any]:
        raise NotImplementedError("apply is implemented in Task 2")

    def restore(self, manifest_path: Path | str) -> dict[str, Any]:
        raise NotImplementedError("restore is implemented in Task 3")


def load_manifest(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Manifest must be a JSON object")
    manifest = cast(dict[str, Any], parsed)
    _validate_manifest(manifest, path)
    return manifest


def _validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("Unsupported cleanup operation manifest version")
    required = {
        "operation_id",
        "created_at",
        "updated_at",
        "root_path",
        "mods_path",
        "source_plan",
        "manifest_path",
        "status",
        "actions",
        "warnings",
        "blockers",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"Manifest is missing required keys: {', '.join(sorted(missing))}")
    if manifest["status"] not in VALID_MANIFEST_STATUSES:
        raise ValueError(f"Unknown cleanup operation status: {manifest['status']}")
    if Path(str(manifest["manifest_path"])).expanduser().resolve() != path:
        raise ValueError("Manifest path does not match loaded path")
    if not isinstance(manifest["actions"], list):
        raise ValueError("Manifest actions must be a list")


def _load_plan_file(plan_path: Path | str) -> dict[str, Any]:
    path = Path(plan_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Cleanup plan not found: {plan_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cleanup plan is not valid JSON: {plan_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Cleanup plan must be a JSON object")
    return cast(dict[str, Any], parsed)


def _validate_plan_for_root(plan: dict[str, Any], root: Path) -> None:
    if plan.get("version") != 1:
        raise ValueError("Unsupported cleanup plan version")
    if Path(str(plan.get("root_path", ""))).expanduser().resolve() != root:
        raise ValueError("Cleanup plan root does not match selected Sims 4 folder")
    for key in ("plan_id", "created_at", "scan_id", "findings"):
        if key not in plan:
            raise ValueError(f"Cleanup plan is missing required key: {key}")
    if not isinstance(plan["findings"], list):
        raise ValueError("Cleanup plan findings must be a list")


def _selected_action_ids(
    plan: dict[str, Any],
    selected_action_ids: list[str] | None,
    all_actions: bool,
) -> list[str]:
    selected = list(selected_action_ids or [])
    if selected and all_actions:
        raise ValueError("Choose explicit actions or --all-actions, not both")
    available = [action["action_id"] for _, action in _iter_plan_actions(plan)]
    if all_actions:
        selected = [str(action_id) for action_id in available]
    if not selected:
        raise ValueError("Choose at least one cleanup action")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate cleanup action selected")
    missing = sorted(set(selected) - {str(action_id) for action_id in available})
    if missing:
        raise ValueError(f"Unknown cleanup action: {', '.join(missing)}")
    return selected


def _iter_plan_actions(plan: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for finding in plan["findings"]:
        if not isinstance(finding, dict):
            continue
        actions = finding.get("actions", [])
        if not isinstance(actions, list):
            continue
        for action in actions:
            if isinstance(action, dict):
                pairs.append((finding, action))
    return pairs


def _find_plan_action(
    plan: dict[str, Any],
    action_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (finding, action)
        for finding, action in _iter_plan_actions(plan)
        if str(action.get("action_id")) == action_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Cleanup action must map to exactly one finding: {action_id}")
    return matches[0]


def _manifest_action(root: Path, plan: dict[str, Any], action_id: str) -> dict[str, Any]:
    finding, action = _find_plan_action(plan, action_id)
    kind = str(action.get("kind", ""))
    if kind not in VALID_ACTION_KINDS:
        raise ValueError(f"Unsupported cleanup action kind: {kind}")

    source_relative = str(action.get("source_relative_path", ""))
    destination_relative = str(action.get("proposed_destination", ""))
    source_path = _resolve_source(root, source_relative)
    destination_path = _resolve_destination(root, destination_relative)
    evidence = finding.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ValueError(f"Cleanup finding has invalid evidence: {finding.get('finding_id')}")
    expected = _expected_for_action(evidence, source_relative)
    _reject_symlinked_path(source_path, "symlinked source")
    _reject_symlinked_existing_ancestors(destination_path, "symlinked destination")
    return {
        "action_id": action_id,
        "finding_id": str(finding.get("finding_id", "")),
        "kind": kind,
        "source_relative_path": source_relative,
        "destination_relative_path": destination_relative,
        "source_path": str(source_path),
        "destination_path": str(destination_path),
        "reason": str(action.get("reason", "")),
        "expected": expected,
        "status": "pending",
        "error": None,
    }


def _expected_for_action(evidence: dict[str, Any], source_relative: str) -> dict[str, Any]:
    if "path" in evidence and str(evidence["path"]) != source_relative:
        raise ValueError("Cleanup finding evidence path does not match selected action")
    expected: dict[str, Any] = {}
    if "sha256" in evidence:
        expected["sha256"] = str(evidence["sha256"])
    if "size" in evidence:
        expected["size"] = int(evidence["size"])
    if "keep_candidate" in evidence:
        expected["keep_candidate"] = str(evidence["keep_candidate"])
    return expected


def _resolve_source(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Cleanup source must be a relative Mods path")
    source = _logical_absolute(root / relative_path)
    mods = _logical_absolute(root / "Mods")
    try:
        source.relative_to(mods)
    except ValueError as exc:
        raise ValueError("Cleanup source must be under Mods") from exc
    return source


def _resolve_destination(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Cleanup destination must be relative")
    destination = _logical_absolute(root / relative_path)
    cleanup_root = _logical_absolute(root / SESSION_ROOT_NAME)
    try:
        destination.relative_to(cleanup_root)
    except ValueError as exc:
        raise ValueError("Cleanup destination must be under _Simanalysis_Cleanup") from exc
    if destination == cleanup_root:
        raise ValueError("Cleanup destination must be a file path")
    return destination


def _logical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _reject_symlinked_path(path: Path, message: str) -> None:
    for part in [path, *path.parents]:
        if part.exists() and part.is_symlink():
            raise ValueError(f"Refusing {message}: {path}")


def _reject_symlinked_existing_ancestors(path: Path, message: str) -> None:
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    _reject_symlinked_path(current, message)


def _write_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(manifest["manifest_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(json.dumps(manifest, indent=2, sort_keys=True))
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return manifest


def _operation_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cleanup-op-{digits[:8]}-{digits[8:14]}"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
```

- [ ] **Step 4: Run staging tests to verify GREEN**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-stage-green.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: `6 passed`.

- [ ] **Step 5: Run focused formatting/linting**

Run:

```bash
.venv/bin/ruff check src/simanalysis/operating_table.py tests/unit/test_operating_table.py
.venv/bin/ruff format --check src/simanalysis/operating_table.py tests/unit/test_operating_table.py
```

Expected: both pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/simanalysis/operating_table.py tests/unit/test_operating_table.py
git commit -m "feat: stage cleanup operation manifests"
```

---

### Task 2: Apply Cleanup Manifests With Preflight And Partial-State Safety

**Files:**
- Modify: `src/simanalysis/operating_table.py`
- Modify: `tests/unit/test_operating_table.py`

- [ ] **Step 1: Add failing apply tests**

Append these tests to `tests/unit/test_operating_table.py`:

```python
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


def test_apply_refuses_running_sims_before_mutation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_apply_refuses_hash_mismatch_without_moving(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    source.write_bytes(b"changed")

    with pytest.raises(ValueError, match="no longer matches cleanup plan evidence"):
        table.apply(manifest_path)

    assert source.exists()
    assert load_manifest(manifest_path)["status"] == "planned"


def test_apply_preflight_blocks_destination_collision_before_any_move(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    manifest = load_manifest(manifest_path)
    destination = Path(str(manifest["actions"][0]["destination_path"]))
    _write(destination, b"collision")

    with pytest.raises(ValueError, match="Destination already exists"):
        table.apply(manifest_path)

    assert source.exists()
    assert destination.read_bytes() == b"collision"
    assert load_manifest(manifest_path)["status"] == "planned"


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
```

- [ ] **Step 2: Run apply tests to verify RED**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-apply-red.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: fail because `OperatingTable.apply` raises `NotImplementedError`.

- [ ] **Step 3: Implement apply behavior**

Modify `src/simanalysis/operating_table.py`:

1. Add these imports if they are missing:

```python
import hashlib
import shutil
```

2. Replace `OperatingTable.apply` with:

```python
    def apply(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_manifest(manifest_path)
        if manifest["status"] not in {"planned", "partial"}:
            raise ValueError(f"Cleanup operation cannot be applied from status: {manifest['status']}")
        pending = [
            action
            for action in cast(list[dict[str, Any]], manifest["actions"])
            if action.get("status") in {"pending", "blocked"}
        ]
        _preflight_actions(pending)
        manifest["status"] = "applying"
        _save_manifest(manifest)

        for action in pending:
            try:
                _preflight_action(action)
                action["status"] = "moving"
                action["error"] = None
                _save_manifest(manifest)
                destination = Path(str(action["destination_path"]))
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(action["source_path"]), str(destination))
                action["status"] = "moved"
                _save_manifest(manifest)
            except Exception as exc:
                action["status"] = "blocked"
                action["error"] = str(exc)
                manifest["status"] = "partial" if _has_moved_actions(manifest) else "blocked"
                _save_manifest(manifest)
                raise

        manifest["status"] = "applied"
        return _save_manifest(manifest)
```

3. Add these helpers below `_write_manifest`:

```python
def _save_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["updated_at"] = _utc_now()
    return _write_manifest(manifest)


def _preflight_actions(actions: list[dict[str, Any]]) -> None:
    for action in actions:
        _preflight_action(action)


def _preflight_action(action: dict[str, Any]) -> None:
    source = Path(str(action["source_path"]))
    destination = Path(str(action["destination_path"]))
    if not source.exists():
        raise ValueError(f"Source path is missing: {source}")
    _reject_symlinked_path(source, "symlinked source")
    _reject_symlinked_existing_ancestors(destination, "symlinked destination")
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    _validate_source_still_under_mods(action)
    _validate_destination_still_under_cleanup(action)
    _validate_expected_file_identity(action)


def _validate_source_still_under_mods(action: dict[str, Any]) -> None:
    source = _logical_absolute(Path(str(action["source_path"])))
    relative = Path(str(action["source_relative_path"]))
    if not relative.parts or relative.parts[0] != "Mods":
        raise ValueError("Source relative path is not under Mods")
    root = source
    for _ in relative.parts:
        root = root.parent
    mods = _logical_absolute(root / "Mods")
    if mods.is_symlink():
        raise ValueError("Mods folder must not be a symlink")
    try:
        source.relative_to(mods)
    except ValueError as exc:
        raise ValueError("Source path is not under Mods") from exc


def _validate_destination_still_under_cleanup(action: dict[str, Any]) -> None:
    destination = _logical_absolute(Path(str(action["destination_path"])))
    parts = destination.parts
    if SESSION_ROOT_NAME not in parts:
        raise ValueError("Destination is not under _Simanalysis_Cleanup")
    cleanup_index = parts.index(SESSION_ROOT_NAME)
    cleanup_root = Path(*parts[: cleanup_index + 1])
    try:
        destination.relative_to(cleanup_root)
    except ValueError as exc:
        raise ValueError("Destination is not under _Simanalysis_Cleanup") from exc


def _validate_expected_file_identity(action: dict[str, Any]) -> None:
    expected = action.get("expected", {})
    if not isinstance(expected, dict):
        raise ValueError("Action expected evidence must be an object")
    source = Path(str(action["source_path"]))
    if "size" in expected and source.stat().st_size != int(expected["size"]):
        raise ValueError(f"Source path no longer matches cleanup plan evidence: {source}")
    if "sha256" in expected and _sha256_file(source) != str(expected["sha256"]):
        raise ValueError(f"Source path no longer matches cleanup plan evidence: {source}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_moved_actions(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(action, dict) and action.get("status") == "moved"
        for action in manifest.get("actions", [])
    )
```

- [ ] **Step 4: Run apply tests to verify GREEN**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-apply-green.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: staging and apply tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/simanalysis/operating_table.py tests/unit/test_operating_table.py
git commit -m "feat: apply cleanup operation manifests"
```

---

### Task 3: Restore From Cleanup Manifests

**Files:**
- Modify: `src/simanalysis/operating_table.py`
- Modify: `tests/unit/test_operating_table.py`

- [ ] **Step 1: Add failing restore tests**

Append these tests:

```python
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


def test_restore_refuses_destination_collision_and_preserves_state(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    table.apply(manifest_path)
    source.write_bytes(b"collision")

    with pytest.raises(ValueError, match="Restore destination already exists"):
        table.restore(manifest_path)

    saved = load_manifest(manifest_path)
    assert saved["status"] == "blocked"
    assert saved["actions"][0]["status"] == "blocked"


def test_restore_refuses_running_sims_before_mutation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_stage_apply_restore_returns_mods_to_original_file_set(tmp_path: Path) -> None:
    table, manifest_path, source = _stage_manifest(tmp_path)
    mods = source.parents[1]
    before = sorted(path.relative_to(mods) for path in mods.rglob("*") if path.is_file())

    table.apply(manifest_path)
    table.restore(manifest_path)

    after = sorted(path.relative_to(mods) for path in mods.rglob("*") if path.is_file())
    assert after == before
```

- [ ] **Step 2: Run restore tests to verify RED**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-restore-red.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: fail because `OperatingTable.restore` raises `NotImplementedError`.

- [ ] **Step 3: Implement restore behavior**

Replace `OperatingTable.restore` with:

```python
    def restore(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_manifest(manifest_path)
        restorable = [
            action
            for action in reversed(cast(list[dict[str, Any]], manifest["actions"]))
            if action.get("status") in RESTORABLE_ACTION_STATUSES
        ]
        manifest["status"] = "restoring"
        _save_manifest(manifest)

        for action in restorable:
            try:
                _restore_action(action)
                action["status"] = "restored"
                action["error"] = None
                _save_manifest(manifest)
            except Exception as exc:
                action["status"] = "blocked"
                action["error"] = str(exc)
                manifest["status"] = "blocked"
                _save_manifest(manifest)
                raise

        if _has_moved_or_moving_actions(manifest):
            manifest["status"] = "blocked"
            _save_manifest(manifest)
            raise ValueError("Could not restore every moved cleanup action")
        manifest["status"] = "restored"
        return _save_manifest(manifest)
```

Add these helpers:

```python
def _restore_action(action: dict[str, Any]) -> None:
    source = Path(str(action["destination_path"]))
    destination = Path(str(action["source_path"]))
    if not source.exists():
        if action.get("status") == "moving" and destination.exists():
            return
        raise ValueError(f"Restore source is missing: {source}")
    _reject_symlinked_path(source, "symlinked restore source")
    _reject_symlinked_existing_ancestors(destination, "symlinked restore destination")
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}")
    _validate_destination_still_under_cleanup(action)
    _validate_source_still_under_mods(action)
    destination.parent.mkdir(parents=True, exist_ok=True)
    action["status"] = "restoring"
    shutil.move(str(source), str(destination))


def _has_moved_or_moving_actions(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(action, dict)
        and action.get("status") in {"moving", "moved", "restore_pending", "restoring"}
        for action in manifest.get("actions", [])
    )
```

- [ ] **Step 4: Run restore tests to verify GREEN**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-restore-green.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py -q --no-cov
```

Expected: all `test_operating_table.py` tests pass.

- [ ] **Step 5: Run static checks for service**

Run:

```bash
.venv/bin/ruff check src/simanalysis/operating_table.py tests/unit/test_operating_table.py
.venv/bin/ruff format --check src/simanalysis/operating_table.py tests/unit/test_operating_table.py
.venv/bin/mypy src
```

Expected: all pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/simanalysis/operating_table.py tests/unit/test_operating_table.py
git commit -m "feat: restore cleanup operation manifests"
```

---

### Task 4: Bridge Commands

**Files:**
- Modify: `src/simanalysis/bridge/__init__.py`
- Modify: `src/simanalysis/bridge/commands.py`
- Modify: `tests/unit/test_bridge_main.py`
- Modify: `tests/unit/test_bridge_commands.py`

- [ ] **Step 1: Add failing parser tests**

Append to `tests/unit/test_bridge_main.py`:

```python
def test_cleanup_stage_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    plan_path = tmp_path / "plan.json"

    def fake_cleanup_stage(args, emit):
        called["path"] = args.path
        called["plan"] = args.plan
        called["actions"] = args.action
        called["all_actions"] = args.all_actions
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "cleanup-stage", fake_cleanup_stage)

    code, events = _run(
        monkeypatch,
        [
            "cleanup-stage",
            str(tmp_path),
            "--plan",
            str(plan_path),
            "--action",
            "duplicate:1",
            "--action",
            "archive:1",
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "plan": str(plan_path),
        "actions": ["duplicate:1", "archive:1"],
        "all_actions": False,
    }
    assert [event["type"] for event in events] == ["result", "done"]


def test_cleanup_operation_commands_are_dispatched(monkeypatch):
    calls = []

    def fake_handler(args, emit):
        calls.append((args.command, getattr(args, "manifest_path", None)))
        emit.result({"ok": True})
        emit.done()

    for command in ("cleanup-apply", "cleanup-restore", "cleanup-status"):
        monkeypatch.setitem(commands.DISPATCH, command, fake_handler)

    for command in ("cleanup-apply", "cleanup-restore", "cleanup-status"):
        code, events = _run(monkeypatch, [command, "manifest.json"])
        assert code == 0
        assert [event["type"] for event in events] == ["result", "done"]

    assert calls == [
        ("cleanup-apply", "manifest.json"),
        ("cleanup-restore", "manifest.json"),
        ("cleanup-status", "manifest.json"),
    ]
```

- [ ] **Step 2: Add failing command handler tests**

Append to `tests/unit/test_bridge_commands.py`:

```python
def test_cleanup_stage_emits_operation_manifest(monkeypatch, tmp_path):
    calls = {}

    class FakeOperatingTable:
        def stage_cleanup_plan_file(self, root, plan, *, selected_action_ids=None, all_actions=False):
            calls["stage"] = (root, plan, selected_action_ids, all_actions)
            return {"manifest_path": "manifest.json", "status": "planned"}

    monkeypatch.setattr(commands, "OperatingTable", lambda: FakeOperatingTable())

    buf = io.StringIO()
    commands.cleanup_stage(
        argparse.Namespace(
            path=str(tmp_path),
            plan="plan.json",
            action=["duplicate:1"],
            all_actions=False,
        ),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "cleanup-stage"
    assert events[1]["data"] == {"manifest_path": "manifest.json", "status": "planned"}
    assert calls["stage"] == (tmp_path.resolve(), "plan.json", ["duplicate:1"], False)


def test_cleanup_apply_restore_status_emit_results(monkeypatch):
    calls = []

    class FakeOperatingTable:
        def apply(self, manifest_path):
            calls.append(("apply", manifest_path))
            return {"status": "applied"}

        def restore(self, manifest_path):
            calls.append(("restore", manifest_path))
            return {"status": "restored"}

        def load_status(self, manifest_path):
            calls.append(("status", manifest_path))
            return {"status": "planned"}

    monkeypatch.setattr(commands, "OperatingTable", lambda: FakeOperatingTable())

    for handler, task, status in (
        (commands.cleanup_apply, "cleanup-apply", "applied"),
        (commands.cleanup_restore, "cleanup-restore", "restored"),
        (commands.cleanup_status, "cleanup-status", "planned"),
    ):
        buf = io.StringIO()
        handler(argparse.Namespace(manifest_path="manifest.json"), Emitter(buf))
        events = [json.loads(line) for line in buf.getvalue().splitlines()]
        assert [event["type"] for event in events] == ["start", "result", "done"]
        assert events[0]["task"] == task
        assert events[1]["data"] == {"status": status}

    assert calls == [
        ("apply", "manifest.json"),
        ("restore", "manifest.json"),
        ("status", "manifest.json"),
    ]
```

- [ ] **Step 3: Run bridge tests to verify RED**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-bridge-red.coverage .venv/bin/python -m pytest tests/unit/test_bridge_main.py::test_cleanup_stage_command_is_dispatched tests/unit/test_bridge_main.py::test_cleanup_operation_commands_are_dispatched tests/unit/test_bridge_commands.py::test_cleanup_stage_emits_operation_manifest tests/unit/test_bridge_commands.py::test_cleanup_apply_restore_status_emit_results -q --no-cov
```

Expected: fail because parser choices and command handlers do not exist.

- [ ] **Step 4: Add parser commands**

Modify `src/simanalysis/bridge/__init__.py` after the `cleanup-plan` parser:

```python
    p_cleanup_stage = sub.add_parser("cleanup-stage")
    p_cleanup_stage.add_argument("path")
    p_cleanup_stage.add_argument("--plan", required=True)
    p_cleanup_stage.add_argument("--action", action="append", default=[])
    p_cleanup_stage.add_argument("--all-actions", action="store_true")

    p_cleanup_apply = sub.add_parser("cleanup-apply")
    p_cleanup_apply.add_argument("manifest_path")

    p_cleanup_restore = sub.add_parser("cleanup-restore")
    p_cleanup_restore.add_argument("manifest_path")

    p_cleanup_status = sub.add_parser("cleanup-status")
    p_cleanup_status.add_argument("manifest_path")
```

- [ ] **Step 5: Add command handlers and dispatch**

Modify `src/simanalysis/bridge/commands.py`:

1. Add import:

```python
from simanalysis.operating_table import OperatingTable
```

2. Add handlers after `cleanup_plan`:

```python
def cleanup_stage(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("cleanup-stage")
    result = OperatingTable().stage_cleanup_plan_file(
        path,
        args.plan,
        selected_action_ids=args.action,
        all_actions=args.all_actions,
    )
    emit.result(result)
    emit.done()


def cleanup_apply(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("cleanup-apply")
    emit.result(OperatingTable().apply(args.manifest_path))
    emit.done()


def cleanup_restore(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("cleanup-restore")
    emit.result(OperatingTable().restore(args.manifest_path))
    emit.done()


def cleanup_status(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("cleanup-status")
    emit.result(OperatingTable().load_status(args.manifest_path))
    emit.done()
```

3. Add to `DISPATCH`:

```python
    "cleanup-stage": cleanup_stage,
    "cleanup-apply": cleanup_apply,
    "cleanup-restore": cleanup_restore,
    "cleanup-status": cleanup_status,
```

- [ ] **Step 6: Run bridge tests to verify GREEN**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-bridge-green.coverage .venv/bin/python -m pytest tests/unit/test_bridge_main.py::test_cleanup_stage_command_is_dispatched tests/unit/test_bridge_main.py::test_cleanup_operation_commands_are_dispatched tests/unit/test_bridge_commands.py::test_cleanup_stage_emits_operation_manifest tests/unit/test_bridge_commands.py::test_cleanup_apply_restore_status_emit_results -q --no-cov
```

Expected: `4 passed`.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
git commit -m "feat: expose cleanup operation bridge commands"
```

---

### Task 5: Tauri And Web Non-Visual API Plumbing

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Modify: `web/src/api.js`
- Create: `web/src/operatingTableApiModel.js`
- Create: `web/src/operatingTableApiModel.test.js`

- [ ] **Step 1: Add failing Rust argument-builder tests**

Append in the Rust `tests` module in `src-tauri/src/lib.rs`:

```rust
    #[test]
    fn builds_cleanup_stage_args_with_plan_and_actions() {
        let opts = AnalysisOptions {
            plan_path: Some("/tmp/cleanup-plan.json".into()),
            actions: vec!["duplicate:1".into(), "archive:1".into()],
            ..Default::default()
        };
        let args = build_args("cleanup-stage", "/Sims/The Sims 4", &opts).unwrap();
        assert_eq!(
            args,
            vec![
                "cleanup-stage",
                "/Sims/The Sims 4",
                "--plan",
                "/tmp/cleanup-plan.json",
                "--action",
                "duplicate:1",
                "--action",
                "archive:1",
            ]
        );
    }

    #[test]
    fn builds_cleanup_stage_args_with_all_actions() {
        let opts = AnalysisOptions {
            plan_path: Some("/tmp/cleanup-plan.json".into()),
            all_actions: true,
            ..Default::default()
        };
        let args = build_args("cleanup-stage", "/Sims/The Sims 4", &opts).unwrap();
        assert_eq!(
            args,
            vec![
                "cleanup-stage",
                "/Sims/The Sims 4",
                "--plan",
                "/tmp/cleanup-plan.json",
                "--all-actions",
            ]
        );
    }

    #[test]
    fn cleanup_stage_requires_plan_path() {
        let err = build_args("cleanup-stage", "/Sims/The Sims 4", &AnalysisOptions::default())
            .unwrap_err();
        assert_eq!(err, "cleanup-stage requires options.planPath");
    }

    #[test]
    fn builds_cleanup_operation_manifest_args() {
        for kind in ["cleanup-apply", "cleanup-restore", "cleanup-status"] {
            let args = build_args(kind, "/Sims/manifest.json", &AnalysisOptions::default())
                .unwrap();
            assert_eq!(args, vec![kind, "/Sims/manifest.json"]);
        }
    }
```

- [ ] **Step 2: Run Rust tests to verify RED**

Run:

```bash
cargo test builds_cleanup_stage_args_with_plan_and_actions --manifest-path src-tauri/Cargo.toml
```

Expected: fail because `AnalysisOptions` does not have `plan_path`, `actions`, or `all_actions`.

- [ ] **Step 3: Implement Rust argument plumbing**

Modify `AnalysisOptions` in `src-tauri/src/lib.rs`:

```rust
    #[serde(default)]
    plan_path: Option<String>,
    #[serde(default)]
    actions: Vec<String>,
    #[serde(default)]
    all_actions: bool,
```

Add cases in `build_args` after `cleanup-plan`:

```rust
        "cleanup-stage" => {
            let plan_path = opts
                .plan_path
                .as_deref()
                .ok_or("cleanup-stage requires options.planPath")?;
            args.push("cleanup-stage".into());
            args.push(path.into());
            args.push("--plan".into());
            args.push(plan_path.into());
            for action in &opts.actions {
                args.push("--action".into());
                args.push(action.into());
            }
            if opts.all_actions {
                args.push("--all-actions".into());
            }
        }
        "cleanup-apply" | "cleanup-restore" | "cleanup-status" => {
            args.push(kind.into());
            args.push(path.into());
        }
```

- [ ] **Step 4: Add failing web model tests**

Create `web/src/operatingTableApiModel.test.js`:

```javascript
import assert from 'node:assert/strict';
import test from 'node:test';

import { cleanupStageOptions } from './operatingTableApiModel.js';

test('cleanup stage options require a plan path', () => {
  assert.throws(
    () => cleanupStageOptions({ actions: ['duplicate:1'] }),
    /planPath/,
  );
});

test('cleanup stage options include selected actions', () => {
  assert.deepEqual(
    cleanupStageOptions({
      planPath: '/tmp/cleanup-plan.json',
      actions: ['duplicate:1', 'archive:1'],
    }),
    {
      planPath: '/tmp/cleanup-plan.json',
      actions: ['duplicate:1', 'archive:1'],
      allActions: false,
    },
  );
});

test('cleanup stage options include all-actions flag', () => {
  assert.deepEqual(
    cleanupStageOptions({
      planPath: '/tmp/cleanup-plan.json',
      allActions: true,
    }),
    {
      planPath: '/tmp/cleanup-plan.json',
      actions: [],
      allActions: true,
    },
  );
});

test('cleanup stage options reject action and all-actions together', () => {
  assert.throws(
    () => cleanupStageOptions({
      planPath: '/tmp/cleanup-plan.json',
      actions: ['duplicate:1'],
      allActions: true,
    }),
    /either selected actions or allActions/,
  );
});
```

- [ ] **Step 5: Run web model tests to verify RED**

Run:

```bash
node --test web/src/operatingTableApiModel.test.js
```

Expected: fail with `ERR_MODULE_NOT_FOUND` for `operatingTableApiModel.js`.

- [ ] **Step 6: Implement web model and API wrappers**

Create `web/src/operatingTableApiModel.js`:

```javascript
export function cleanupStageOptions(options = {}) {
  if (!options.planPath) {
    throw new Error('cleanupStage requires planPath');
  }
  const actions = Array.isArray(options.actions) ? options.actions : [];
  const allActions = Boolean(options.allActions);
  if (actions.length > 0 && allActions) {
    throw new Error('Choose either selected actions or allActions');
  }
  return {
    planPath: options.planPath,
    actions,
    allActions,
  };
}
```

Modify `web/src/api.js`:

1. Add import:

```javascript
import { cleanupStageOptions } from './operatingTableApiModel';
```

2. Add wrappers near `cleanupPlan`:

```javascript
  cleanupStage: (sims4Path, callbacks, options = {}) =>
    runAnalysis('cleanup-stage', sims4Path, cleanupStageOptions(options), callbacks),
  cleanupApply: (manifestPath, callbacks) =>
    runAnalysis('cleanup-apply', manifestPath, {}, callbacks),
  cleanupRestore: (manifestPath, callbacks) =>
    runAnalysis('cleanup-restore', manifestPath, {}, callbacks),
  cleanupStatus: (manifestPath, callbacks) =>
    runAnalysis('cleanup-status', manifestPath, {}, callbacks),
```

- [ ] **Step 7: Run Tauri/web tests to verify GREEN**

Run:

```bash
cargo test builds_cleanup_stage_args_with_plan_and_actions --manifest-path src-tauri/Cargo.toml
cargo test builds_cleanup_operation_manifest_args --manifest-path src-tauri/Cargo.toml
node --test web/src/operatingTableApiModel.test.js web/src/cleanupApiModel.test.js web/src/inventoryApiModel.test.js web/src/liveMonitorModel.test.js
```

Expected: Rust focused tests pass, Node tests pass.

- [ ] **Step 8: Commit Task 5**

```bash
git add src-tauri/src/lib.rs web/src/api.js web/src/operatingTableApiModel.js web/src/operatingTableApiModel.test.js
git commit -m "feat: add cleanup operation api plumbing"
```

---

### Task 6: Documentation And Full Verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `IMPLEMENTATION_STATUS.md`
- Modify: `docs/STATUS.md`
- Modify: `docs/superpowers/specs/2026-06-12-operating-table-v1-design.md`

- [ ] **Step 1: Update release/status docs**

Add to `CHANGELOG.md` under `[Unreleased]` / `Added`:

```markdown
- Added Operating Table v1 backend plumbing for manifest-first cleanup staging, apply, restore, and status commands, preserving explicit selection, Sims process guards, path/hash preflight, and restore-from-manifest behavior.
```

In `IMPLEMENTATION_STATUS.md`, add after `Cleanup Planner Progress`:

```markdown
## Operating Table Progress

Implemented on this branch after Cleanup Planner v1:

- Added `src/simanalysis/operating_table.py`, a manifest-first cleanup operation engine.
- Cleanup actions must be explicitly selected or staged with an explicit all-actions flag.
- Apply and restore use the operation manifest, block while The Sims 4 is running, reject path escapes/symlinks/collisions, and never delete or overwrite files.
- The desktop bridge and Tauri/web API plumbing expose `cleanup-stage`, `cleanup-apply`, `cleanup-restore`, and `cleanup-status`; the visual cleanup route remains future work.
```

In `docs/STATUS.md`, extend the current branch note:

```markdown
Operating Table v1 adds manifest-first non-visual cleanup staging, apply, restore, and status plumbing. Visual inventory and cleanup routes remain pending design approval.
```

In `docs/superpowers/specs/2026-06-12-operating-table-v1-design.md`, change status to:

```markdown
**Status:** Implemented backend/API slice; visual cleanup route pending separate design
```

- [ ] **Step 2: Run targeted Python verification**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-operating-table-targeted.coverage .venv/bin/python -m pytest tests/unit/test_operating_table.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
```

Expected: all targeted tests pass.

- [ ] **Step 3: Run full Python gates**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
COVERAGE_FILE=/tmp/simanalysis-operating-table-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-operating-table-full.coverage .venv/bin/python -m pytest -q
```

Expected: all pass.

- [ ] **Step 4: Run Rust and web gates**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
node --test web/src/operatingTableApiModel.test.js web/src/cleanupApiModel.test.js web/src/inventoryApiModel.test.js web/src/liveMonitorModel.test.js
npm --prefix web run lint
npm --prefix web run build
```

Expected: all pass. The Vite build may emit existing browser-data freshness warnings; those warnings are acceptable if the build exits zero.

- [ ] **Step 5: Run diff/status checks**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended docs/code files are modified before final commit.

- [ ] **Step 6: Commit verified Operating Table slice**

```bash
git add CHANGELOG.md IMPLEMENTATION_STATUS.md docs/STATUS.md docs/superpowers/specs/2026-06-12-operating-table-v1-design.md
git commit -m "docs: update operating table status"
```

If any code/test files remain unstaged from formatting or final fixes, include them in the commit only after rerunning the relevant focused verification.

---

## Spec Coverage Map

- Consume Cleanup Planner v1 plan: Task 1 `stage_cleanup_plan` and `stage_cleanup_plan_file`.
- Explicit selected actions or explicit all-actions: Task 1 tests and `_selected_action_ids`.
- Manifest-first writes: Task 1 writes manifest; Task 2 writes statuses before moves.
- Apply moves into `_Simanalysis_Cleanup`: Task 2.
- Restore from manifest: Task 3.
- Sims process guard: Tasks 2 and 3.
- Path escape, symlink, missing source, collision, malformed plan/manifest, unsupported version: Tasks 1-3.
- Source hash/size mismatch: Task 2.
- Partial progress and restore recovery: Tasks 2 and 3.
- Bridge commands: Task 4.
- Tauri/web non-visual wrappers: Task 5.
- No visual cleanup route: Task 5 only adds API wrappers; Task 6 docs preserve visual route as future work.
- Verification: Task 6.

## Execution Choice

Plan complete. Execute with one of these:

1. **Subagent-Driven (recommended):** one fresh task worker per task, with review checkpoints after each task.
2. **Inline Execution:** execute this plan in the current session using `executing-plans`, with checkpoints after each commit.
