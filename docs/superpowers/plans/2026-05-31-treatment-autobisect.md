# Treatment + Auto-Bisect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Assisted Auto-Bisect v1: a dry-run-first, reversible desktop workflow that turns active Doctor findings into safe mod-batch test steps.

**Architecture:** Add a pure Python treatment service that extracts active candidates from Doctor JSON, groups them by movable top-level `Mods` unit, persists session manifests only when requested, and applies/restores moves through strict path and process guards. Expose that service through `simanalysis-bridge` NDJSON commands, route them through Tauri's existing sidecar command runner, and add a compact React Treatment view that guides the user through plan -> start session -> apply step -> record result -> restore.

**Tech Stack:** Python 3.9+ stdlib (`dataclasses`, `json`, `shutil`, `subprocess`, `datetime`, `pathlib`), existing Simanalysis analyzers/bridge protocol, pytest, Rust/Tauri command argument builder, React 18 + Vite + lucide-react. Spec: `docs/superpowers/specs/2026-05-30-treatment-autobisect-design.md`.

---

## File Structure

- Create `src/simanalysis/treatment.py` — pure service for candidate extraction, dry-run plans, manifest persistence, path guards, move/restore, and outcome transitions.
- Modify `src/simanalysis/bridge/commands.py` — add treatment command handlers and refactor Doctor payload construction into a reusable helper.
- Modify `src/simanalysis/bridge/__init__.py` — add argparse subcommands for `treatment-plan`, `treatment-apply`, `treatment-outcome`, `treatment-restore`, and `treatment-status`.
- Create `tests/unit/test_treatment.py` — unit coverage for planning, guards, manifest write behavior, moves, restore, and outcomes.
- Modify `tests/unit/test_bridge_commands.py` and `tests/unit/test_bridge_main.py` — command output shape and parser dispatch.
- Modify `src-tauri/src/lib.rs` — extend sidecar arg construction for treatment commands and add Rust unit tests.
- Modify `web/src/api.js` — add Treatment API methods over the existing `runAnalysis` transport.
- Modify `web/src/App.jsx` and `web/src/components/Sidebar.jsx` — add `/treatment` route and sidebar item.
- Create `web/src/views/Treatment.jsx` — guided Treatment workflow.
- Modify `web/src/views/Doctor.jsx` — add link/button to Treatment when active findings exist.
- Create `docs/superpowers/2026-05-31-treatment-autobisect-validation.md` — real-folder dry-run validation notes.

## Implementation Notes

- Do not mutate the real Sims folder during automated validation. Real-folder validation is `treatment-plan` without `--save`.
- Keep all mutation tests inside `tmp_path`.
- `treatment-plan` without `--save` must not create `_Simanalysis_Treatment`.
- A saved session manifest is required before `apply`, `outcome`, `restore`, or `status` can mutate or inspect a session.
- For script Doctor findings, use `script_crashes.ranked_mods[*].mod` to locate an active `.ts4script` filename under `Mods`. The raw traceback evidence is not a user filesystem path.
- For UI Doctor findings, use `ui_crashes.findings[*].hits[*].package_path` when `finding.status == "active"` and `hit.status == "active"`.
- Unit boundaries are always direct children of `Mods`: direct file stays file; nested file maps to first-level folder.
- Path guards must reject symlinks, path escapes, missing sources, and existing destinations.
- The Sims process guard is required for apply/restore/outcome moves. In tests, monkeypatch it; do not depend on the host process list.

---

## Task 1: Core Planner and Candidate Extraction

**Files:**
- Create: `src/simanalysis/treatment.py`
- Create: `tests/unit/test_treatment.py`

- [ ] **Step 1: Write failing tests for read-only planning**

Create `tests/unit/test_treatment.py` with these tests:

