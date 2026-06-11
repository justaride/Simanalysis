# Cleanup Planner v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Mods-folder cleanup planner that consumes the latest inventory snapshot and emits a JSON-serializable review plan without moving or creating Sims-folder files.

**Architecture:** Add a focused `simanalysis.cleanup` service that reads the existing inventory SQLite database directly, filters latest snapshot rows to `Mods/`, and runs small rule helpers for duplicates, archives, duplicate `Resource.cfg`, support files, and misplaced Tray files. Expose the service through a `cleanup-plan` bridge command, then add thin Tauri/web argument plumbing without adding a visual route.

**Tech Stack:** Python 3.11, SQLite stdlib, dataclasses, pytest, existing `InventoryScanner`, existing NDJSON bridge protocol, Rust Tauri argument-builder tests, Node test for web API options.

---

## Scope Check

The approved spec is one backend/non-visual slice. It creates a read-only planner service, bridge command, and thin non-visual wrappers. It does not add a React route, write cleanup manifests, create `_Simanalysis_Cleanup`, move files, scan outside `Mods`, unpack archives, or do network update checks.

## File Structure

- Create `src/simanalysis/cleanup.py`
  - Owns cleanup plan dataclasses, latest-inventory loading, Mods-only filtering, rule helpers, deterministic keep selection, proposed destination generation, export-path validation, and JSON writing.
- Create `tests/unit/test_cleanup.py`
  - Unit coverage for duplicate grouping, archives, duplicate `Resource.cfg`, support files, misplaced Tray files, outside-`Mods` ignore, missing-snapshot errors, export safety, and no-mutation guarantees.
- Modify `src/simanalysis/bridge/__init__.py`
  - Adds parser support for `simanalysis-bridge cleanup-plan <sims4_dir> [--db PATH] [--export PATH]`.
- Modify `src/simanalysis/bridge/commands.py`
  - Adds the `cleanup_plan` command handler and dispatch entry.
- Modify `tests/unit/test_bridge_main.py`
  - Covers parser/dispatch for `cleanup-plan`.
- Modify `tests/unit/test_bridge_commands.py`
  - Covers bridge command event sequence and explicit export behavior.
- Modify `src-tauri/src/lib.rs`
  - Adds an optional `export_path` field and `cleanup-plan` argument construction.
- Modify `web/src/api.js`
  - Adds `api.cleanupPlan(...)` as a thin non-visual wrapper.
- Create `web/src/cleanupApiModel.js`
  - Builds validated cleanup-plan options for the web API.
- Create `web/src/cleanupApiModel.test.js`
  - Covers default options plus db/export option shape.
- Modify `CHANGELOG.md`, `IMPLEMENTATION_STATUS.md`, and `docs/STATUS.md`
  - Records the new read-only planner surface once implementation is verified.

---

### Task 1: Core Cleanup Planner Service

**Files:**
- Create: `src/simanalysis/cleanup.py`
- Create: `tests/unit/test_cleanup.py`

- [ ] **Step 1: Write failing tests for the planner rules**

Create `tests/unit/test_cleanup.py`:

