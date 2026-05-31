# Live Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only Live Monitoring that detects new Sims crash logs, runs Doctor automatically, and returns a dry-run Treatment summary when candidates become available.

**Architecture:** Add a focused `simanalysis.live_monitoring` service for fingerprinting logs, tracking per-session state, and producing monitor results. Expose it through a new `simanalysis-bridge live-monitor` command and wire the Tauri sidecar argument builder so the desktop app can consume the bridge command in a future UI slice.

**Tech Stack:** Python 3.11, pytest, existing NDJSON bridge protocol, existing Doctor builder, existing Treatment planner, Rust Tauri sidecar argument tests, Bandit.

---

## Scope Check

The approved spec is one backend slice: stdlib polling, bridge exposure, and no desktop UI controls. This plan does not create React monitoring controls, persist monitor state across app restarts, or mutate the Sims folder.

## File Structure

- Create `src/simanalysis/live_monitoring.py`
  - Owns log discovery, fingerprints, snapshots, monitor state, recommended-action selection, and dry-run Doctor/Treatment orchestration.
- Create `tests/unit/test_live_monitoring.py`
  - Covers fingerprinting, changed-log detection, startup baseline behavior, dry-run planning, action selection, and no-manifest safety.
- Modify `src/simanalysis/bridge/__init__.py`
  - Adds parser support for `simanalysis-bridge live-monitor`.
- Modify `src/simanalysis/bridge/commands.py`
  - Adds the bridge command handler and dispatch entry.
- Modify `tests/unit/test_bridge_main.py`
  - Covers parser/dispatch for the new command.
- Modify `tests/unit/test_bridge_commands.py`
  - Covers bridge command event sequence and interval validation.
- Modify `src-tauri/src/lib.rs`
  - Adds `live-monitor` sidecar argument construction.
- Modify `docs/superpowers/2026-05-31-live-monitoring-validation.md`
  - Records final test, Bandit, synthetic validation, and real-folder read-only validation evidence.

---

### Task 1: Log Fingerprints And Snapshot Diff

**Files:**
- Create: `src/simanalysis/live_monitoring.py`
- Create: `tests/unit/test_live_monitoring.py`

- [ ] **Step 1: Write failing fingerprint and diff tests**

Add this new test file:

```python
# tests/unit/test_live_monitoring.py
from __future__ import annotations

from pathlib import Path

from simanalysis.live_monitoring import (
    build_snapshot,
    changed_fingerprints,
    discover_log_files,
)


def test_discover_log_files_finds_script_and_ui_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    script_log = sims4 / "lastException.txt"
    ui_log = sims4 / "lastUIException_1.txt"
    ignored = sims4 / "notify.glob"
    script_log.write_text("script", encoding="utf-8")
    ui_log.write_text("ui", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")

    discovered = discover_log_files(sims4)

    assert [(item.kind, item.path.name) for item in discovered] == [
        ("script", "lastException.txt"),
        ("ui", "lastUIException_1.txt"),
    ]


def test_build_snapshot_records_stable_file_fingerprints(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    log = sims4 / "lastException.txt"
    log.write_text("first crash", encoding="utf-8")

    snapshot, warnings = build_snapshot(sims4)

    fingerprint = snapshot[str(log.resolve())]
    assert warnings == []
    assert fingerprint.path == str(log.resolve())
    assert fingerprint.name == "lastException.txt"
    assert fingerprint.kind == "script"
    assert fingerprint.size == len("first crash")
    assert fingerprint.mtime_ns > 0
    assert len(fingerprint.digest) == 16


def test_changed_fingerprints_detects_new_and_modified_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    script_log = sims4 / "lastException.txt"
    script_log.write_text("old", encoding="utf-8")
    previous, previous_warnings = build_snapshot(sims4)
    assert previous_warnings == []

    script_log.write_text("new content", encoding="utf-8")
    ui_log = sims4 / "lastUIException.txt"
    ui_log.write_text("ui", encoding="utf-8")
    current, current_warnings = build_snapshot(sims4)

    changed = changed_fingerprints(previous, current)

    assert current_warnings == []
    assert [item.name for item in changed] == ["lastException.txt", "lastUIException.txt"]


def test_build_snapshot_warns_when_log_cannot_be_read(monkeypatch, tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    log = sims4 / "lastException.txt"
    log.write_text("crash", encoding="utf-8")

    def fail_fingerprint(discovered):
        raise OSError("permission denied")

    monkeypatch.setattr(
        "simanalysis.live_monitoring.fingerprint_log",
        fail_fingerprint,
    )

    snapshot, warnings = build_snapshot(sims4)

    assert snapshot == {}
    assert warnings == ["Could not read lastException.txt: permission denied"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py -q --no-cov
```