```python
from __future__ import annotations

from pathlib import Path

from simanalysis.treatment import create_plan, unit_for_path


def _doctor_payload(ui_path: Path, script_name: str = "Active.ts4script") -> dict:
    return {
        "summary": {"script_active": 1, "ui_active": 1},
        "script_crashes": {
            "ranked_mods": [
                {
                    "mod": script_name,
                    "status": "active",
                    "confidence": "high",
                    "top_suspect_count": 2,
                    "crash_count": 2,
                },
                {
                    "mod": "Disabled.ts4script",
                    "status": "disabled",
                    "confidence": "high",
                    "top_suspect_count": 10,
                    "crash_count": 10,
                },
            ],
            "findings": [],
            "parse_errors": [],
        },
        "ui_crashes": {
            "findings": [
                {
                    "status": "active",
                    "reason": "key found in active package",
                    "report": {"source_file": "lastUIException.txt", "signature": "ui-sig"},
                    "hits": [
                        {
                            "status": "active",
                            "package_name": "menu.package",
                            "package_path": str(ui_path),
                        },
                        {
                            "status": "disabled",
                            "package_name": "old.package",
                            "package_path": str(ui_path.parent.parent / "_Disabled" / "old.package"),
                        },
                    ],
                },
                {
                    "status": "not_found",
                    "reason": "key not found",
                    "report": {"source_file": "lastUIException.txt", "signature": "missing"},
                    "hits": [],
                },
            ],
            "parse_errors": [],
            "index_errors": [],
        },
    }


def test_unit_for_path_uses_top_level_mods_child(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    nested = mods / "Creator" / "Nested" / "menu.package"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b"x")

    unit = unit_for_path(nested, mods)

    assert unit is not None
    assert unit.unit_path == str(mods / "Creator")
    assert unit.unit_name == "Creator"
    assert unit.unit_kind == "folder"


def test_unit_for_path_keeps_direct_file_as_unit(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()
    direct = mods / "Standalone.ts4script"
    direct.write_bytes(b"x")

    unit = unit_for_path(direct, mods)

    assert unit is not None
    assert unit.unit_path == str(direct)
    assert unit.unit_name == "Standalone.ts4script"
    assert unit.unit_kind == "file"


def test_create_plan_collects_only_active_doctor_candidates_without_writing(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    ui_pkg = mods / "Creator" / "menu.package"
    script = mods / "Scripts" / "Active.ts4script"
    ui_pkg.parent.mkdir(parents=True)
    script.parent.mkdir(parents=True)
    ui_pkg.write_bytes(b"package")
    script.write_bytes(b"script")

    plan = create_plan(sims4, mods, _doctor_payload(ui_pkg), save=False)

    assert plan["manifest_path"] is None
    assert not (sims4 / "_Simanalysis_Treatment").exists()
    assert [c["unit_name"] for c in plan["active_candidates"]] == ["Creator", "Scripts"]
    assert plan["next_batch"] == [str(mods / "Creator")]
    assert plan["status"] == "planned"
    assert plan["warnings"] == []
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: import failure for `simanalysis.treatment`.

- [ ] **Step 3: Implement planner models and candidate extraction**

Create `src/simanalysis/treatment.py`:

```python
"""Safe Treatment + Auto-Bisect planning and session operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SESSION_ROOT_NAME = "_Simanalysis_Treatment"
DISABLED_PREFIX = "_Disabled_Simanalysis_Bisect_"
VALID_OUTCOMES = {"same_issue", "issue_gone", "different_issue"}


@dataclass(frozen=True)
class Evidence:
    source: str
    finding: str
    reason: str
    path: str


@dataclass(frozen=True)
class TreatmentCandidate:
    unit_path: str
    unit_name: str
    unit_kind: str
    evidence: list[Evidence] = field(default_factory=list)
    rank: int = 100


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_for(dt: datetime) -> str:
    return dt.strftime("%Y%m%d-%H%M%S")


def unit_for_path(path: str | Path, mods_dir: str | Path) -> TreatmentCandidate | None:
    mods = Path(mods_dir).expanduser().resolve()
    candidate_path = Path(path).expanduser()
    try:
        resolved = candidate_path.resolve(strict=True)
    except FileNotFoundError:
        return None

    try:
        rel = resolved.relative_to(mods)
    except ValueError:
        return None
    if not rel.parts:
        return None

    first = mods / rel.parts[0]
    if not first.exists():
        return None
    return TreatmentCandidate(
        unit_path=str(first),
        unit_name=first.name,
        unit_kind="folder" if first.is_dir() else "file",
    )


def _merge_candidate(
    by_path: dict[str, TreatmentCandidate],
    unit: TreatmentCandidate,
    evidence: Evidence,
    rank: int,
) -> None:
    current = by_path.get(unit.unit_path)
    if current is None:
        by_path[unit.unit_path] = TreatmentCandidate(
            unit_path=unit.unit_path,
            unit_name=unit.unit_name,
            unit_kind=unit.unit_kind,
            evidence=[evidence],
            rank=rank,
        )
        return
    by_path[unit.unit_path] = TreatmentCandidate(
        unit_path=current.unit_path,
        unit_name=current.unit_name,
        unit_kind=current.unit_kind,
        evidence=[*current.evidence, evidence],
        rank=min(current.rank, rank),
    )


def _confidence_rank(confidence: str | None) -> int:
    if confidence == "high":
        return 20
    if confidence == "medium":
        return 30
    return 40


def _find_active_script(mods_dir: Path, mod_name: str) -> Path | None:
    target = mod_name.casefold()
    for path in mods_dir.rglob("*.ts4script"):
        if path.name.casefold() == target:
            return path
    return None


def candidates_from_doctor(doctor_payload: dict[str, Any], mods_dir: str | Path) -> list[TreatmentCandidate]:
    mods = Path(mods_dir).expanduser().resolve()
    by_path: dict[str, TreatmentCandidate] = {}

    for finding in doctor_payload.get("ui_crashes", {}).get("findings", []):
        if finding.get("status") != "active":
            continue
        report = finding.get("report") or {}
        for hit in finding.get("hits", []):
            if hit.get("status") != "active" or not hit.get("package_path"):
                continue
            unit = unit_for_path(hit["package_path"], mods)
            if unit is None:
                continue
            _merge_candidate(
                by_path,
                unit,
                Evidence(
                    source="ui",
                    finding=str(report.get("source_file") or report.get("signature") or "ui finding"),
                    reason=str(finding.get("reason") or "active package hit"),
                    path=str(hit["package_path"]),
                ),
                10,
            )

    for ranked in doctor_payload.get("script_crashes", {}).get("ranked_mods", []):
        if ranked.get("status") != "active" or not ranked.get("mod"):
            continue
        script_path = _find_active_script(mods, str(ranked["mod"]))
        if script_path is None:
            continue
        unit = unit_for_path(script_path, mods)
        if unit is None:
            continue
        confidence = ranked.get("confidence")
        _merge_candidate(
            by_path,
            unit,
            Evidence(
                source="script",
                finding=str(ranked["mod"]),
                reason=f"active script suspect ({confidence or 'unknown'} confidence)",
                path=str(script_path),
            ),
            _confidence_rank(confidence),
        )

    return sorted(by_path.values(), key=lambda c: (c.rank, c.unit_name.casefold()))


def _base_plan(
    sims4_dir: Path,
    mods_dir: Path,
    doctor_payload: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    candidates = candidates_from_doctor(doctor_payload, mods_dir) if mods_dir.exists() else []
    ts = timestamp_for(now)
    remaining = [candidate.unit_path for candidate in candidates]
    batch_size = (len(remaining) + 1) // 2 if len(remaining) > 1 else len(remaining)
    warnings: list[str] = []
    if not mods_dir.exists():
        warnings.append(f"Mods folder does not exist: {mods_dir}")
    if not candidates:
        warnings.append("No active Doctor candidates can be moved.")

    return {
        "version": 1,
        "session_id": f"bisect-{ts}",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "sims4_dir": str(sims4_dir),
        "mods_dir": str(mods_dir),
        "disabled_dir": str(sims4_dir / f"{DISABLED_PREFIX}{ts}"),
        "manifest_path": None,
        "status": "planned",
        "active_candidates": [asdict(candidate) for candidate in candidates],
        "remaining_candidates": remaining,
        "current_removed": [],
        "next_batch": remaining[:batch_size],
        "steps": [],
        "warnings": warnings,
        "blockers": [],
    }


def create_plan(
    sims4_dir: str | Path,
    mods_dir: str | Path | None,
    doctor_payload: dict[str, Any],
    *,
    save: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = Path(sims4_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Invalid Sims 4 directory path: {sims4_dir}")
    mods = Path(mods_dir).expanduser().resolve() if mods_dir else base / "Mods"
    plan = _base_plan(base, mods, doctor_payload, now=now or utc_now())
    if save:
        # Implemented in Task 2.
        raise NotImplementedError("saved treatment sessions are implemented in Task 2")
    return plan
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/simanalysis/treatment.py tests/unit/test_treatment.py
git commit -m "feat: add treatment dry-run planner"
```

---

## Task 2: Manifest Persistence and Mutation Guards

**Files:**
- Modify: `src/simanalysis/treatment.py`
- Modify: `tests/unit/test_treatment.py`

- [ ] **Step 1: Add failing tests for save behavior and guards**

Append to `tests/unit/test_treatment.py`:

```python
import json

import pytest

from simanalysis.treatment import (
    assert_safe_unit_move,
    contains_symlink,
    create_plan,
    load_session,
)


def test_create_plan_with_save_writes_manifest(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pkg = mods / "Creator" / "menu.package"
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b"x")

    plan = create_plan(sims4, mods, _doctor_payload(pkg), save=True)

    manifest = Path(plan["manifest_path"])
    assert manifest.exists()
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert saved["status"] == "planned"
    assert saved["manifest_path"] == str(manifest)
    assert saved["active_candidates"][0]["unit_name"] == "Creator"


def test_load_session_rejects_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Manifest not found"):
        load_session(tmp_path / "missing.json")


def test_assert_safe_unit_move_rejects_symlink(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    mods.mkdir(parents=True)
    target = tmp_path / "outside"
    target.mkdir()
    link = mods / "LinkOut"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        assert_safe_unit_move(link, disabled / "LinkOut", mods, disabled)


def test_assert_safe_unit_move_rejects_destination_collision(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    disabled = sims4 / "_Disabled_Simanalysis_Bisect_20260531-010203"
    source = mods / "Creator"
    dest = disabled / "Creator"
    source.mkdir(parents=True)
    dest.mkdir(parents=True)

    with pytest.raises(ValueError, match="Destination already exists"):
        assert_safe_unit_move(source, dest, mods, disabled)


def test_contains_symlink_detects_nested_symlink(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "link").symlink_to(tmp_path)

    assert contains_symlink(root) is True
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: missing `load_session`, `assert_safe_unit_move`, `contains_symlink`, and saved-session implementation failures.

- [ ] **Step 3: Implement manifest persistence and path guards**

Extend `src/simanalysis/treatment.py` with these imports:

```python
import json
```

Add these functions below `create_plan` helpers, then update `create_plan(save=True)` to call `_write_session`:

```python
def manifest_path_for(sims4_dir: Path, session_id: str) -> Path:
    return sims4_dir / SESSION_ROOT_NAME / f"{session_id}.json"


def _write_session(session: dict[str, Any]) -> dict[str, Any]:
    path = Path(session["manifest_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session


def load_session(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {manifest_path}") from exc
    if data.get("version") != 1:
        raise ValueError("Unsupported treatment manifest version")
    required = {"session_id", "sims4_dir", "mods_dir", "disabled_dir", "status", "steps"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Manifest is missing required keys: {', '.join(sorted(missing))}")
    data["manifest_path"] = str(path)
    return data


def contains_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    if path.is_dir():
        return any(child.is_symlink() for child in path.rglob("*"))
    return False


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_safe_unit_move(source: Path, destination: Path, mods_dir: Path, disabled_dir: Path) -> None:
    mods = mods_dir.expanduser().resolve()
    disabled = disabled_dir.expanduser().resolve()
    if not source.exists():
        raise ValueError(f"Source path is missing: {source}")
    if contains_symlink(source):
        raise ValueError(f"Refusing to move symlinked unit: {source}")
    resolved_source = source.expanduser().resolve(strict=True)
    if resolved_source.parent != mods:
        raise ValueError(f"Source must be a direct child of Mods: {source}")
    resolved_destination_parent = destination.parent.expanduser().resolve()
    if resolved_destination_parent != disabled:
        raise ValueError(f"Destination must be inside active disabled folder: {destination}")
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    if not _is_relative_to(resolved_source, mods):
        raise ValueError(f"Source escapes Mods folder: {source}")
```

Replace the `save` branch in `create_plan`:

```python
    if save:
        manifest = manifest_path_for(base, plan["session_id"])
        plan["manifest_path"] = str(manifest)
        return _write_session(plan)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: all treatment tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/simanalysis/treatment.py tests/unit/test_treatment.py
git commit -m "feat: persist treatment manifests safely"
```

---

## Task 3: Apply, Restore, and Outcome Transitions

**Files:**
- Modify: `src/simanalysis/treatment.py`
- Modify: `tests/unit/test_treatment.py`

- [ ] **Step 1: Add failing tests for mutation and bisect transitions**

Append to `tests/unit/test_treatment.py`:

```python
from simanalysis.treatment import apply_next_step, record_outcome, restore_session


def test_apply_next_step_moves_first_half_and_updates_manifest(tmp_path: Path, monkeypatch) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    a = mods / "A" / "a.package"
    b = mods / "B" / "b.package"
    c = mods / "C" / "Active.ts4script"
    for path in (a, b, c):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    payload = _doctor_payload(a)
    payload["ui_crashes"]["findings"][0]["hits"].append(
        {"status": "active", "package_name": "b.package", "package_path": str(b)}
    )
    payload["script_crashes"]["ranked_mods"][0]["mod"] = "Active.ts4script"
    session = create_plan(sims4, mods, payload, save=True)
    monkeypatch.setattr("simanalysis.treatment.assert_sims_not_running", lambda: None)

    result = apply_next_step(session["manifest_path"])

    assert result["status"] == "awaiting_result"
    assert not (mods / "A").exists()
    assert not (mods / "B").exists()
    assert (mods / "C").exists()
    assert len(result["current_removed"]) == 2
    assert result["steps"][0]["status"] == "applied"


def test_record_same_issue_restores_removed_batch_and_narrows_to_other_half(tmp_path: Path, monkeypatch) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    a = mods / "A" / "a.package"
    b = mods / "B" / "b.package"
    for path in (a, b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    payload = _doctor_payload(a, script_name="Missing.ts4script")
    payload["ui_crashes"]["findings"][0]["hits"].append(
        {"status": "active", "package_name": "b.package", "package_path": str(b)}
    )
    session = create_plan(sims4, mods, payload, save=True)
    monkeypatch.setattr("simanalysis.treatment.assert_sims_not_running", lambda: None)

    applied = apply_next_step(session["manifest_path"])
    result = record_outcome(applied["manifest_path"], "same_issue")

    assert result["status"] == "confirmed_candidate"
    assert result["remaining_candidates"] == [str(mods / "B")]
    assert (mods / "A").exists()
    assert result["current_removed"] == []
    assert result["steps"][0]["outcome"] == "same_issue"


def test_record_issue_gone_keeps_removed_batch_as_remaining(tmp_path: Path, monkeypatch) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    a = mods / "A" / "a.package"
    b = mods / "B" / "b.package"
    for path in (a, b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    payload = _doctor_payload(a, script_name="Missing.ts4script")
    payload["ui_crashes"]["findings"][0]["hits"].append(
        {"status": "active", "package_name": "b.package", "package_path": str(b)}
    )
    session = create_plan(sims4, mods, payload, save=True)
    monkeypatch.setattr("simanalysis.treatment.assert_sims_not_running", lambda: None)

    applied = apply_next_step(session["manifest_path"])
    result = record_outcome(applied["manifest_path"], "issue_gone")

    assert result["status"] == "confirmed_candidate"
    assert result["remaining_candidates"] == [str(mods / "A")]
    assert not (mods / "A").exists()
    assert result["current_removed"] == [str(mods / "A")]


def test_restore_latest_step_moves_units_back(tmp_path: Path, monkeypatch) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pkg = mods / "Creator" / "menu.package"
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b"x")
    session = create_plan(sims4, mods, _doctor_payload(pkg, script_name="Missing.ts4script"), save=True)
    monkeypatch.setattr("simanalysis.treatment.assert_sims_not_running", lambda: None)
    applied = apply_next_step(session["manifest_path"])

    restored = restore_session(applied["manifest_path"], step="latest")

    assert restored["status"] == "planned"
    assert (mods / "Creator").exists()
    assert restored["current_removed"] == []
    assert restored["steps"][0]["status"] == "restored"


def test_different_issue_marks_manual_review(tmp_path: Path, monkeypatch) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    pkg = mods / "Creator" / "menu.package"
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b"x")
    session = create_plan(sims4, mods, _doctor_payload(pkg, script_name="Missing.ts4script"), save=True)
    monkeypatch.setattr("simanalysis.treatment.assert_sims_not_running", lambda: None)
    applied = apply_next_step(session["manifest_path"])

    result = record_outcome(applied["manifest_path"], "different_issue")

    assert result["status"] == "manual_review"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: missing apply/outcome/restore functions.

- [ ] **Step 3: Implement mutation functions**

Extend imports in `src/simanalysis/treatment.py`:

```python
import shutil
import subprocess
```

Add these functions:

```python
def assert_sims_not_running() -> None:
    names = {"the sims 4", "the sims 4.app", "ts4_x64.exe", "ts4_dx9_x64.exe"}
    try:
        proc = subprocess.run(
            ["ps", "-axo", "comm="],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        raise ValueError("Cannot verify whether The Sims 4 is running; refusing to move files") from exc
    running = {Path(line.strip()).name.casefold() for line in proc.stdout.splitlines() if line.strip()}
    if running & names:
        raise ValueError("The Sims 4 appears to be running; close it before moving mods")


def _save_loaded(session: dict[str, Any]) -> dict[str, Any]:
    session["updated_at"] = utc_now().isoformat().replace("+00:00", "Z")
    return _write_session(session)


def _candidate_by_path(session: dict[str, Any], unit_path: str) -> dict[str, Any]:
    for candidate in session.get("active_candidates", []):
        if candidate["unit_path"] == unit_path:
            return candidate
    raise ValueError(f"Candidate not found in manifest: {unit_path}")


def _next_batch(session: dict[str, Any]) -> list[str]:
    remaining = list(session.get("remaining_candidates", []))
    if len(remaining) <= 1:
        return []
    batch_size = (len(remaining) + 1) // 2
    return remaining[:batch_size]


def _move_records_for(session: dict[str, Any], unit_paths: list[str]) -> list[dict[str, Any]]:
    disabled_dir = Path(session["disabled_dir"])
    records = []
    for unit_path in unit_paths:
        candidate = _candidate_by_path(session, unit_path)
        source = Path(candidate["unit_path"])
        records.append(
            {
                "source": str(source),
                "destination": str(disabled_dir / source.name),
                "unit_kind": candidate["unit_kind"],
                "status": "pending",
            }
        )
    return records


def apply_next_step(manifest_path: str | Path) -> dict[str, Any]:
    assert_sims_not_running()
    session = load_session(manifest_path)
    if session.get("current_removed"):
        raise ValueError("Record the current step outcome before applying another step")
    batch = _next_batch(session)
    if not batch:
        session["status"] = "confirmed_candidate" if session.get("remaining_candidates") else "inconclusive"
        return _save_loaded(session)

    step = {
        "step_id": len(session.get("steps", [])) + 1,
        "created_at": utc_now().isoformat().replace("+00:00", "Z"),
        "status": "pending",
        "reason": "bisect first half",
        "removed_units": _move_records_for(session, batch),
        "outcome": None,
    }
    session.setdefault("steps", []).append(step)
    _save_loaded(session)

    mods = Path(session["mods_dir"]).expanduser().resolve()
    disabled = Path(session["disabled_dir"]).expanduser().resolve()
    disabled.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for record in step["removed_units"]:
        source = Path(record["source"])
        destination = Path(record["destination"])
        try:
            assert_safe_unit_move(source, destination, mods, disabled)
            shutil.move(str(source), str(destination))
            record["status"] = "moved"
            moved.append(record["source"])
            session["current_removed"] = moved
            step["status"] = "applied"
            session["status"] = "awaiting_result"
            _save_loaded(session)
        except Exception:
            record["status"] = "blocked"
            step["status"] = "blocked"
            session["status"] = "blocked"
            _save_loaded(session)
            raise
    session["next_batch"] = []
    return _save_loaded(session)


def _restore_records(records: list[dict[str, Any]], mods_dir: Path, disabled_dir: Path) -> None:
    for record in records:
        if record.get("status") not in {"moved", "kept_disabled"}:
            continue
        source = Path(record["destination"])
        destination = Path(record["source"])
        if not source.exists():
            raise ValueError(f"Disabled unit is missing: {source}")
        if destination.exists():
            raise ValueError(f"Restore destination already exists: {destination}")
        if source.is_symlink() or contains_symlink(source):
            raise ValueError(f"Refusing to restore symlinked unit: {source}")
        if destination.parent.resolve() != mods_dir:
            raise ValueError(f"Restore destination must be a direct child of Mods: {destination}")
        if source.parent.resolve() != disabled_dir:
            raise ValueError(f"Restore source must be inside active disabled folder: {source}")
        shutil.move(str(source), str(destination))
        record["status"] = "restored"


def _latest_step(session: dict[str, Any]) -> dict[str, Any]:
    steps = session.get("steps", [])
    if not steps:
        raise ValueError("No treatment steps have been applied")
    return steps[-1]


def restore_session(manifest_path: str | Path, *, step: str = "latest") -> dict[str, Any]:
    assert_sims_not_running()
    session = load_session(manifest_path)
    mods = Path(session["mods_dir"]).expanduser().resolve()
    disabled = Path(session["disabled_dir"]).expanduser().resolve()
    steps = session.get("steps", []) if step == "all" else [_latest_step(session)]
    for item in reversed(steps):
        _restore_records(item.get("removed_units", []), mods, disabled)
        item["status"] = "restored"
    session["current_removed"] = []
    session["status"] = "planned"
    remaining = list(session.get("remaining_candidates", []))
    batch_size = (len(remaining) + 1) // 2 if len(remaining) > 1 else len(remaining)
    session["next_batch"] = remaining[:batch_size]
    return _save_loaded(session)


def _finalize_status(session: dict[str, Any]) -> None:
    remaining = session.get("remaining_candidates", [])
    if len(remaining) == 1:
        session["status"] = "confirmed_candidate"
    elif len(remaining) == 0:
        session["status"] = "inconclusive"
    else:
        session["status"] = "planned"
    batch_size = (len(remaining) + 1) // 2 if len(remaining) > 1 else len(remaining)
    session["next_batch"] = remaining[:batch_size]


def record_outcome(manifest_path: str | Path, outcome: str) -> dict[str, Any]:
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Invalid treatment outcome: {outcome}")
    assert_sims_not_running()
    session = load_session(manifest_path)
    step = _latest_step(session)
    if step.get("status") != "applied":
        raise ValueError("Latest treatment step is not awaiting an outcome")
    step["outcome"] = outcome

    removed = list(session.get("current_removed", []))
    if outcome == "different_issue":
        session["status"] = "manual_review"
        return _save_loaded(session)

    if outcome == "same_issue":
        restore_session(manifest_path, step="latest")
        session = load_session(manifest_path)
        step = _latest_step(session)
        step["outcome"] = outcome
        remaining = [path for path in session.get("remaining_candidates", []) if path not in removed]
        session["remaining_candidates"] = remaining
        session["current_removed"] = []
        _finalize_status(session)
        return _save_loaded(session)

    # issue_gone: keep current batch disabled and narrow to it.
    for record in step.get("removed_units", []):
        if record.get("status") == "moved":
            record["status"] = "kept_disabled"
    session["remaining_candidates"] = removed
    session["current_removed"] = removed
    _finalize_status(session)
    return _save_loaded(session)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py -q --no-cov
```

Expected: all treatment tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/simanalysis/treatment.py tests/unit/test_treatment.py
git commit -m "feat: apply reversible treatment bisect steps"
```

---

## Task 4: Bridge Commands and Parser Wiring

**Files:**
- Modify: `src/simanalysis/bridge/commands.py`
- Modify: `src/simanalysis/bridge/__init__.py`
- Modify: `tests/unit/test_bridge_commands.py`
- Modify: `tests/unit/test_bridge_main.py`

- [ ] **Step 1: Add failing bridge command tests**

Append to `tests/unit/test_bridge_commands.py`:

```python
def test_treatment_plan_emits_result(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    payload = {"summary": {}, "script_crashes": {}, "ui_crashes": {}}
    monkeypatch.setattr(commands, "_build_doctor_payload", lambda base, mods, recursive: payload)
    monkeypatch.setattr(
        commands.treatment,
        "create_plan",
        lambda sims4_dir, mods_dir, doctor_payload, save=False: {
            "status": "planned",
            "manifest_path": None,
            "active_candidates": [],
            "next_batch": [],
            "warnings": ["No active Doctor candidates can be moved."],
        },
    )

    buf = io.StringIO()
    commands.treatment_plan(
        argparse.Namespace(path=str(sims4), mods=None, doctor_json=None, save=False),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[1]["data"]["status"] == "planned"


def test_treatment_apply_emits_result(monkeypatch, tmp_path):
    manifest = tmp_path / "session.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        commands.treatment,
        "apply_next_step",
        lambda path: {"status": "awaiting_result", "manifest_path": str(path)},
    )

    buf = io.StringIO()
    commands.treatment_apply(argparse.Namespace(manifest_path=str(manifest)), Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[1]["data"]["status"] == "awaiting_result"


def test_treatment_outcome_emits_result(monkeypatch, tmp_path):
    manifest = tmp_path / "session.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        commands.treatment,
        "record_outcome",
        lambda path, outcome: {"status": "confirmed_candidate", "outcome": outcome},
    )

    buf = io.StringIO()
    commands.treatment_outcome(
        argparse.Namespace(manifest_path=str(manifest), outcome="same_issue"),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert events[1]["data"]["outcome"] == "same_issue"


def test_treatment_status_emits_loaded_manifest(monkeypatch, tmp_path):
    manifest = tmp_path / "session.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        commands.treatment,
        "load_session",
        lambda path: {"status": "planned", "manifest_path": str(path)},
    )

    buf = io.StringIO()
    commands.treatment_status(argparse.Namespace(manifest_path=str(manifest)), Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert events[1]["data"]["status"] == "planned"
```

Append to `tests/unit/test_bridge_main.py`:

```python
def test_treatment_plan_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_treatment_plan(args, emit):
        called["path"] = args.path
        called["mods"] = args.mods
        called["doctor_json"] = args.doctor_json
        called["save"] = args.save
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "treatment-plan", fake_treatment_plan)

    code, events = _run(monkeypatch, ["treatment-plan", str(tmp_path), "--save"])

    assert code == 0
    assert called == {"path": str(tmp_path), "mods": None, "doctor_json": None, "save": True}
    assert [event["type"] for event in events] == ["result", "done"]


def test_treatment_outcome_command_is_dispatched(monkeypatch, tmp_path):
    manifest = tmp_path / "session.json"
    manifest.write_text("{}", encoding="utf-8")
    called = {}

    def fake_treatment_outcome(args, emit):
        called["manifest_path"] = args.manifest_path
        called["outcome"] = args.outcome
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "treatment-outcome", fake_treatment_outcome)

    code, events = _run(
        monkeypatch,
        ["treatment-outcome", str(manifest), "--outcome", "issue_gone"],
    )

    assert code == 0
    assert called == {"manifest_path": str(manifest), "outcome": "issue_gone"}
    assert [event["type"] for event in events] == ["result", "done"]
```

- [ ] **Step 2: Run bridge tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_bridge_commands.py tests/unit/test_bridge_main.py -q --no-cov
```

Expected: missing treatment command functions/parser commands.

- [ ] **Step 3: Refactor Doctor payload helper and add command handlers**

In `src/simanalysis/bridge/commands.py`, add imports:

```python
import json
from typing import Any

from simanalysis import treatment
```

Extract Doctor result construction from `doctor_scan` into:

```python
def _build_doctor_payload(base: Path, mods_dir: Path, recursive: bool) -> dict[str, Any]:
    pattern = "**/lastException*.txt" if recursive else "lastException*.txt"
    crash_reports = []
    crash_parse_errors = []
    seen = set()
    for log_file in sorted(base.glob(pattern)):
        try:
            for report in parse_exception_file(log_file):
                if report.signature in seen:
                    continue
                seen.add(report.signature)
                crash_reports.append(report)
        except Exception as exc:
            crash_parse_errors.append(f"{log_file.name}: {exc}")

    crash_analyzer = CrashAnalyzer()
    extra_roots = [d for d in base.glob("**/_*") if d.is_dir() and _is_disabled_name(d.name)]
    module_index = crash_analyzer.build_module_index(mods_dir, extra_roots=extra_roots)
    crash_result = crash_analyzer.analyze(crash_reports, module_index)
    crash_result.parse_errors = crash_parse_errors
    crash_payload = serialization.crash_result_to_dict(crash_result)

    ui_pattern = "**/lastUIException*.txt" if recursive else "lastUIException*.txt"
    ui_reports = []
    ui_parse_errors = []
    for log_file in sorted(base.glob(ui_pattern)):
        try:
            ui_reports.extend(parse_ui_exception_file(log_file))
        except Exception as exc:
            ui_parse_errors.append(f"{log_file.name}: {exc}")

    ui_analyzer = UICrashAnalyzer()
    target_keys = {key for report in ui_reports for key in report.keys}
    if target_keys:
        resource_index = ui_analyzer.build_resource_index(
            mods_dir,
            extra_roots=discover_disabled_roots(base),
            target_keys=target_keys,
        )
    else:
        resource_index = {}
    ui_result = ui_analyzer.analyze(ui_reports, resource_index)
    ui_result.parse_errors = ui_parse_errors
    ui_payload = serialization.ui_result_to_dict(ui_result)

    return {
        "summary": _doctor_summary(crash_payload, ui_payload),
        "script_crashes": crash_payload,
        "ui_crashes": ui_payload,
    }
```

Update `doctor_scan` to call the helper and emit two progress events around it:

```python
def doctor_scan(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"
    emit.start("doctor-scan", total=2)
    payload = _build_doctor_payload(base, mods_dir, args.recursive)
    emit.progress(1, 2, stage="script-crashes", force=True)
    emit.progress(2, 2, stage="ui-crashes", force=True)
    emit.result(payload)
    emit.done()
```

Add treatment handlers:

```python
def _load_doctor_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_file():
        raise ValueError(f"Doctor JSON not found: {path}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if "script_crashes" not in data or "ui_crashes" not in data:
        raise ValueError("Doctor JSON must contain script_crashes and ui_crashes")
    return data


def treatment_plan(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"
    emit.start("treatment-plan")
    doctor_payload = _load_doctor_json(args.doctor_json)
    if doctor_payload is None:
        doctor_payload = _build_doctor_payload(base, mods_dir, recursive=False)
    emit.result(treatment.create_plan(base, mods_dir, doctor_payload, save=args.save))
    emit.done()


def treatment_apply(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-apply")
    emit.result(treatment.apply_next_step(args.manifest_path))
    emit.done()


def treatment_outcome(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-outcome")
    emit.result(treatment.record_outcome(args.manifest_path, args.outcome))
    emit.done()


def treatment_restore(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-restore")
    emit.result(treatment.restore_session(args.manifest_path, step=args.step))
    emit.done()


def treatment_status(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-status")
    emit.result(treatment.load_session(args.manifest_path))
    emit.done()
```

Add to `DISPATCH`:

```python
    "treatment-plan": treatment_plan,
    "treatment-apply": treatment_apply,
    "treatment-outcome": treatment_outcome,
    "treatment-restore": treatment_restore,
    "treatment-status": treatment_status,
```

- [ ] **Step 4: Add argparse subcommands**

In `src/simanalysis/bridge/__init__.py`, add after `doctor-scan`:

```python
    p_treatment_plan = sub.add_parser("treatment-plan")
    p_treatment_plan.add_argument("path")
    p_treatment_plan.add_argument("--mods", default=None)
    p_treatment_plan.add_argument("--doctor-json", default=None)
    p_treatment_plan.add_argument("--save", action="store_true")

    p_treatment_apply = sub.add_parser("treatment-apply")
    p_treatment_apply.add_argument("manifest_path")

    p_treatment_outcome = sub.add_parser("treatment-outcome")
    p_treatment_outcome.add_argument("manifest_path")
    p_treatment_outcome.add_argument(
        "--outcome",
        required=True,
        choices=["same_issue", "issue_gone", "different_issue"],
    )

    p_treatment_restore = sub.add_parser("treatment-restore")
    p_treatment_restore.add_argument("manifest_path")
    p_treatment_restore.add_argument("--step", choices=["latest", "all"], default="latest")

    p_treatment_status = sub.add_parser("treatment-status")
    p_treatment_status.add_argument("manifest_path")
```

- [ ] **Step 5: Run bridge and treatment tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py tests/unit/test_bridge_commands.py tests/unit/test_bridge_main.py -q --no-cov
.venv/bin/ruff check src/simanalysis/treatment.py src/simanalysis/bridge tests/unit/test_treatment.py tests/unit/test_bridge_commands.py tests/unit/test_bridge_main.py
```

Expected: tests pass; Ruff clean.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add src/simanalysis/treatment.py src/simanalysis/bridge/commands.py src/simanalysis/bridge/__init__.py tests/unit/test_treatment.py tests/unit/test_bridge_commands.py tests/unit/test_bridge_main.py
git commit -m "feat: add treatment bridge commands"
```

---

## Task 5: Tauri Argument Builder and Frontend API

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Modify: `web/src/api.js`

- [ ] **Step 1: Add failing Rust tests for treatment args**

In `src-tauri/src/lib.rs` tests module, add:

```rust
#[test]
fn builds_treatment_plan_args_with_save_and_mods() {
    let opts = AnalysisOptions {
        mods_path: Some("/Sims/Mods".into()),
        save: true,
        ..Default::default()
    };
    let args = build_args("treatment-plan", "/Sims/The Sims 4", &opts).unwrap();
    assert_eq!(
        args,
        vec![
            "treatment-plan",
            "/Sims/The Sims 4",
            "--mods",
            "/Sims/Mods",
            "--save",
        ]
    );
}

#[test]
fn builds_treatment_outcome_args() {
    let opts = AnalysisOptions {
        outcome: Some("issue_gone".into()),
        ..Default::default()
    };
    let args = build_args("treatment-outcome", "/Sims/session.json", &opts).unwrap();
    assert_eq!(
        args,
        vec!["treatment-outcome", "/Sims/session.json", "--outcome", "issue_gone"]
    );
}

#[test]
fn treatment_outcome_requires_outcome() {
    let opts = AnalysisOptions::default();
    let err = build_args("treatment-outcome", "/Sims/session.json", &opts).unwrap_err();
    assert!(err.contains("requires options.outcome"));
}
```

- [ ] **Step 2: Run Rust tests and verify they fail**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: compile failure for missing `save` and `outcome` fields.

- [ ] **Step 3: Extend `AnalysisOptions` and `build_args`**

In `src-tauri/src/lib.rs`, extend `AnalysisOptions`:

```rust
    #[serde(default)]
    doctor_json_path: Option<String>,
    #[serde(default)]
    save: bool,
    #[serde(default)]
    outcome: Option<String>,
    #[serde(default)]
    step: Option<String>,
```

Add `build_args` match arms:

```rust
        "treatment-plan" => {
            args.push("treatment-plan".into());
            args.push(path.into());
            if let Some(mods) = opts.mods_path.as_deref() {
                args.push("--mods".into());
                args.push(mods.into());
            }
            if let Some(doctor_json) = opts.doctor_json_path.as_deref() {
                args.push("--doctor-json".into());
                args.push(doctor_json.into());
            }
            if opts.save {
                args.push("--save".into());
            }
        }
        "treatment-apply" => {
            args.push("treatment-apply".into());
            args.push(path.into());
        }
        "treatment-outcome" => {
            let outcome = opts
                .outcome
                .as_deref()
                .ok_or("treatment-outcome requires options.outcome")?;
            args.push("treatment-outcome".into());
            args.push(path.into());
            args.push("--outcome".into());
            args.push(outcome.into());
        }
        "treatment-restore" => {
            args.push("treatment-restore".into());
            args.push(path.into());
            if let Some(step) = opts.step.as_deref() {
                args.push("--step".into());
                args.push(step.into());
            }
        }
        "treatment-status" => {
            args.push("treatment-status".into());
            args.push(path.into());
        }
```

- [ ] **Step 4: Add frontend API methods**

In `web/src/api.js`, add methods inside `api`:

```javascript
  planTreatment: (sims4Path, modsPath, save, callbacks) =>
    runAnalysis('treatment-plan', sims4Path, { modsPath, save }, callbacks),
  applyTreatment: (manifestPath, callbacks) =>
    runAnalysis('treatment-apply', manifestPath, {}, callbacks),
  recordTreatmentOutcome: (manifestPath, outcome, callbacks) =>
    runAnalysis('treatment-outcome', manifestPath, { outcome }, callbacks),
  restoreTreatment: (manifestPath, step, callbacks) =>
    runAnalysis('treatment-restore', manifestPath, { step }, callbacks),
  treatmentStatus: (manifestPath, callbacks) =>
    runAnalysis('treatment-status', manifestPath, {}, callbacks),
```

- [ ] **Step 5: Run Rust and web build checks**

Run:

```bash
cargo test --manifest-path src-tauri/Cargo.toml
npm --prefix web run build
```

Expected: Rust tests pass; Vite build succeeds.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src-tauri/src/lib.rs web/src/api.js
git commit -m "feat: wire treatment commands through desktop shell"
```

---

## Task 6: Desktop Treatment View and Doctor Link

**Files:**
- Create: `web/src/views/Treatment.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Sidebar.jsx`
- Modify: `web/src/views/Doctor.jsx`

- [ ] **Step 1: Add route and sidebar imports**

In `web/src/App.jsx`, add:

```javascript
const Treatment = lazy(() => import('./views/Treatment'));
```

and route:

```javascript
<Route path="/treatment" element={<Treatment />} />
```

In `web/src/components/Sidebar.jsx`, add `Stethoscope` or `ShieldCheck` to lucide imports and add nav item after Doctor:

```javascript
{ path: '/treatment', icon: Stethoscope, label: 'Treatment' },
```

- [ ] **Step 2: Create Treatment view**

Create `web/src/views/Treatment.jsx`:

```javascript
import { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
    AlertTriangle,
    CheckCircle,
    FolderOpen,
    Loader2,
    Play,
    RotateCcw,
    ShieldCheck,
    Stethoscope,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import api from '../api';
import FilePicker from '../components/FilePicker';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';

function CandidateList({ candidates = [] }) {
    if (!candidates.length) {
        return <p className="text-sm text-gray-500">No movable active candidates found.</p>;
    }
    return (
        <div className="space-y-3">
            {candidates.map((candidate) => (
                <div key={candidate.unit_path} className="rounded-lg border border-gray-800 bg-gray-950/40 p-3">
                    <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                            <p className="font-medium text-white">{candidate.unit_name}</p>
                            <p className="break-all text-xs text-gray-500">{candidate.unit_path}</p>
                        </div>
                        <span className="w-fit rounded-md bg-blue-500/10 px-2 py-1 text-xs text-blue-200">
                            {candidate.unit_kind}
                        </span>
                    </div>
                    <div className="mt-2 space-y-1">
                        {(candidate.evidence || []).map((item, index) => (
                            <p key={`${candidate.unit_path}-${index}`} className="text-xs text-gray-400">
                                {item.source}: {item.reason} · <span className="break-all">{item.path}</span>
                            </p>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

function Treatment() {
    const location = useLocation();
    const [simsPath, setSimsPath] = useState(location.state?.simsPath || DEFAULT_SIMS_PATH);
    const [modsPath, setModsPath] = useState(location.state?.modsPath || '');
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showModsPicker, setShowModsPicker] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [isBusy, setIsBusy] = useState(false);

    const manifestPath = result?.manifest_path || null;
    const nextBatch = result?.next_batch || [];
    const candidateCount = result?.active_candidates?.length || 0;
    const canStart = result && !manifestPath && candidateCount > 0;
    const canApply = manifestPath && nextBatch.length > 0 && result?.status !== 'awaiting_result';
    const canRecord = manifestPath && result?.status === 'awaiting_result';

    const removedNames = useMemo(
        () =>
            (result?.current_removed || []).map((path) => {
                const parts = String(path).split('/');
                return parts[parts.length - 1] || path;
            }),
        [result],
    );

    const run = (action) => {
        setIsBusy(true);
        setError(null);
        action({
            onComplete: (data) => {
                setResult(data);
                setIsBusy(false);
            },
            onError: (message) => {
                setError(message);
                setIsBusy(false);
            },
        });
    };

    const createPlan = (save = false) => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            return;
        }
        run((callbacks) => api.planTreatment(simsPath.trim(), modsPath.trim() || null, save, callbacks));
    };

    const applyStep = () => {
        if (!manifestPath) return;
        if (!window.confirm(`Move ${nextBatch.length} candidate unit(s) out of Mods for the next test?`)) return;
        run((callbacks) => api.applyTreatment(manifestPath, callbacks));
    };

    const recordOutcome = (outcome) => {
        if (!manifestPath) return;
        run((callbacks) => api.recordTreatmentOutcome(manifestPath, outcome, callbacks));
    };

    const restoreLatest = () => {
        if (!manifestPath) return;
        if (!window.confirm('Restore the latest moved batch back into Mods?')) return;
        run((callbacks) => api.restoreTreatment(manifestPath, 'latest', callbacks));
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-7xl space-y-6">
                <motion.header
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col gap-3"
                >
                    <h1 className="flex items-center gap-3 text-3xl font-bold text-white">
                        <span className="rounded-xl bg-emerald-500/15 p-2 text-emerald-300">
                            <Stethoscope size={28} />
                        </span>
                        Treatment
                    </h1>
                    <p className="max-w-3xl text-gray-400">
                        Create a reversible bisect plan, move one suggested batch at a time, then record what happened after you test in The Sims 4.
                    </p>
                </motion.header>

                <section className="glass-card p-5">
                    <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
                        <div>
                            <label className="mb-2 block text-sm font-medium text-gray-300">Sims 4 Folder</label>
                            <div className="flex gap-2">
                                <input
                                    value={simsPath}
                                    onChange={(event) => setSimsPath(event.target.value)}
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    className="rounded-lg border border-gray-700 bg-gray-800 px-3 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div>
                            <label className="mb-2 block text-sm font-medium text-gray-300">Mods Folder</label>
                            <div className="flex gap-2">
                                <input
                                    value={modsPath}
                                    onChange={(event) => setModsPath(event.target.value)}
                                    placeholder="Default: Sims 4 folder / Mods"
                                    className="min-w-0 flex-1 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600"
                                />
                                <button
                                    onClick={() => setShowModsPicker(true)}
                                    className="rounded-lg border border-gray-700 bg-gray-800 px-3 text-gray-200 hover:bg-gray-700"
                                    title="Browse for Mods folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={() => createPlan(false)}
                                disabled={isBusy}
                                className="flex h-[42px] w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-5 font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60 lg:w-auto"
                            >
                                {isBusy ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
                                Create Plan
                            </button>
                        </div>
                    </div>
                    <AnimatePresence>
                        {error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                {error}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                {result && (
                    <section className="grid gap-4 md:grid-cols-4">
                        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                            <p className="text-sm text-gray-400">Status</p>
                            <p className="mt-2 text-2xl font-semibold text-white">{result.status}</p>
                        </div>
                        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                            <p className="text-sm text-gray-400">Candidates</p>
                            <p className="mt-2 text-2xl font-semibold text-white">{candidateCount}</p>
                        </div>
                        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                            <p className="text-sm text-gray-400">Next Batch</p>
                            <p className="mt-2 text-2xl font-semibold text-white">{nextBatch.length}</p>
                        </div>
                        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
                            <p className="text-sm text-gray-400">Removed Now</p>
                            <p className="mt-2 text-2xl font-semibold text-white">{removedNames.length}</p>
                        </div>
                    </section>
                )}

                {result && (
                    <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                        <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                                <CheckCircle size={20} className="text-emerald-300" />
                                Movable Candidates
                            </h2>
                            <CandidateList candidates={result.active_candidates || []} />
                        </div>
                        <div className="space-y-4">
                            {(result.warnings || []).length > 0 && (
                                <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
                                    <div className="mb-2 flex items-center gap-2 font-medium">
                                        <AlertTriangle size={18} />
                                        Warnings
                                    </div>
                                    {(result.warnings || []).map((warning) => (
                                        <p key={warning}>{warning}</p>
                                    ))}
                                </div>
                            )}
                            <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                                <h2 className="mb-4 text-lg font-semibold text-white">Next Action</h2>
                                <div className="space-y-3">
                                    {canStart && (
                                        <button
                                            onClick={() => createPlan(true)}
                                            disabled={isBusy}
                                            className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:opacity-60"
                                        >
                                            <Play size={17} />
                                            Start Session
                                        </button>
                                    )}
                                    {canApply && (
                                        <button
                                            onClick={applyStep}
                                            disabled={isBusy}
                                            className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
                                        >
                                            <Play size={17} />
                                            Apply Step
                                        </button>
                                    )}
                                    {canRecord && (
                                        <div className="space-y-2">
                                            <p className="text-sm text-gray-400">Run Sims and try the same action, then record the result.</p>
                                            <button onClick={() => recordOutcome('same_issue')} className="w-full rounded-lg bg-gray-800 px-4 py-2 text-white hover:bg-gray-700">Same Issue</button>
                                            <button onClick={() => recordOutcome('issue_gone')} className="w-full rounded-lg bg-gray-800 px-4 py-2 text-white hover:bg-gray-700">Issue Gone</button>
                                            <button onClick={() => recordOutcome('different_issue')} className="w-full rounded-lg bg-gray-800 px-4 py-2 text-white hover:bg-gray-700">Different Issue</button>
                                        </div>
                                    )}
                                    {manifestPath && (
                                        <button
                                            onClick={restoreLatest}
                                            disabled={isBusy}
                                            className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-700 px-4 py-2 font-medium text-gray-200 hover:bg-gray-800 disabled:opacity-60"
                                        >
                                            <RotateCcw size={17} />
                                            Restore Latest Step
                                        </button>
                                    )}
                                </div>
                                {manifestPath && <p className="mt-4 break-all text-xs text-gray-500">{manifestPath}</p>}
                            </div>
                        </div>
                    </section>
                )}

                <FilePicker
                    isOpen={showSimsPicker}
                    onClose={() => setShowSimsPicker(false)}
                    onSelect={(path) => setSimsPath(path)}
                    initialPath={simsPath}
                    selectDirectory={true}
                />
                <FilePicker
                    isOpen={showModsPicker}
                    onClose={() => setShowModsPicker(false)}
                    onSelect={(path) => setModsPath(path)}
                    initialPath={modsPath || simsPath}
                    selectDirectory={true}
                />
            </div>
        </div>
    );
}

export default Treatment;
```

- [ ] **Step 3: Link Doctor to Treatment**

In `web/src/views/Doctor.jsx`, import `useNavigate`:

```javascript
import { useNavigate } from 'react-router-dom';
```

Inside `Doctor()`, add:

```javascript
    const navigate = useNavigate();
```

In the header action area where Export JSON is rendered, add a Treatment button when `activeTotal > 0`:

```javascript
                    {result && activeTotal > 0 && (
                        <button
                            onClick={() => navigate('/treatment', { state: { simsPath, modsPath } })}
                            className="flex w-fit items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
                        >
                            <ShieldCheck size={17} />
                            Open Treatment
                        </button>
                    )}
```

If the existing header action container only handles one button, wrap the buttons in:

```javascript
<div className="flex flex-wrap gap-2">
    ...
</div>
```

- [ ] **Step 4: Run frontend checks**

Run:

```bash
npm --prefix web run lint
npm --prefix web run build
```

Expected: lint and build pass.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add web/src/views/Treatment.jsx web/src/App.jsx web/src/components/Sidebar.jsx web/src/views/Doctor.jsx
git commit -m "feat: add desktop Treatment workflow"
```

---

## Task 7: Validation, Security, and Final Review

**Files:**
- Create: `docs/superpowers/2026-05-31-treatment-autobisect-validation.md`
- Potentially modify files from earlier tasks only if validation finds a real bug.

- [ ] **Step 1: Run dry-run validation against the real Sims folder**

Run:

```bash
.venv/bin/simanalysis-bridge treatment-plan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" > /tmp/simanalysis-treatment-plan.ndjson
tail -n 5 /tmp/simanalysis-treatment-plan.ndjson
test ! -d "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4/_Simanalysis_Treatment"
```

Expected:
- NDJSON contains `start`, `result`, `done`.
- The shell `test ! -d .../_Simanalysis_Treatment` succeeds unless the user already had that folder from prior manual work. If it exists, inspect its timestamp before making any claim.
- No files are moved because `--save` was not used.

- [ ] **Step 2: Summarize validation in a doc**

Create `docs/superpowers/2026-05-31-treatment-autobisect-validation.md`:

````markdown
# Treatment + Auto-Bisect Real-Folder Validation

Date: 2026-05-31
Branch: `feat/treatment-autobisect`

## Command

```bash
.venv/bin/simanalysis-bridge treatment-plan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Raw NDJSON was written outside the repo at `/tmp/simanalysis-treatment-plan.ndjson`.

## Result

- NDJSON sequence:
  1. `start`
  2. `result`
  3. `done`
- Default planning did not use `--save`.
- No live mod move was attempted.
- `_Simanalysis_Treatment` was not created by the dry-run command.

## Candidate Summary

Generate the result summary from the NDJSON file and write the actual values into this section:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

events = [json.loads(line) for line in Path("/tmp/simanalysis-treatment-plan.ndjson").read_text().splitlines()]
data = next(event["data"] for event in events if event["type"] == "result")
print(f"- status: {data['status']}")
print(f"- movable candidate count: {len(data.get('active_candidates', []))}")
print(f"- next batch count: {len(data.get('next_batch', []))}")
print(f"- warnings: {data.get('warnings', [])}")
print(f"- blockers: {data.get('blockers', [])}")
PY
```

## Safety Notes

The validation stayed read-only against the real Sims folder. Mutation behavior is covered by tmp-path unit tests.
````

- [ ] **Step 3: Run full local verification**

Run:

```bash
git diff --check
.venv/bin/python -m pytest -q --no-cov
.venv/bin/ruff check .
.venv/bin/mypy src/simanalysis
.venv/bin/bandit -r src
npm --prefix web run lint
npm --prefix web run build
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected:
- pytest passes.
- Ruff passes.
- mypy exits 0. It may print the existing `python_version: Python 3.9 is not supported` warning; do not treat that warning as a failure if the exit code is 0.
- Bandit reports no issues.
- web lint/build pass.
- cargo tests pass.

If `cargo test` fails locally because the ignored Tauri sidecar binary is absent, create the local ignored sidecar shim:

```bash
mkdir -p src-tauri/binaries
printf '#!/bin/sh\nexit 0\n' > src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin
chmod +x src-tauri/binaries/simanalysis-bridge-aarch64-apple-darwin
cargo test --manifest-path src-tauri/Cargo.toml
```

Do not commit the sidecar shim.

- [ ] **Step 4: Commit validation doc**

Run:

```bash
git add docs/superpowers/2026-05-31-treatment-autobisect-validation.md
git commit -m "docs: validate Treatment Auto-Bisect dry run"
```

- [ ] **Step 5: Final branch review**

Before opening the PR, run:

```bash
git status --short --branch
git log --oneline github/main..HEAD
```

Expected:
- Working tree clean except ignored local `.venv` and optional ignored Tauri sidecar shim.
- Commits are focused:
  - spec commit already exists
  - plan commit already exists
  - treatment planner
  - manifest/move safety
  - bridge commands
  - Tauri/API wiring
  - Treatment UI
  - validation doc

Then dispatch final code review using `superpowers:requesting-code-review`.

- [ ] **Step 6: Open PR and merge after CI is green**

Use the GitHub workflow from prior Simanalysis PRs:

```bash
git push -u github feat/treatment-autobisect
gh pr create --repo justaride/Simanalysis --base main --head feat/treatment-autobisect --title "feat: add Treatment Auto-Bisect" --body-file /tmp/treatment-autobisect-pr.md
gh pr checks <PR_NUMBER> --repo justaride/Simanalysis --watch
gh pr merge <PR_NUMBER> --repo justaride/Simanalysis --auto --squash
```

If CI fails, use `github:gh-fix-ci`, inspect logs first, and patch only the root cause. If the known DBPF lazy-loading benchmark flakes, rerun once; if it repeats, treat it as a real CI blocker and stabilize it intentionally.

## Plan Self-Review

- **Spec coverage:** Dry-run planning is in Tasks 1 and 4; manifest/save boundary in Task 2; reversible apply/restore/outcome in Task 3; bridge commands in Task 4; desktop/Tauri wiring in Tasks 5 and 6; real-folder dry-run validation and Bandit in Task 7.
- **Scope check:** No Sims launching, live monitoring, delete/permanent quarantine, network lookups, or automatic real-folder mutation are included.
- **Type/name consistency:** `treatment-plan`, `treatment-apply`, `treatment-outcome`, `treatment-restore`, and `treatment-status` are used consistently across Python bridge, Rust `build_args`, and frontend API.
- **Safety check:** Default planning has `manifest_path: null` and no Sims-folder writes. Mutation commands all require a manifest and call `assert_sims_not_running()`.