```python
"""Tests for read-only Mods cleanup planning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from simanalysis.cleanup import CleanupPlanner
from simanalysis.inventory import InventoryScanner, InventoryStore

pytestmark = pytest.mark.synthetic


def _scan_fixture(tmp_path: Path) -> tuple[Path, Path]:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)
    return sims4, db_path


def test_cleanup_plan_groups_exact_duplicates_with_stable_keep_candidate(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    deep = mods / "Creator" / "Nested"
    deep.mkdir(parents=True)
    (mods / "keep.package").write_bytes(b"duplicate")
    (deep / "extra.package").write_bytes(b"duplicate")
    (mods / "other.package").write_bytes(b"unique")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    duplicate = next(item for item in plan["findings"] if item["category"] == "exact_duplicate")
    assert plan["summary"]["duplicate_groups"] == 1
    assert duplicate["evidence"]["keep_candidate"] == "Mods/keep.package"
    assert duplicate["evidence"]["paths"] == [
        "Mods/Creator/Nested/extra.package",
        "Mods/keep.package",
    ]
    assert duplicate["actions"] == [
        {
            "action_id": "duplicate:1",
            "kind": "review_duplicate",
            "source_relative_path": "Mods/Creator/Nested/extra.package",
            "proposed_destination": (
                "_Simanalysis_Cleanup/cleanup-20260611-123456/"
                "duplicates/Mods/Creator/Nested/extra.package"
            ),
            "reason": "Exact duplicate of Mods/keep.package",
        }
    ]


def test_cleanup_plan_flags_archives_support_files_resource_cfg_and_tray(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pack = mods / "Creator"
    pack.mkdir(parents=True)
    (mods / "Resource.cfg").write_text("root resource", encoding="utf-8")
    (pack / "Resource.cfg").write_text("nested resource", encoding="utf-8")
    (mods / "download.zip").write_bytes(b"archive")
    (mods / "preview.png").write_bytes(b"image")
    (mods / "readme.txt").write_text("notes", encoding="utf-8")
    (mods / "lot.trayitem").write_bytes(b"tray")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    categories = [finding["category"] for finding in plan["findings"]]
    assert categories == [
        "duplicate_resource_cfg",
        "inactive_archive",
        "misplaced_tray",
        "support_file",
        "support_file",
    ]
    assert plan["summary"] == {
        "files_considered": 6,
        "finding_count": 5,
        "action_count": 5,
        "duplicate_groups": 0,
        "archives": 1,
        "duplicate_resource_cfg": 1,
        "support_files": 2,
        "misplaced_tray": 1,
    }
    assert all(action["kind"].startswith("review_") for finding in plan["findings"] for action in finding["actions"])


def test_cleanup_plan_ignores_files_outside_mods(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "active.package").write_bytes(b"active")
    tray = sims4 / "Tray"
    tray.mkdir()
    (tray / "real.trayitem").write_bytes(b"tray")
    (sims4 / "notes.zip").write_bytes(b"outside")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)

    plan = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)

    assert plan["summary"]["files_considered"] == 1
    assert plan["findings"] == []
    assert plan["warnings"] == []


def test_cleanup_plan_requires_existing_inventory_database(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    db_path = tmp_path / "inventory.sqlite3"

    with pytest.raises(ValueError, match="No inventory database exists"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)


def test_cleanup_plan_requires_existing_inventory_snapshot(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    db_path = tmp_path / "inventory.sqlite3"
    InventoryStore(db_path).initialize()

    with pytest.raises(ValueError, match="No inventory scan exists"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").plan(sims4)


def test_cleanup_plan_export_must_be_outside_sims_root(tmp_path: Path) -> None:
    sims4, db_path = _scan_fixture(tmp_path)
    export_path = sims4 / "cleanup.json"

    with pytest.raises(ValueError, match="outside the selected Sims 4 folder"):
        CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").export_plan(
            sims4,
            export_path,
        )

    assert not export_path.exists()


def test_cleanup_plan_export_writes_json_without_sims_folder_mutation(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.7z").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    InventoryScanner(db_path).scan(sims4)
    before = sorted(path.relative_to(sims4).as_posix() for path in sims4.rglob("*"))
    export_path = tmp_path / "cleanup-plan.json"

    result = CleanupPlanner(db_path, clock=lambda: "2026-06-11T12:34:56Z").export_plan(
        sims4,
        export_path,
    )

    after = sorted(path.relative_to(sims4).as_posix() for path in sims4.rglob("*"))
    assert before == after
    assert not (sims4 / "_Simanalysis_Cleanup").exists()
    assert json.loads(export_path.read_text(encoding="utf-8")) == result
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-red.coverage .venv/bin/python -m pytest tests/unit/test_cleanup.py -q --no-cov
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'simanalysis.cleanup'`.

- [ ] **Step 3: Implement the cleanup planner service**

Create `src/simanalysis/cleanup.py`:

```python
"""Read-only cleanup planning for Sims 4 Mods folders."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PLAN_VERSION = 1
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}
SUPPORT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".md",
    ".pdf",
    ".rtf",
    ".doc",
    ".docx",
    ".url",
    ".webloc",
    ".lnk",
}
SUPPORT_NAMES = {".ds_store", "thumbs.db"}
TRAY_EXTENSIONS = {".trayitem", ".blueprint", ".bpi", ".hhi", ".householdbinary", ".sgi"}


@dataclass(frozen=True)
class CleanupFile:
    relative_path: str
    extension: str
    size: int
    sha256: str


class CleanupPlanner:
    """Build read-only cleanup plans from inventory snapshots."""

    def __init__(
        self,
        db_path: Path | str,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser()
        self._clock = clock or _utc_now

    def plan(self, root_path: Path | str) -> dict[str, object]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Cleanup root is not a directory: {root_path}")
        if not self.db_path.exists():
            raise ValueError("No inventory database exists; run inventory-scan first")

        created_at = self._clock()
        plan_id = _plan_id(created_at)
        snapshot = _load_latest_inventory_files(self.db_path, root)
        mods_files = [item for item in snapshot.files if _is_mods_path(item.relative_path)]
        findings: list[dict[str, object]] = []
        findings.extend(_duplicate_findings(mods_files, plan_id))
        findings.extend(_single_file_findings(mods_files, plan_id))
        summary = _summary(mods_files, findings)
        warnings = list(snapshot.warnings)
        if not mods_files:
            warnings.append("Latest inventory snapshot contains no Mods files")

        return {
            "version": PLAN_VERSION,
            "plan_id": plan_id,
            "created_at": created_at,
            "root_path": str(root),
            "mods_path": str(root / "Mods"),
            "db_path": str(self.db_path),
            "scan_id": snapshot.scan_id,
            "summary": summary,
            "findings": findings,
            "warnings": warnings,
        }

    def export_plan(self, root_path: Path | str, export_path: Path | str) -> dict[str, object]:
        root = Path(root_path).expanduser().resolve()
        destination = Path(export_path).expanduser().resolve()
        if destination == root or root in destination.parents:
            raise ValueError("Cleanup plan export path must be outside the selected Sims 4 folder")

        plan = self.plan(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return plan


@dataclass(frozen=True)
class _InventorySnapshot:
    scan_id: int
    files: list[CleanupFile]
    warnings: list[str]


def _load_latest_inventory_files(db_path: Path, root: Path) -> _InventorySnapshot:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        snapshot = conn.execute(
            """
            SELECT
                s.id AS snapshot_id,
                s.scan_id,
                sc.warnings_json
            FROM snapshots s
            JOIN scans sc ON sc.id = s.scan_id
            WHERE s.root_path = ?
            ORDER BY s.id DESC
            LIMIT 1
            """,
            (str(root),),
        ).fetchone()
        if snapshot is None:
            raise ValueError(f"No inventory scan exists for {root}; run inventory-scan first")

        rows = conn.execute(
            """
            SELECT
                sf.relative_path,
                f.extension,
                sf.size,
                sf.sha256
            FROM snapshot_files sf
            JOIN files f ON f.id = sf.file_id
            WHERE sf.snapshot_id = ?
            ORDER BY sf.relative_path
            """,
            (int(snapshot["snapshot_id"]),),
        ).fetchall()

    return _InventorySnapshot(
        scan_id=int(snapshot["scan_id"]),
        files=[
            CleanupFile(
                relative_path=str(row["relative_path"]),
                extension=str(row["extension"]).lower(),
                size=int(row["size"]),
                sha256=str(row["sha256"]),
            )
            for row in rows
        ],
        warnings=json.loads(str(snapshot["warnings_json"])),
    )


def _is_mods_path(relative_path: str) -> bool:
    return relative_path == "Mods" or relative_path.startswith("Mods/")


def _duplicate_findings(files: list[CleanupFile], plan_id: str) -> list[dict[str, object]]:
    by_identity: dict[tuple[str, int], list[CleanupFile]] = {}
    for item in files:
        if item.size <= 0:
            continue
        by_identity.setdefault((item.sha256, item.size), []).append(item)

    findings: list[dict[str, object]] = []
    duplicate_index = 1
    for (sha256, size), group in sorted(by_identity.items(), key=lambda item: item[0]):
        if len(group) < 2:
            continue
        ordered_paths = sorted(item.relative_path for item in group)
        keep = min(ordered_paths, key=lambda path: (path.count("/"), len(path), path))
        actions = []
        for source in [path for path in ordered_paths if path != keep]:
            actions.append(
                {
                    "action_id": f"duplicate:{duplicate_index}",
                    "kind": "review_duplicate",
                    "source_relative_path": source,
                    "proposed_destination": _destination(plan_id, "duplicates", source),
                    "reason": f"Exact duplicate of {keep}",
                }
            )
            duplicate_index += 1
        findings.append(
            {
                "finding_id": f"duplicate:sha256:{sha256}",
                "category": "exact_duplicate",
                "severity": "review",
                "title": "Exact duplicate files",
                "explanation": "These files have identical SHA-256 and size in Mods.",
                "evidence": {
                    "sha256": sha256,
                    "size": size,
                    "paths": ordered_paths,
                    "keep_candidate": keep,
                },
                "actions": actions,
            }
        )
    return findings


def _single_file_findings(files: list[CleanupFile], plan_id: str) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for item in sorted(files, key=lambda file: file.relative_path):
        finding = _single_file_finding(item, plan_id)
        if finding is not None:
            findings.append(finding)
    return findings


def _single_file_finding(item: CleanupFile, plan_id: str) -> dict[str, object] | None:
    name = Path(item.relative_path).name
    lowered_name = name.casefold()
    if item.extension in ARCHIVE_EXTENSIONS:
        return _review_finding(
            item,
            plan_id,
            category="inactive_archive",
            kind="review_archive",
            title="Archive file inside Mods",
            explanation="The Sims 4 does not load this archive directly from Mods.",
            bucket="archives",
        )
    if lowered_name == "resource.cfg" and item.relative_path.casefold() != "mods/resource.cfg":
        return _review_finding(
            item,
            plan_id,
            category="duplicate_resource_cfg",
            kind="review_resource_cfg",
            title="Nested Resource.cfg",
            explanation="Only the root Mods/Resource.cfg is expected for normal setup.",
            bucket="resource_cfg",
        )
    if item.extension in SUPPORT_EXTENSIONS or lowered_name in SUPPORT_NAMES:
        return _review_finding(
            item,
            plan_id,
            category="support_file",
            kind="review_support_file",
            title="Support file inside Mods",
            explanation="This file is not an active package or script payload.",
            bucket="support_files",
        )
    if item.extension in TRAY_EXTENSIONS:
        return _review_finding(
            item,
            plan_id,
            category="misplaced_tray",
            kind="review_misplaced_tray",
            title="Likely Tray file inside Mods",
            explanation="Tray files normally belong in the Sims 4 Tray folder, not Mods.",
            bucket="misplaced_tray",
        )
    return None


def _review_finding(
    item: CleanupFile,
    plan_id: str,
    *,
    category: str,
    kind: str,
    title: str,
    explanation: str,
    bucket: str,
) -> dict[str, object]:
    return {
        "finding_id": f"{category}:{item.relative_path}",
        "category": category,
        "severity": "review",
        "title": title,
        "explanation": explanation,
        "evidence": {
            "path": item.relative_path,
            "extension": item.extension,
            "size": item.size,
            "sha256": item.sha256,
        },
        "actions": [
            {
                "action_id": f"{category}:1:{item.relative_path}",
                "kind": kind,
                "source_relative_path": item.relative_path,
                "proposed_destination": _destination(plan_id, bucket, item.relative_path),
                "reason": explanation,
            }
        ],
    }


def _destination(plan_id: str, bucket: str, relative_path: str) -> str:
    return f"_Simanalysis_Cleanup/{plan_id}/{bucket}/{relative_path}"


def _summary(files: list[CleanupFile], findings: list[dict[str, object]]) -> dict[str, int]:
    counts = {
        "files_considered": len(files),
        "finding_count": len(findings),
        "action_count": sum(len(finding["actions"]) for finding in findings),
        "duplicate_groups": 0,
        "archives": 0,
        "duplicate_resource_cfg": 0,
        "support_files": 0,
        "misplaced_tray": 0,
    }
    for finding in findings:
        category = str(finding["category"])
        if category == "exact_duplicate":
            counts["duplicate_groups"] += 1
        elif category == "inactive_archive":
            counts["archives"] += 1
        elif category == "duplicate_resource_cfg":
            counts["duplicate_resource_cfg"] += 1
        elif category == "support_file":
            counts["support_files"] += 1
        elif category == "misplaced_tray":
            counts["misplaced_tray"] += 1
    return counts


def _plan_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cleanup-{digits[:8]}-{digits[8:14]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
```