Expected: FAIL during import with `ModuleNotFoundError: No module named 'simanalysis.live_monitoring'`.

- [ ] **Step 3: Add the minimal monitoring fingerprint module**

Create the new module:

```python
# src/simanalysis/live_monitoring.py
"""Read-only live monitoring for Sims 4 crash logs."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

LOG_GLOBS = (("script", "lastException*.txt"), ("ui", "lastUIException*.txt"))


@dataclass(frozen=True)
class DiscoveredLog:
    kind: str
    path: Path


@dataclass(frozen=True)
class LogFingerprint:
    path: str
    name: str
    kind: str
    size: int
    mtime_ns: int
    digest: str

    def to_event(self) -> dict[str, object]:
        return asdict(self)


def discover_log_files(sims4_dir: str | Path) -> list[DiscoveredLog]:
    base = Path(sims4_dir).expanduser().resolve()
    logs: list[DiscoveredLog] = []
    for kind, pattern in LOG_GLOBS:
        for path in sorted(base.glob(pattern), key=lambda item: item.name.casefold()):
            if path.is_file():
                logs.append(DiscoveredLog(kind=kind, path=path.resolve()))
    return logs


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def fingerprint_log(discovered: DiscoveredLog) -> LogFingerprint:
    stat = discovered.path.stat()
    return LogFingerprint(
        path=str(discovered.path),
        name=discovered.path.name,
        kind=discovered.kind,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        digest=_digest_file(discovered.path),
    )


def build_snapshot(sims4_dir: str | Path) -> tuple[dict[str, LogFingerprint], list[str]]:
    snapshot: dict[str, LogFingerprint] = {}
    warnings: list[str] = []
    for discovered in discover_log_files(sims4_dir):
        try:
            fingerprint = fingerprint_log(discovered)
        except OSError as exc:
            warnings.append(f"Could not read {discovered.path.name}: {exc}")
            continue
        snapshot[fingerprint.path] = fingerprint
    return snapshot, warnings


def changed_fingerprints(
    previous: dict[str, LogFingerprint],
    current: dict[str, LogFingerprint],
) -> list[LogFingerprint]:
    changed = [
        fingerprint
        for path, fingerprint in current.items()
        if previous.get(path) != fingerprint
    ]
    return sorted(changed, key=lambda item: (item.kind, item.name.casefold()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py -q --no-cov
```

Expected: PASS with `4 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/simanalysis/live_monitoring.py tests/unit/test_live_monitoring.py
git commit -m "feat: add live monitor log fingerprinting"
```

---

### Task 2: Monitor State And Waiting Results

**Files:**
- Modify: `src/simanalysis/live_monitoring.py`
- Modify: `tests/unit/test_live_monitoring.py`

- [ ] **Step 1: Write failing monitor state tests**

Append these tests:

```python
from simanalysis.live_monitoring import LiveMonitor


def test_live_monitor_baseline_ignores_existing_logs(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastException.txt").write_text("existing", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods)

    def fail_doctor_builder(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Doctor should not run when no log changed")

    def fail_treatment_planner(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("Treatment should not run when no log changed")

    result = monitor.poll(fail_doctor_builder, fail_treatment_planner)

    assert result["changed_logs"] == []
    assert result["watched_log_count"] == 1
    assert result["doctor_summary"] == {}
    assert result["treatment"] == {
        "candidate_count": 0,
        "first_batch_count": 0,
        "manifest_path": None,
        "warnings": [],
        "blockers": [],
    }
    assert result["recommended_next_action"] == "waiting"


def test_live_monitor_with_empty_prior_snapshot_detects_existing_log(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastUIException.txt").write_text("ui crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})

    result = monitor.poll(
        lambda base, mods_dir, recursive: {
            "summary": {"script_reports": 0, "ui_findings": 1, "ui_active": 0},
            "script_crashes": {},
            "ui_crashes": {},
        },
        lambda base, mods_dir, doctor_payload, *, save=False: {
            "active_candidates": [],
            "next_batch": [],
            "manifest_path": None,
            "warnings": ["No active Doctor candidates can be moved."],
            "blockers": [],
        },
    )

    assert [log["name"] for log in result["changed_logs"]] == ["lastUIException.txt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py::test_live_monitor_baseline_ignores_existing_logs tests/unit/test_live_monitoring.py::test_live_monitor_with_empty_prior_snapshot_detects_existing_log -q --no-cov
```

Expected: FAIL with `ImportError` or `AttributeError` for `LiveMonitor`.

- [ ] **Step 3: Add monitor state and waiting result support**

Extend `src/simanalysis/live_monitoring.py`:

```python
from typing import Any, Callable

DoctorBuilder = Callable[[Path, Path, bool], dict[str, Any]]
TreatmentPlanner = Callable[..., dict[str, Any]]


def _empty_treatment_summary() -> dict[str, object]:
    return {
        "candidate_count": 0,
        "first_batch_count": 0,
        "manifest_path": None,
        "warnings": [],
        "blockers": [],
    }


class LiveMonitor:
    def __init__(
        self,
        sims4_dir: str | Path,
        mods_dir: str | Path | None = None,
        *,
        initial_snapshot: dict[str, LogFingerprint] | None = None,
    ) -> None:
        self.sims4_dir = Path(sims4_dir).expanduser().resolve()
        self.mods_dir = (
            Path(mods_dir).expanduser().resolve()
            if mods_dir is not None
            else self.sims4_dir / "Mods"
        )
        if initial_snapshot is None:
            self.snapshot, self.startup_warnings = build_snapshot(self.sims4_dir)
        else:
            self.snapshot = dict(initial_snapshot)
            self.startup_warnings = []

    def poll(
        self,
        doctor_builder: DoctorBuilder,
        treatment_planner: TreatmentPlanner,
    ) -> dict[str, Any]:
        current, warnings = build_snapshot(self.sims4_dir)
        changed = changed_fingerprints(self.snapshot, current)
        self.snapshot = current
        all_warnings = [*self.startup_warnings, *warnings]
        self.startup_warnings = []

        if not changed:
            return {
                "changed_logs": [],
                "watched_log_count": len(current),
                "doctor_summary": {},
                "treatment": _empty_treatment_summary(),
                "recommended_next_action": "waiting",
                "warnings": all_warnings,
            }

        return {
            "changed_logs": [fingerprint.to_event() for fingerprint in changed],
            "watched_log_count": len(current),
            "doctor_summary": {},
            "treatment": _empty_treatment_summary(),
            "recommended_next_action": "review_doctor",
            "warnings": all_warnings,
        }
```

- [ ] **Step 4: Run tests to verify monitor-state behavior passes**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py::test_live_monitor_baseline_ignores_existing_logs tests/unit/test_live_monitoring.py::test_live_monitor_with_empty_prior_snapshot_detects_existing_log -q --no-cov
```

Expected: both tests PASS. The Doctor/Treatment result assertions are added in Task 3.

- [ ] **Step 5: Run the whole live monitoring test file**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py -q --no-cov
```