- [ ] **Step 4: Run the cleanup tests**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-green.coverage .venv/bin/python -m pytest tests/unit/test_cleanup.py -q --no-cov
```

Expected: all tests in `tests/unit/test_cleanup.py` pass.

- [ ] **Step 5: Commit the core service**

```bash
git add src/simanalysis/cleanup.py tests/unit/test_cleanup.py
git commit -m "feat: add read-only cleanup planner"
```

---

### Task 2: Bridge Command And Export Path

**Files:**
- Modify: `src/simanalysis/bridge/__init__.py`
- Modify: `src/simanalysis/bridge/commands.py`
- Modify: `tests/unit/test_bridge_main.py`
- Modify: `tests/unit/test_bridge_commands.py`

- [ ] **Step 1: Write failing parser dispatch test**

Add this test after the inventory command dispatch tests in `tests/unit/test_bridge_main.py`:

```python
def test_cleanup_plan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}
    db_path = tmp_path / "inventory.sqlite3"
    export_path = tmp_path / "cleanup.json"

    def fake_cleanup_plan(args, emit):
        called["path"] = args.path
        called["db"] = args.db
        called["export"] = args.export
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "cleanup-plan", fake_cleanup_plan)

    code, events = _run(
        monkeypatch,
        [
            "cleanup-plan",
            str(tmp_path),
            "--db",
            str(db_path),
            "--export",
            str(export_path),
        ],
    )

    assert code == 0
    assert called == {
        "path": str(tmp_path),
        "db": str(db_path),
        "export": str(export_path),
    }
    assert [event["type"] for event in events] == ["result", "done"]