Expected: PASS with `6 passed`.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/simanalysis/live_monitoring.py tests/unit/test_live_monitoring.py
git commit -m "feat: track live monitor session state"
```

---

### Task 3: Doctor And Dry-Run Treatment Integration

**Files:**
- Modify: `src/simanalysis/live_monitoring.py`
- Modify: `tests/unit/test_live_monitoring.py`

- [ ] **Step 1: Write failing integration and action-selection tests**

Append these tests:

```python
def test_poll_runs_doctor_and_dry_run_treatment_for_changed_log(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastException.txt").write_text("new crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})
    calls: dict[str, object] = {}
    doctor_payload = {
        "summary": {"script_reports": 1, "script_active": 1, "ui_findings": 0, "ui_active": 0},
        "script_crashes": {},
        "ui_crashes": {},
    }

    def doctor_builder(base: Path, mods_dir: Path, recursive: bool) -> dict[str, object]:
        calls["doctor"] = (base, mods_dir, recursive)
        return doctor_payload

    def treatment_planner(
        base: Path,
        mods_dir: Path,
        payload: dict[str, object],
        *,
        save: bool = False,
    ) -> dict[str, object]:
        calls["treatment"] = (base, mods_dir, payload, save)
        return {
            "active_candidates": [{"unit_name": "Creator"}],
            "next_batch": [str(mods / "Creator")],
            "manifest_path": None,
            "warnings": [],
            "blockers": [],
        }

    result = monitor.poll(doctor_builder, treatment_planner)

    assert calls["doctor"] == (sims4.resolve(), mods.resolve(), False)
    assert calls["treatment"] == (sims4.resolve(), mods.resolve(), doctor_payload, False)
    assert result["doctor_summary"] == doctor_payload["summary"]
    assert result["treatment"] == {
        "candidate_count": 1,
        "first_batch_count": 1,
        "manifest_path": None,
        "warnings": [],
        "blockers": [],
    }
    assert result["recommended_next_action"] == "open_treatment"


def test_poll_reports_no_movable_candidates_without_creating_manifest(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastUIException.txt").write_text("new ui crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})

    result = monitor.poll(
        lambda base, mods_dir, recursive: {
            "summary": {
                "script_reports": 0,
                "script_active": 0,
                "script_disabled": 0,
                "script_not_installed": 0,
                "ui_findings": 1,
                "ui_active": 0,
                "ui_disabled": 1,
                "ui_not_found": 0,
                "ui_no_key": 0,
                "parse_errors": 0,
                "index_errors": 0,
            },
            "script_crashes": {},
            "ui_crashes": {},
        },
        lambda base, mods_dir, payload, *, save=False: {
            "active_candidates": [],
            "next_batch": [],
            "manifest_path": None,
            "warnings": ["No active Doctor candidates can be moved."],
            "blockers": [],
        },
    )

    assert result["recommended_next_action"] == "no_movable_candidates"
    assert result["treatment"]["candidate_count"] == 0
    assert result["treatment"]["manifest_path"] is None
    assert not (sims4 / "_Simanalysis_Treatment").exists()


def test_poll_recommends_review_when_active_evidence_has_no_candidate(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastException.txt").write_text("new crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})

    result = monitor.poll(
        lambda base, mods_dir, recursive: {
            "summary": {
                "script_reports": 1,
                "script_active": 1,
                "ui_findings": 0,
                "ui_active": 0,
                "parse_errors": 0,
                "index_errors": 0,
            },
            "script_crashes": {},
            "ui_crashes": {},
        },
        lambda base, mods_dir, payload, *, save=False: {
            "active_candidates": [],
            "next_batch": [],
            "manifest_path": None,
            "warnings": ["No active Doctor candidates can be moved."],
            "blockers": [],
        },
    )

    assert result["recommended_next_action"] == "review_doctor"


def test_poll_surfaces_treatment_planning_error_with_doctor_summary(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (sims4 / "lastException.txt").write_text("new crash", encoding="utf-8")
    monitor = LiveMonitor(sims4, mods, initial_snapshot={})

    def treatment_planner(*args: object, **kwargs: object) -> dict[str, object]:
        raise ValueError("plan failed")

    result = monitor.poll(
        lambda base, mods_dir, recursive: {
            "summary": {"script_reports": 1, "script_active": 1, "parse_errors": 0},
            "script_crashes": {},
            "ui_crashes": {},
        },
        treatment_planner,
    )

    assert result["doctor_summary"] == {"script_reports": 1, "script_active": 1, "parse_errors": 0}
    assert result["treatment"]["warnings"] == ["Treatment planning failed: plan failed"]
    assert result["recommended_next_action"] == "review_doctor"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py::test_poll_runs_doctor_and_dry_run_treatment_for_changed_log tests/unit/test_live_monitoring.py::test_poll_reports_no_movable_candidates_without_creating_manifest tests/unit/test_live_monitoring.py::test_poll_recommends_review_when_active_evidence_has_no_candidate tests/unit/test_live_monitoring.py::test_poll_surfaces_treatment_planning_error_with_doctor_summary -q --no-cov
```

Expected: FAIL because `LiveMonitor.poll` does not yet call Doctor or Treatment.

- [ ] **Step 3: Add Treatment summary and action selection helpers**

Add these helpers above `LiveMonitor`:

```python
def _doctor_has_evidence(summary: dict[str, Any]) -> bool:
    return any(
        int(summary.get(key, 0) or 0) > 0
        for key in (
            "script_reports",
            "script_disabled",
            "script_not_installed",
            "script_base_game_only",
            "ui_findings",
            "ui_disabled",
            "ui_not_found",
            "ui_no_key",
        )
    )


def _doctor_needs_review(summary: dict[str, Any]) -> bool:
    return any(
        int(summary.get(key, 0) or 0) > 0
        for key in ("script_active", "ui_active", "parse_errors", "index_errors")
    )


def _treatment_summary(plan: dict[str, Any]) -> dict[str, object]:
    return {
        "candidate_count": len(plan.get("active_candidates", [])),
        "first_batch_count": len(plan.get("next_batch", [])),
        "manifest_path": plan.get("manifest_path"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _recommended_action(
    changed: list[LogFingerprint],
    doctor_summary: dict[str, Any],
    treatment: dict[str, object],
) -> str:
    if not changed:
        return "waiting"
    if int(treatment.get("candidate_count", 0) or 0) > 0:
        return "open_treatment"
    if _doctor_needs_review(doctor_summary):
        return "review_doctor"
    if _doctor_has_evidence(doctor_summary):
        return "no_movable_candidates"
    return "review_doctor"
```

- [ ] **Step 4: Replace the changed-log branch in `LiveMonitor.poll`**

Use this body after the no-change return:

```python
        doctor_payload = doctor_builder(self.sims4_dir, self.mods_dir, False)
        doctor_summary = dict(doctor_payload.get("summary", {}))
        try:
            plan = treatment_planner(
                self.sims4_dir,
                self.mods_dir,
                doctor_payload,
                save=False,
            )
            treatment = _treatment_summary(plan)
        except Exception as exc:
            treatment = _empty_treatment_summary()
            treatment["warnings"] = [f"Treatment planning failed: {exc}"]

        return {
            "changed_logs": [fingerprint.to_event() for fingerprint in changed],
            "watched_log_count": len(current),
            "doctor_summary": doctor_summary,
            "treatment": treatment,
            "recommended_next_action": _recommended_action(changed, doctor_summary, treatment),
            "warnings": all_warnings,
        }
```

- [ ] **Step 5: Run live monitoring tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py -q --no-cov
```

Expected: PASS with `10 passed`.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/simanalysis/live_monitoring.py tests/unit/test_live_monitoring.py
git commit -m "feat: connect live monitor to doctor treatment dry run"
```

---

### Task 4: Python Bridge Command

**Files:**
- Modify: `src/simanalysis/bridge/__init__.py`
- Modify: `src/simanalysis/bridge/commands.py`
- Modify: `tests/unit/test_bridge_main.py`
- Modify: `tests/unit/test_bridge_commands.py`

- [ ] **Step 1: Write failing parser dispatch test**

Add this test to `tests/unit/test_bridge_main.py`:

```python
def test_live_monitor_command_is_dispatched(monkeypatch, tmp_path):
    called = {}

    def fake_live_monitor(args, emit):
        called["args"] = args
        emit.result({"ok": True})
        emit.done()

    monkeypatch.setitem(commands.DISPATCH, "live-monitor", fake_live_monitor)

    code, events = _run(
        monkeypatch,
        [
            "live-monitor",
            str(tmp_path),
            "--mods",
            str(tmp_path),
            "--interval",
            "0.25",
            "--once",
        ],
    )

    assert code == 0
    assert called["args"].path == str(tmp_path)
    assert called["args"].mods == str(tmp_path)
    assert called["args"].interval == 0.25
    assert called["args"].once is True
    assert [event["type"] for event in events] == ["result", "done"]
```

- [ ] **Step 2: Run the parser test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_bridge_main.py::test_live_monitor_command_is_dispatched -q --no-cov
```

Expected: FAIL with argparse `SystemExit: 2` because `live-monitor` is unknown.

- [ ] **Step 3: Add bridge parser arguments**

In `src/simanalysis/bridge/__init__.py`, add this parser block before `return parser`:

```python
    p_live_monitor = sub.add_parser("live-monitor")
    p_live_monitor.add_argument("path")
    p_live_monitor.add_argument("--mods", default=None)
    p_live_monitor.add_argument("--interval", type=float, default=2.0)
    p_live_monitor.add_argument("--once", action="store_true")
```

- [ ] **Step 4: Run parser test and verify dispatch receives parsed arguments**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_bridge_main.py::test_live_monitor_command_is_dispatched -q --no-cov
```

Expected: PASS because this test injects a fake `live-monitor` handler through `commands.DISPATCH`.

- [ ] **Step 5: Write failing bridge command tests**

Add these tests to `tests/unit/test_bridge_commands.py`:

```python
def test_live_monitor_once_emits_waiting_result(monkeypatch, tmp_path):
    class FakeLiveMonitor:
        def __init__(self, base, mods_dir):
            self.base = base
            self.mods_dir = mods_dir

        def poll(self, doctor_builder, treatment_planner):
            return {
                "changed_logs": [],
                "watched_log_count": 0,
                "doctor_summary": {},
                "treatment": {
                    "candidate_count": 0,
                    "first_batch_count": 0,
                    "manifest_path": None,
                    "warnings": [],
                    "blockers": [],
                },
                "recommended_next_action": "waiting",
                "warnings": [],
            }

    monkeypatch.setattr(commands.live_monitoring, "LiveMonitor", FakeLiveMonitor)
    buf = io.StringIO()

    commands.live_monitor(
        argparse.Namespace(path=str(tmp_path), mods=None, interval=0.2, once=True),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "progress", "result", "done"]
    assert events[0]["task"] == "live-monitor"
    assert events[1]["stage"] == "waiting"
    assert events[2]["data"]["recommended_next_action"] == "waiting"


def test_live_monitor_rejects_non_positive_interval(tmp_path):
    with pytest.raises(ValueError, match="Live monitor interval must be greater than zero"):
        commands.live_monitor(
            argparse.Namespace(path=str(tmp_path), mods=None, interval=0, once=True),
            Emitter(io.StringIO()),
        )
```

- [ ] **Step 6: Run bridge command tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_bridge_commands.py::test_live_monitor_once_emits_waiting_result tests/unit/test_bridge_commands.py::test_live_monitor_rejects_non_positive_interval -q --no-cov
```

Expected: FAIL with `AttributeError` because `commands.live_monitoring` or `commands.live_monitor` is missing.

- [ ] **Step 7: Add bridge command handler**

Modify `src/simanalysis/bridge/commands.py`:

```python
import time

from simanalysis import live_monitoring, serialization, treatment
```

Add the handler near the Treatment handlers:

```python
def live_monitor(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    if args.interval <= 0:
        raise ValueError("Live monitor interval must be greater than zero")
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"
    monitor = live_monitoring.LiveMonitor(base, mods_dir)

    emit.start("live-monitor")
    while True:
        result = monitor.poll(_build_doctor_payload, treatment.create_plan)
        watched_count = int(result.get("watched_log_count", 0) or 0)
        emit.progress(
            watched_count,
            watched_count,
            stage=str(result.get("recommended_next_action", "waiting")),
            force=True,
        )
        if result.get("changed_logs") or args.once:
            emit.result(result)
        if args.once:
            emit.done()
            return
        time.sleep(args.interval)
```

Add the dispatch entry:

```python
    "live-monitor": live_monitor,
```

- [ ] **Step 8: Run Python bridge tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_bridge_main.py::test_live_monitor_command_is_dispatched tests/unit/test_bridge_commands.py::test_live_monitor_once_emits_waiting_result tests/unit/test_bridge_commands.py::test_live_monitor_rejects_non_positive_interval -q --no-cov
```

Expected: PASS with `3 passed`.

- [ ] **Step 9: Commit Task 4**

```bash
git add src/simanalysis/bridge/__init__.py src/simanalysis/bridge/commands.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py
git commit -m "feat: expose live monitor bridge command"
```

---

### Task 5: Tauri Sidecar Argument Support

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Write failing Rust argument-builder test**

Add this test in the existing Rust `#[cfg(test)] mod tests` block:

```rust
    #[test]
    fn builds_live_monitor_args_with_mods_interval_and_once() {
        let opts = AnalysisOptions {
            mods_path: Some("/Sims/Mods".into()),
            interval: Some(0.25),
            once: true,
            ..Default::default()
        };
        let args = build_args("live-monitor", "/Sims/The Sims 4", &opts).unwrap();
        assert_eq!(
            args,
            vec![
                "live-monitor",
                "/Sims/The Sims 4",
                "--mods",
                "/Sims/Mods",
                "--interval",
                "0.25",
                "--once",
            ]
        );
    }
```

- [ ] **Step 2: Run the Rust test to verify it fails**

Run:

```bash
cd src-tauri && cargo test builds_live_monitor_args_with_mods_interval_and_once
```

Expected: FAIL because `AnalysisOptions` has no `interval` or `once` fields, and `build_args` rejects `live-monitor`.

- [ ] **Step 3: Add live monitor options to `AnalysisOptions`**

Extend the struct:

```rust
    #[serde(default)]
    interval: Option<f64>,
    #[serde(default)]
    once: bool,
```

- [ ] **Step 4: Add the `live-monitor` arm to `build_args`**

Add this arm before the treatment commands:

```rust
        "live-monitor" => {
            args.push("live-monitor".into());
            args.push(path.into());
            if let Some(mods) = opts.mods_path.as_deref() {
                args.push("--mods".into());
                args.push(mods.into());
            }
            if let Some(interval) = opts.interval {
                if interval <= 0.0 {
                    return Err("live-monitor interval must be greater than zero".into());
                }
                args.push("--interval".into());
                args.push(interval.to_string());
            }
            if opts.once {
                args.push("--once".into());
            }
        }
```

- [ ] **Step 5: Add interval validation test**

Add this Rust test:

```rust
    #[test]
    fn live_monitor_rejects_non_positive_interval() {
        let opts = AnalysisOptions {
            interval: Some(0.0),
            ..Default::default()
        };
        let err = build_args("live-monitor", "/Sims/The Sims 4", &opts).unwrap_err();
        assert!(err.contains("interval must be greater than zero"));
    }
```

- [ ] **Step 6: Run Rust tests**

Run:

```bash
cd src-tauri && cargo test live_monitor
```

Expected: PASS for both live monitor tests.

- [ ] **Step 7: Commit Task 5**

```bash
git add src-tauri/src/lib.rs
git commit -m "feat: support live monitor sidecar args"
```

---

### Task 6: Validation Evidence And Safety Checks

**Files:**
- Create: `docs/superpowers/2026-05-31-live-monitoring-validation.md`

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
```

Expected: PASS.

- [ ] **Step 2: Run focused Treatment safety tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
```

Expected: PASS. The first test confirms dry-run planning does not write `_Simanalysis_Treatment`; the second protects existing saved-session behavior.

- [ ] **Step 3: Run Rust sidecar tests**

Run:

```bash
cd src-tauri && cargo test live_monitor
```

Expected: PASS.

- [ ] **Step 4: Run full Python unit test suite**

Run:

```bash
.venv/bin/python -m pytest tests/unit -q
```

Expected: PASS. Coverage output is expected because default pytest options enable coverage.

- [ ] **Step 5: Install Bandit if the worktree venv lacks it**

Run:

```bash
.venv/bin/python -m pip show bandit >/dev/null 2>&1 || uv pip install "bandit[toml]"
```

Expected: command exits 0.

- [ ] **Step 6: Run Bandit before push**

Run:

```bash
.venv/bin/python -m bandit -r src
```

Expected: no high-severity findings. If Bandit reports existing low-severity findings, record the exact finding IDs and file paths in the validation doc.

- [ ] **Step 7: Run synthetic read-only bridge validation**

Run:

```bash
fixture="/tmp/simanalysis-live-monitor-fixture"
rm -rf "$fixture"
mkdir -p "$fixture/Mods"
printf "old crash" > "$fixture/lastException.txt"
.venv/bin/simanalysis-bridge live-monitor "$fixture" --once > /tmp/simanalysis-live-monitor-once.ndjson
test ! -e "$fixture/_Simanalysis_Treatment"
```

Expected: command exits 0, emits a waiting result, and does not create `_Simanalysis_Treatment`.

- [ ] **Step 8: Run real-folder read-only validation**

Run:

```bash
.venv/bin/simanalysis-bridge live-monitor "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --once > /tmp/simanalysis-live-monitor-real-once.ndjson
```

Expected: command exits 0 and does not mutate the real Sims folder. The result should be `waiting` unless a new crash log appears during the command.

- [ ] **Step 9: Write validation note**

Create `docs/superpowers/2026-05-31-live-monitoring-validation.md`:

````markdown
# Live Monitoring validation

Date: 2026-05-31
Branch: `feat/live-monitoring`

## Commands

```text
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
cd src-tauri && cargo test live_monitor
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m bandit -r src
.venv/bin/simanalysis-bridge live-monitor /tmp/simanalysis-live-monitor-fixture --once
.venv/bin/simanalysis-bridge live-monitor "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --once
```

## Results

- Focused Live Monitoring and bridge tests: PASS
- Focused Treatment safety tests: PASS
- Rust live monitor sidecar tests: PASS
- Full Python unit suite: PASS
- Bandit: PASS
- Synthetic bridge validation: PASS; `_Simanalysis_Treatment` was not created.
- Real-folder read-only validation: PASS; no Sims folder mutation was performed.

## Notes

- Live Monitoring runs Treatment planning with `save=false`.
- `--once` establishes a fresh baseline and reports `waiting` when no log changes during that invocation.
- Live Monitoring does not create a Treatment manifest and does not move files.
````

- [ ] **Step 10: Commit validation note**

```bash
git add docs/superpowers/2026-05-31-live-monitoring-validation.md
git commit -m "docs: validate live monitoring"
```

---

## Final Pre-Push Checklist

- [ ] `git status --short --branch` shows only intentional committed work.
- [ ] `git log --oneline --decorate -5` shows the Live Monitoring commits on `feat/live-monitoring`.
- [ ] Bandit has been run after code changes.
- [ ] No command wrote to `/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4/_Simanalysis_Treatment`.
- [ ] No command moved files in the real Sims folder.
- [ ] If pushing, run:

```bash
git push -u github feat/live-monitoring
```