```

- [ ] **Step 2: Write failing bridge command behavior tests**

Add these tests near the inventory bridge command tests in `tests/unit/test_bridge_commands.py`:

```python
def test_cleanup_plan_emits_latest_plan_without_export(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.zip").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), export=None)
    commands.cleanup_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert result["root_path"] == str(sims4.resolve())
    assert result["db_path"] == str(db_path)
    assert result["summary"]["archives"] == 1
    assert not (sims4 / "_Simanalysis_Cleanup").exists()


def test_cleanup_plan_command_exports_only_when_requested(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.zip").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    export_path = tmp_path / "cleanup-plan.json"
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), export=str(export_path))
    commands.cleanup_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert export_path.exists()
    assert json.loads(export_path.read_text(encoding="utf-8")) == result
```

- [ ] **Step 3: Run bridge tests to verify they fail**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-bridge-red.coverage .venv/bin/python -m pytest \
  tests/unit/test_bridge_main.py::test_cleanup_plan_command_is_dispatched \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_emits_latest_plan_without_export \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_command_exports_only_when_requested \
  -q --no-cov
```

Expected: FAIL because `cleanup-plan` parser and `commands.cleanup_plan` do not exist.

- [ ] **Step 4: Add parser support**

In `src/simanalysis/bridge/__init__.py`, after the inventory file-events parser block, add:

```python
    p_cleanup_plan = sub.add_parser("cleanup-plan")
    p_cleanup_plan.add_argument("path")
    p_cleanup_plan.add_argument("--db", default=None)
    p_cleanup_plan.add_argument("--export", default=None)
```

- [ ] **Step 5: Add bridge command handler**

In `src/simanalysis/bridge/commands.py`, add the import:

```python
from simanalysis.cleanup import CleanupPlanner
```

Add this function after `inventory_file_events`:

```python
def cleanup_plan(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    db_path = Path(args.db).expanduser() if args.db else default_inventory_db_path()
    planner = CleanupPlanner(db_path)

    emit.start("cleanup-plan")
    if args.export:
        result = planner.export_plan(path, Path(args.export))
    else:
        result = planner.plan(path)
    emit.result(result)
    emit.done()
```

Add the dispatch entry:

```python
    "cleanup-plan": cleanup_plan,
```

- [ ] **Step 6: Run bridge tests**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-bridge-green.coverage .venv/bin/python -m pytest \
  tests/unit/test_bridge_main.py::test_cleanup_plan_command_is_dispatched \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_emits_latest_plan_without_export \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_command_exports_only_when_requested \
  -q --no-cov
```

Expected: all three tests pass.

- [ ] **Step 7: Commit bridge command**

```bash
git add src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
git commit -m "feat: expose cleanup planner bridge command"
```

---

### Task 3: Tauri And Web Non-Visual API Plumbing

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Modify: `web/src/api.js`
- Create: `web/src/cleanupApiModel.js`
- Create: `web/src/cleanupApiModel.test.js`

- [ ] **Step 1: Write failing Tauri argument test**

In `src-tauri/src/lib.rs`, add this test near the inventory argument tests:

```rust
    #[test]
    fn builds_cleanup_plan_args_with_db_and_export() {
        let opts = AnalysisOptions {
            db: Some("/Sims/inventory.sqlite3".into()),
            export_path: Some("/tmp/cleanup-plan.json".into()),
            ..Default::default()
        };
        let args = build_args("cleanup-plan", "/Sims/The Sims 4", &opts).unwrap();
        assert_eq!(
            args,
            vec![
                "cleanup-plan",
                "/Sims/The Sims 4",
                "--db",
                "/Sims/inventory.sqlite3",
                "--export",
                "/tmp/cleanup-plan.json",
            ]
        );
    }
```

- [ ] **Step 2: Run the focused Tauri test to verify it fails**

Run:

```bash
cargo test builds_cleanup_plan_args_with_db_and_export --manifest-path src-tauri/Cargo.toml
```

Expected: FAIL because `AnalysisOptions` has no `export_path` field or `cleanup-plan` match arm.

- [ ] **Step 3: Implement Tauri argument builder**

In `src-tauri/src/lib.rs`, add the field to `AnalysisOptions`:

```rust
    #[serde(default)]
    export_path: Option<String>,
```

Add this match arm to `build_args` after the inventory commands:

```rust
        "cleanup-plan" => {
            args.push("cleanup-plan".into());
            args.push(path.into());
            if let Some(db) = opts.db.as_deref() {
                args.push("--db".into());
                args.push(db.into());
            }
            if let Some(export_path) = opts.export_path.as_deref() {
                args.push("--export".into());
                args.push(export_path.into());
            }
        }
```

- [ ] **Step 4: Run the focused Tauri test**

Run:

```bash
cargo test builds_cleanup_plan_args_with_db_and_export --manifest-path src-tauri/Cargo.toml
```

Expected: PASS.

- [ ] **Step 5: Write failing web options tests**

Create `web/src/cleanupApiModel.test.js`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';

import { cleanupPlanOptions } from './cleanupApiModel.js';

test('cleanup plan options are empty by default', () => {
    assert.deepEqual(cleanupPlanOptions(), {});
});

test('cleanup plan includes explicit database and export paths', () => {
    assert.deepEqual(
        cleanupPlanOptions({
            db: '/tmp/inventory.sqlite3',
            exportPath: '/tmp/cleanup-plan.json',
        }),
        {
            db: '/tmp/inventory.sqlite3',
            exportPath: '/tmp/cleanup-plan.json',
        },
    );
});
```

- [ ] **Step 6: Run the web options test to verify it fails**

Run:

```bash
node --test web/src/cleanupApiModel.test.js
```

Expected: FAIL because `web/src/cleanupApiModel.js` does not exist.

- [ ] **Step 7: Implement web options helper and API wrapper**

Create `web/src/cleanupApiModel.js`:

```javascript
export function cleanupPlanOptions(options = {}) {
    const result = {};
    if (options.db) {
        result.db = options.db;
    }
    if (options.exportPath) {
        result.exportPath = options.exportPath;
    }
    return result;
}
```

In `web/src/api.js`, add the import:

```javascript
import { cleanupPlanOptions } from './cleanupApiModel';
```

Add the API method near the inventory methods:

```javascript
  cleanupPlan: (sims4Path, callbacks, options = {}) =>
    runAnalysis('cleanup-plan', sims4Path, cleanupPlanOptions(options), callbacks),
```

- [ ] **Step 8: Run web tests**

Run:

```bash
node --test web/src/cleanupApiModel.test.js web/src/inventoryApiModel.test.js web/src/liveMonitorModel.test.js
```

Expected: all tests pass.

- [ ] **Step 9: Commit Tauri/web plumbing**

```bash
git add src-tauri/src/lib.rs web/src/api.js web/src/cleanupApiModel.js web/src/cleanupApiModel.test.js
git commit -m "feat: add cleanup planner api plumbing"
```

---

### Task 4: Documentation And Full Verification

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `IMPLEMENTATION_STATUS.md`
- Modify: `docs/STATUS.md`

- [ ] **Step 1: Update changelog**

In `CHANGELOG.md`, under `## [Unreleased]` > `### Added`, add:

```markdown
- Added a read-only Mods cleanup planner plus bridge/Tauri/web API `cleanup-plan` plumbing that consumes the inventory database and emits review-only findings for exact duplicates, inactive archives, nested `Resource.cfg`, support files, and misplaced Tray files without moving Sims files.
```

- [ ] **Step 2: Update implementation status**

In `IMPLEMENTATION_STATUS.md`, add a short Cleanup Planner progress section after the Ledger section:

```markdown
## Cleanup Planner Progress

Implemented on this branch after the inventory ledger:

- Added `src/simanalysis/cleanup.py`, a read-only planner that consumes the latest inventory snapshot.
- The planner is scoped to `Mods` files and reports exact duplicates, inactive archives, nested `Resource.cfg`, support files, and misplaced Tray files.
- Plans include proposed future destinations but do not create `_Simanalysis_Cleanup`, move files, or write Sims-folder manifests.
- The desktop bridge and Tauri/web API plumbing expose `cleanup-plan`; the visual cleanup route remains future work.
```

- [ ] **Step 3: Update status index**

In `docs/STATUS.md`, update the current branch note to mention `cleanup-plan`:

```markdown
Current branch note: the read-only SQLite inventory ledger now records scan
history plus per-file change events in `src/simanalysis/inventory.py`; the
bridge/Tauri/web API exposes `inventory-scan`, `inventory-history`, and
`inventory-file-events`. The read-only Cleanup Planner v1 adds `cleanup-plan`
for Mods-folder review findings. Visual inventory and cleanup routes remain
pending design approval.
```

- [ ] **Step 4: Run targeted cleanup and bridge tests**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-targeted.coverage .venv/bin/python -m pytest \
  tests/unit/test_cleanup.py \
  tests/unit/test_bridge_main.py::test_cleanup_plan_command_is_dispatched \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_emits_latest_plan_without_export \
  tests/unit/test_bridge_commands.py::test_cleanup_plan_command_exports_only_when_requested \
  -q --no-cov
```

Expected: cleanup service tests and cleanup bridge tests pass.

- [ ] **Step 5: Run Python lint, format, and type checks**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
```

Expected: all commands exit 0.

- [ ] **Step 6: Run real-fixture and full Python tests**

Run:

```bash
COVERAGE_FILE=/tmp/simanalysis-cleanup-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-cleanup-full.coverage .venv/bin/python -m pytest -q
```

Expected: real fixture tests pass, then full pytest passes.

- [ ] **Step 7: Run Rust and web checks**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
node --test web/src/cleanupApiModel.test.js web/src/inventoryApiModel.test.js web/src/liveMonitorModel.test.js
npm --prefix web run lint
npm --prefix web run build
```

Expected: all commands exit 0. Existing stale Browserslist or baseline warnings may appear during web build; do not treat them as failures unless the command exits non-zero.

- [ ] **Step 8: Run diff and status checks**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits 0. `git status --short` shows only the intended modified files before committing.

- [ ] **Step 9: Commit verified cleanup planner slice**

```bash
git add CHANGELOG.md IMPLEMENTATION_STATUS.md docs/STATUS.md src/simanalysis/cleanup.py src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_cleanup.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py src-tauri/src/lib.rs web/src/api.js web/src/cleanupApiModel.js web/src/cleanupApiModel.test.js
git commit -m "feat: add cleanup planner"
```

Expected: commit succeeds. After committing, `git status --short --branch` should show a clean branch.

---

## Spec Coverage Self-Review

- Latest inventory snapshot: Task 1 loads latest `snapshots` and `snapshot_files` rows by root path.
- Mods-only scope: Task 1 filters to `Mods/` and tests outside-`Mods` ignore behavior.
- Exact duplicates: Task 1 groups by `(sha256, size)`, chooses a stable keep candidate, and emits `review_duplicate`.
- Archives: Task 1 flags `.zip`, `.rar`, and `.7z` as `review_archive`.
- Duplicate `Resource.cfg`: Task 1 flags nested `Resource.cfg` while allowing root `Mods/Resource.cfg`.
- Support files: Task 1 flags previews, notes/docs, shortcuts, and metadata.
- Misplaced Tray files: Task 1 flags Tray extensions inside `Mods`.
- JSON plan/export: Task 1 implements `export_plan`; Task 2 exposes `--export`; tests prove explicit export only.
- Read-only safety: Task 1 tests no `_Simanalysis_Cleanup` creation or Sims-folder mutation; Task 2 and Task 4 keep bridge/API non-visual.
- Bridge command: Task 2 adds `cleanup-plan` parser, handler, and dispatch tests.
- Tauri/web wrappers: Task 3 adds thin non-visual argument plumbing.
- Verification: Task 4 covers targeted tests, lint, type checks, real fixtures, full pytest, Rust tests, web tests/lint/build, diff check, and final commit.
