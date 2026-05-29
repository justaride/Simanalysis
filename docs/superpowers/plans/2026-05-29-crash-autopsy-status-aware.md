# Crash Autopsy — Status-Aware Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every crash suspect a status — `active` (in `Mods/`), `disabled` (found in a `_Disabled_*`/`_Quarantine_*` folder), or `not_installed` (best-guess from the crash path) — so culprits the user already disabled/removed are named instead of vanishing into "unknown".

**Architecture:** `build_module_index` scans `Mods/` plus extra disabled/quarantine roots, recording each mod's status (active beats disabled) in `self.mod_status`. `classify_frame` stamps `frame.mod_status`. `analyze` propagates status to each `Suspect`, adds a best-effort `not_installed` suspect for crashes whose only non-game frames are unknown, and reports per-status counts. The CLI auto-discovers the sibling `_Disabled_*`/`_Quarantine_*` folders and groups the txt report by status.

**Tech Stack:** Python 3.9+ (stdlib `zipfile`, `pathlib`), `click`, pytest. Spec: `docs/superpowers/specs/2026-05-29-crash-autopsy-status-aware-design.md`. Builds on the merged v1 (`main` @ `93f0096`).

**Verified current state (main):** `crash_analyzer.py` has `_norm`, `_archive_names`, `CrashAnalyzer.__init__(framework_fraction, framework_deepest_fraction)`, `build_module_index(mods_dir) -> dict[str,str]`, `classify_frame(frame, index)`, `analyze(reports, index)`. `models.py`: `TracebackFrame` (raw_path, module_path, line, func, kind, mod_name) and `Suspect` (mod_name, confidence, reason, evidence) use `Optional[...]`. `serialization.crash_result_to_dict` emits per-suspect `{mod, confidence, reason, evidence}`. CLI `crash` builds the index from `mods_dir` only. Tests live in `tests/unit/analyzers/test_crash_analyzer.py`, `tests/unit/test_serialization.py`, `tests/unit/test_cli.py`.

---

## File Structure
- Modify `src/simanalysis/models.py` — add `TracebackFrame.mod_status`, `Suspect.status`.
- Modify `src/simanalysis/analyzers/crash_analyzer.py` — status constants, `_status_for`, `_besteffort_name`, `self.mod_status`, status-aware `build_module_index`, `classify_frame` stamps status, `analyze` propagates status + best-effort + per-status summary.
- Modify `src/simanalysis/serialization.py` — add `status` to each serialized suspect.
- Modify `src/simanalysis/cli.py` — auto-discover disabled roots; status-grouped txt report.
- Modify tests: `tests/unit/analyzers/test_crash_analyzer.py`, `tests/unit/test_serialization.py`, `tests/unit/test_cli.py`.

Define `PY=~/src/Simanalysis/.venv/bin` for all steps. Every commit ends with:
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## Task 1: Worktree & baseline

**Files:** none (environment).

- [ ] **Step 1: Worktree off the merged main, reuse the venv**
```bash
cd ~/src/Simanalysis
git fetch github main
git worktree add ~/src/Simanalysis-crash2 -b feat/crash-status-aware github/main
```
- [ ] **Step 2: Baseline green** (run from the worktree; the worktree's `tests/conftest.py` puts its own `src` first)
```bash
cd ~/src/Simanalysis-crash2
~/src/Simanalysis/.venv/bin/python -m pytest tests/unit -q --no-cov 2>&1 | tail -2
```
Expected: all pass (≈244).

---

## Task 2: Models — status fields

**Files:** Modify `src/simanalysis/models.py`

- [ ] **Step 1: Add `mod_status` to `TracebackFrame`** — change the `mod_name` line of `TracebackFrame` from:
```python
    mod_name: Optional[str] = None  # set when kind == "mod"
```
to:
```python
    mod_name: Optional[str] = None  # set when kind == "mod"
    mod_status: Optional[str] = None  # "active" | "disabled" | "not_installed", set with mod_name
```

- [ ] **Step 2: Add `status` to `Suspect`** — change the `Suspect` dataclass body from:
```python
    mod_name: str
    confidence: str  # "high" | "medium" | "low"
    reason: str
    evidence: list[TracebackFrame] = field(default_factory=list)
```
to:
```python
    mod_name: str
    confidence: str  # "high" | "medium" | "low"
    reason: str
    evidence: list[TracebackFrame] = field(default_factory=list)
    status: str = "active"  # "active" | "disabled" | "not_installed"
```

- [ ] **Step 3: Verify import + suite still green**
```bash
$PY/python -c "from simanalysis.models import TracebackFrame, Suspect; print(TracebackFrame('x').mod_status, Suspect('m','high','r').status)"
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```
Expected: prints `None active`; suite green.

- [ ] **Step 4: Commit**
```bash
git add src/simanalysis/models.py
git commit -m "feat: add status fields to crash models (frame.mod_status, Suspect.status)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Status-aware module index + frame stamping

**Files:** Modify `src/simanalysis/analyzers/crash_analyzer.py`; Modify `tests/unit/analyzers/test_crash_analyzer.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/analyzers/test_crash_analyzer.py`):
```python
def test_status_for_classifies_disabled_paths():
    from simanalysis.analyzers.crash_analyzer import _status_for

    assert _status_for(Path("/x/The Sims 4/Mods/CoolMod.ts4script")) == "active"
    assert _status_for(Path("/x/The Sims 4/_Disabled_adeepindigo_2026/m.ts4script")) == "disabled"
    assert _status_for(Path("/x/The Sims 4/_Quarantine_Bad/m.ts4script")) == "disabled"
    assert _status_for(Path("/x/The Sims 4/Mods/_Quarantine_UI/m.ts4script")) == "disabled"


def test_build_module_index_records_status_and_extra_roots(tmp_path: Path):
    mods = tmp_path / "Mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "Active.ts4script", "w") as zf:
        zf.writestr("activemod/a.pyc", b"\x00")
    disabled = tmp_path / "_Disabled_Old_2026"
    disabled.mkdir()
    with zipfile.ZipFile(disabled / "Gone.ts4script", "w") as zf:
        zf.writestr("gonemod/g.pyc", b"\x00")

    a = CrashAnalyzer()
    index = a.build_module_index(mods, extra_roots=[disabled])
    assert index["activemod/a.py"] == "Active.ts4script"
    assert index["gonemod/g.py"] == "Gone.ts4script"
    assert a.mod_status["active.ts4script"] == "active"
    assert a.mod_status["gone.ts4script"] == "disabled"


def test_active_beats_disabled_for_same_mod(tmp_path: Path):
    mods = tmp_path / "Mods"
    mods.mkdir()
    disabled = tmp_path / "_Disabled_Copies"
    disabled.mkdir()
    for root in (mods, disabled):
        with zipfile.ZipFile(root / "Dup.ts4script", "w") as zf:
            zf.writestr("dup/x.pyc", b"\x00")
    a = CrashAnalyzer()
    a.build_module_index(mods, extra_roots=[disabled])
    assert a.mod_status["dup.ts4script"] == "active"  # installed copy wins


def test_classify_frame_stamps_disabled_status():
    a = CrashAnalyzer()
    a.mod_status = {"gone.ts4script": "disabled"}
    index = {"gonemod/g.py": "Gone.ts4script"}
    fr = TracebackFrame(raw_path=r"F:\proj\gonemod\g.py")
    a.classify_frame(fr, index)
    assert fr.kind == "mod"
    assert fr.mod_name == "Gone.ts4script"
    assert fr.mod_status == "disabled"
```

- [ ] **Step 2: Run — expect failures** (`_status_for` missing; `mod_status` attribute / `extra_roots` kw missing)
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov 2>&1 | tail -6
```

- [ ] **Step 3: Implement.** In `crash_analyzer.py`:

(a) Add the import (top, with the other stdlib imports — after `import zipfile`):
```python
from collections.abc import Iterable
```

(b) Add status constants + helpers after `FRAMEWORK_DEEPEST_FRACTION = 0.3`:
```python
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
STATUS_NOT_INSTALLED = "not_installed"
# Path segments (case-insensitive prefixes) that mark a deliberately set-aside mod copy.
_DISABLED_MARKERS = ("_disabled", "_quarantine")


def _status_for(path: Path) -> str:
    """active, unless any path segment marks a disabled/quarantine folder."""
    for part in Path(path).parts:
        pl = part.lower()
        if any(pl.startswith(m) for m in _DISABLED_MARKERS):
            return STATUS_DISABLED
    return STATUS_ACTIVE
```

(c) In `__init__`, add `self.mod_status` (after the two existing assignments):
```python
        self.mod_status: dict[str, str] = {}  # ts4script filename (lowercased) -> status
```

(d) Replace `build_module_index` with the status-aware, multi-root version:
```python
    def build_module_index(
        self, mods_dir: str | Path, extra_roots: Iterable[str | Path] = ()
    ) -> dict[str, str]:
        """Map each installed .ts4script's internal module path -> the .ts4script filename,
        and record each mod's status in self.mod_status (active beats disabled).

        Sims 4 scripts ship COMPILED modules (.pyc); traceback frames cite the original
        .py source path, so .pyc entries are normalized to .py before indexing. Besides
        mods_dir, any extra_roots (e.g. sibling _Disabled_*/_Quarantine_* folders) are
        scanned so set-aside culprits are still named.
        """
        self.mod_status = {}
        index: dict[str, str] = {}
        for root in [Path(mods_dir), *(Path(r) for r in extra_roots)]:
            for ts4 in root.rglob("*.ts4script"):
                key = ts4.name.lower()
                status = _status_for(ts4)
                prev = self.mod_status.get(key)
                self.mod_status[key] = (
                    STATUS_ACTIVE if STATUS_ACTIVE in (prev, status) else STATUS_DISABLED
                )
                for name in _archive_names(ts4):
                    if name.endswith(".pyc"):
                        index[_norm(name[:-1])] = ts4.name  # 'module.pyc' -> 'module.py'
                    elif name.endswith(".py"):
                        index[_norm(name)] = ts4.name
        return index
```

(e) In `classify_frame`, stamp `mod_status` on both mod-matching branches. Change the `.ts4script/` branch from:
```python
            frame.mod_name = head.split("/")[-1] + ".ts4script"
            return
```
to:
```python
            frame.mod_name = head.split("/")[-1] + ".ts4script"
            frame.mod_status = self.mod_status.get(frame.mod_name.lower(), STATUS_ACTIVE)
            return
```
and change the index-match branch from:
```python
            frame.mod_name = index[best]
            return
```
to:
```python
            frame.mod_name = index[best]
            frame.mod_status = self.mod_status.get(frame.mod_name.lower(), STATUS_ACTIVE)
            return
```

- [ ] **Step 4: Run — expect pass**, then full unit suite green.
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov 2>&1 | tail -2
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```

- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/analyzers/crash_analyzer.py tests/unit/analyzers/test_crash_analyzer.py
git commit -m "feat: status-aware module index (active/disabled, extra roots) + frame status" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Analyze — propagate status, best-effort not_installed, per-status summary

**Files:** Modify `src/simanalysis/analyzers/crash_analyzer.py`; Modify `tests/unit/analyzers/test_crash_analyzer.py`

- [ ] **Step 1: Write the failing tests** (append):
```python
def test_besteffort_name_no_doubling():
    from simanalysis.analyzers.crash_analyzer import _besteffort_name

    assert _besteffort_name(r"E:\x\adeepindigo\career.py") == "adeepindigo/career.py"
    assert _besteffort_name("thing.py") == "thing.py"
    assert _besteffort_name("x/thing.py/thing.py") == "thing.py"  # consecutive dup collapsed


def test_disabled_mod_is_named_with_status():
    a = CrashAnalyzer()
    a.mod_status = {"gone.ts4script": "disabled"}
    index = {"gonemod/g.py": "Gone.ts4script"}
    reports = [_report(r"Core\sims4\u.py", r"F:\p\gonemod\g.py")]
    result = a.analyze(reports, index)
    top = result.findings[0].suspects[0]
    assert top.mod_name == "Gone.ts4script"
    assert top.status == "disabled"
    assert result.ranked_mods[0]["status"] == "disabled"
    assert result.summary["disabled_culprits"] == 1


def test_not_installed_culprit_surfaced_from_unknown_frame():
    # No matching mod on disk, only an unknown non-game frame -> best-effort not_installed suspect
    a = CrashAnalyzer()
    reports = [_report(r"Core\sims4\u.py", r"Z:\removedmod\logic.py")]
    result = a.analyze(reports, {})
    sus = result.findings[0].suspects
    assert sus
    assert sus[0].status == "not_installed"
    assert sus[0].confidence == "low"
    assert "removedmod" in sus[0].mod_name
    assert result.summary["not_installed_culprits"] == 1
    assert result.summary["base_game_only"] == 0  # no longer mislabeled as base-game


def test_active_culprit_summary_count():
    index = {"moda/a.py": "ModA.ts4script"}
    reports = [_report(r"Core\sims4\u.py", r"y\moda\a.py")]
    result = CrashAnalyzer().analyze(reports, index)
    assert result.summary["active_culprits"] == 1
    assert result.findings[0].suspects[0].status == "active"
```

- [ ] **Step 2: Run — expect failures**
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov 2>&1 | tail -8
```

- [ ] **Step 3: Implement.**

(a) Add `_besteffort_name` after `_status_for`:
```python
def _besteffort_name(raw_path: str) -> str:
    """A rough culprit label for a frame matching no installed mod (status not_installed)."""
    segs = [s for s in _norm(raw_path).split("/") if s]
    if not segs:
        return "unknown"
    tail = segs[-2:] if len(segs) >= 2 else segs[-1:]
    out: list[str] = []
    for s in tail:
        if not out or out[-1] != s:  # collapse consecutive duplicates (avoid 'x.py/x.py')
            out.append(s)
    return "/".join(out)
```

(b) Replace the per-crash findings loop and the summary in `analyze`. Find the block that begins:
```python
        findings: list[CrashFinding] = []
        top_counts: dict[str, int] = {}
        base_game_only = 0

        for r in reports:
```
…through the end of `analyze` (the `return CrashAnalysisResult(...)` line) and replace the whole region with:
```python
        findings: list[CrashFinding] = []
        top_counts: dict[str, int] = {}
        ranked_status: dict[str, str] = {}
        status_counts = {STATUS_ACTIVE: 0, STATUS_DISABLED: 0, STATUS_NOT_INSTALLED: 0}
        base_game_only = 0

        for r in reports:
            mod_frames = [f for f in r.frames if f.kind == "mod" and f.mod_name]
            if not mod_frames:
                unknowns = [f for f in r.frames if f.kind == "unknown"]
                if unknowns:  # best-effort: deepest unknown frame names a not-installed culprit
                    deepest = unknowns[-1]
                    deepest.mod_status = STATUS_NOT_INSTALLED
                    name = _besteffort_name(deepest.raw_path)
                    suspect = Suspect(
                        mod_name=name,
                        confidence="low",
                        reason=f"referenced but not installed: {deepest.raw_path}",
                        evidence=[deepest],
                        status=STATUS_NOT_INSTALLED,
                    )
                    top_counts[name] = top_counts.get(name, 0) + 1
                    ranked_status[name] = STATUS_NOT_INSTALLED
                    status_counts[STATUS_NOT_INSTALLED] += 1
                    findings.append(CrashFinding(report=r, suspects=[suspect]))
                    continue
                base_game_only += 1
                findings.append(CrashFinding(report=r))
                continue
            ordered = list(reversed(mod_frames))  # most-recent-call-last => deepest first
            non_fw = [f for f in ordered if f.mod_name not in frameworks]
            picked = non_fw if non_fw else ordered

            suspects: list[Suspect] = []
            seen: set[str] = set()
            for i, f in enumerate(picked):
                mod_name = f.mod_name
                if not mod_name or mod_name in seen:
                    continue
                seen.add(mod_name)
                if mod_name in frameworks:
                    conf = "low"
                elif i == 0 and f.module_path in index:
                    conf = "high"
                else:
                    conf = "medium"
                suspects.append(
                    Suspect(
                        mod_name=mod_name,
                        confidence=conf,
                        reason=f"implicated at: {f.raw_path}",
                        evidence=[f],
                        status=f.mod_status or STATUS_ACTIVE,
                    )
                )
            if suspects:
                top = suspects[0]
                top_counts[top.mod_name] = top_counts.get(top.mod_name, 0) + 1
                ranked_status[top.mod_name] = top.status
                status_counts[top.status] = status_counts.get(top.status, 0) + 1
            findings.append(CrashFinding(report=r, suspects=suspects))

        ranked: list[dict] = sorted(
            [
                {
                    "mod": m,
                    "top_suspect_count": top_counts[m],
                    "crash_count": mod_in_crash.get(m, 0),
                    "status": ranked_status.get(m, STATUS_ACTIVE),
                }
                for m in top_counts
            ],
            key=lambda d: (-d["top_suspect_count"], -d["crash_count"], d["mod"]),
        )
        summary = {
            "reports": len(reports),
            "attributable": attributable,
            "active_culprits": status_counts[STATUS_ACTIVE],
            "disabled_culprits": status_counts[STATUS_DISABLED],
            "not_installed_culprits": status_counts[STATUS_NOT_INSTALLED],
            "base_game_only": base_game_only,
            "frameworks_downweighted": sorted(frameworks),
            "game_versions": sorted({r.game_version for r in reports if r.game_version}),
        }
        return CrashAnalysisResult(summary=summary, ranked_mods=ranked, findings=findings)
```
(This removes the old `mod_name: str = f.mod_name  # type: ignore[assignment]` line — the new `if not mod_name` guard narrows the type, so no `type: ignore` is needed.)

- [ ] **Step 4: Run — expect pass**, then full unit suite green (the existing `test_analyze_ranks_and_downweights_framework` still holds: `base_game_only == 1`, `attributable == 3`).
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov 2>&1 | tail -2
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```

- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/analyzers/crash_analyzer.py tests/unit/analyzers/test_crash_analyzer.py
git commit -m "feat: propagate suspect status, best-effort not-installed culprits, per-status summary" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Serialization — include status

**Files:** Modify `src/simanalysis/serialization.py`; Modify `tests/unit/test_serialization.py`

- [ ] **Step 1: Update the failing test** — in `tests/unit/test_serialization.py`, find `test_crash_result_to_dict_shape`. The `Suspect(...)` it builds has no status (defaults to `"active"`). Change its suspect-equality assertion from:
```python
    assert f0["suspects"][0] == {"mod": "ModA.ts4script", "confidence": "high",
                                 "reason": "r", "evidence": ["x/moda/a.py"]}
```
to:
```python
    assert f0["suspects"][0] == {"mod": "ModA.ts4script", "confidence": "high",
                                 "status": "active",
                                 "reason": "r", "evidence": ["x/moda/a.py"]}
```

- [ ] **Step 2: Run — expect failure** (missing `status` key)
```bash
$PY/python -m pytest tests/unit/test_serialization.py::test_crash_result_to_dict_shape -q --no-cov 2>&1 | tail -8
```

- [ ] **Step 3: Implement** — in `crash_result_to_dict`, add `status` to the per-suspect dict. Change:
```python
                    {
                        "mod": s.mod_name,
                        "confidence": s.confidence,
                        "reason": s.reason,
                        "evidence": [fr.raw_path for fr in s.evidence],
                    }
```
to:
```python
                    {
                        "mod": s.mod_name,
                        "confidence": s.confidence,
                        "status": s.status,
                        "reason": s.reason,
                        "evidence": [fr.raw_path for fr in s.evidence],
                    }
```

- [ ] **Step 4: Run — expect pass**, full suite green.
```bash
$PY/python -m pytest tests/unit/test_serialization.py -q --no-cov 2>&1 | tail -2
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```

- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/serialization.py tests/unit/test_serialization.py
git commit -m "feat: include suspect status in crash JSON serialization" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: CLI — auto-scan disabled folders + status-grouped report

**Files:** Modify `src/simanalysis/cli.py`; Modify `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test** (append to `tests/unit/test_cli.py`):
```python
def test_crash_command_names_disabled_culprit(tmp_path):
    import zipfile
    from click.testing import CliRunner
    from simanalysis.cli import cli

    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    # the culprit mod lives in a sibling _Disabled_* folder, not in Mods/
    disabled = sims4 / "_Disabled_adeepindigo_2026"
    disabled.mkdir()
    with zipfile.ZipFile(disabled / "adeepindigo_core.ts4script", "w") as zf:
        zf.writestr("adeepindigo/core.pyc", b"\x00")

    (sims4 / "lastException_1.txt").write_text(
        "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
        "Traceback (most recent call last):&#13;&#10;"
        'File "Core\\sims4\\utils.py", line 1, in w&#13;&#10;'
        'File "E:\\proj\\adeepindigo\\core.py", line 7, in run&#13;&#10;'
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    import json
    data = json.loads(result.output)
    top = data["ranked_mods"][0]
    assert top["mod"] == "adeepindigo_core.ts4script"
    assert top["status"] == "disabled"
    assert data["summary"]["disabled_culprits"] == 1
```

- [ ] **Step 2: Run — expect failure** (culprit currently unattributed → empty `ranked_mods`)
```bash
$PY/python -m pytest tests/unit/test_cli.py::test_crash_command_names_disabled_culprit -q --no-cov 2>&1 | tail -8
```

- [ ] **Step 3: Implement** — in `cli.py`'s `crash` command:

(a) Build the index over `mods_dir` plus auto-discovered disabled siblings. Replace:
```python
    analyzer = CrashAnalyzer()
    index = analyzer.build_module_index(mods_dir) if mods_dir.exists() else {}
    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors
```
with:
```python
    analyzer = CrashAnalyzer()
    # Auto-discover deliberately set-aside folders so disabled/quarantined culprits are named.
    extra_roots = [
        d
        for d in base.iterdir()
        if d.is_dir()
        and (d.name.lower().startswith("_disabled") or d.name.lower().startswith("_quarantine"))
    ]
    index = analyzer.build_module_index(mods_dir, extra_roots=extra_roots)
    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors
```
(`build_module_index` tolerates a missing `mods_dir` — `rglob` on a non-existent path yields nothing — so the old `.exists()` guard is no longer needed.)

(b) Replace the txt-report `else:` block (everything from `lines = [` through `text = "\n".join(lines)`) with the status-grouped version:
```python
        s = result.summary
        lines = [
            f"🔬 Crash Autopsy — {len(log_files)} log file(s), {s['reports']} crash(es)",
            f"   active: {s['active_culprits']}  |  already-disabled: {s['disabled_culprits']}"
            f"  |  not-installed: {s['not_installed_culprits']}  |  base-game-only: {s['base_game_only']}",
            "",
        ]
        groups = [
            ("active", "[ACTIVE] mods still implicated — fix these"),
            ("disabled", "[DISABLED] already set aside — likely handled"),
            ("not_installed", "[NOT INSTALLED] referenced but not on disk — best guess"),
        ]
        any_shown = False
        for status_key, header in groups:
            entries = [e for e in result.ranked_mods if e.get("status") == status_key]
            if not entries:
                continue
            any_shown = True
            lines.append(f"{header}:")
            for entry in entries[:limit]:
                lines.append(
                    f"  - {entry['mod']}  — top suspect in {entry['top_suspect_count']} crash(es)"
                    f", seen in {entry['crash_count']}"
                )
            lines.append("")
        if not any_shown:
            lines.append("  (no mod-attributable crashes found)")
        text = "\n".join(lines).rstrip()
```

- [ ] **Step 4: Run — expect pass**, then full unit suite + ruff + mypy + bandit green.
```bash
$PY/python -m pytest tests/unit/test_cli.py -q --no-cov 2>&1 | tail -2
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
$PY/ruff check . && $PY/ruff format . && $PY/python -m mypy src/simanalysis 2>&1 | tail -1
$PY/python -m bandit -r src/simanalysis -c pyproject.toml 2>&1 | tail -2
```
Expected: pass; ruff clean; mypy `Success`; bandit `No issues identified.` (bandit runs in CI's `security` job — do not skip it).

- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/cli.py tests/unit/test_cli.py
git commit -m "feat: auto-scan disabled folders and group crash report by suspect status" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Real-log re-validation (manual — not a committed test)

**Files:** none (verification).

- [ ] **Step 1: Run the status-aware autopsy over the real logs**
```bash
cd ~/src/Simanalysis-crash2
PYTHONPATH=src $PY/python -m simanalysis.cli crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --recursive --limit 15
```
- [ ] **Step 2: Sanity-check** — confirm: `delimaci_teenparamediccareer` remains the top **[ACTIVE]** culprit; `adeepindigo_*` now appears under **[DISABLED]** (named from its `_Disabled_*` folder); injectors/cores stay down-weighted; the summary shows non-zero `disabled` and the `base-game-only` count dropped versus v1 (since not-installed frames are no longer swept into it). Record the result; if attribution looks off, that's a finding to iterate on before merge.

---

## Self-review notes (completed)
- **Spec coverage:** status field (Task 2) ↔ spec §3; status-aware index + extra roots + active-precedence (Task 3) ↔ §1; classify stamping + best-effort + per-status summary (Tasks 3–4) ↔ §2–§3; serialization status (Task 5) ↔ §4; CLI auto-scan + grouped report (Task 6) ↔ §4; real-log re-validation (Task 7) ↔ spec Testing. Out-of-scope items (UI/desync, treatment, cache-backup scan, desktop view) intentionally absent.
- **Placeholders:** none; every step has complete code + exact commands.
- **Type/name consistency:** `STATUS_ACTIVE/DISABLED/NOT_INSTALLED`, `mod_status`, `_status_for`, `_besteffort_name`, `extra_roots`, and summary keys (`active_culprits`/`disabled_culprits`/`not_installed_culprits`/`base_game_only`) are consistent across tasks and tests. `self.mod_status` is keyed by lowercased `.ts4script` filename; classify looks up with `.lower()`. `Suspect.status` defaults to `active` so pre-existing constructions stay valid.
- **Back-compat:** existing analyzer/CLI tests still hold (`base_game_only`/`attributable` unchanged in the framework test; CLI json `ranked_mods[0]["mod"]` unchanged; `--limit` truncation still yields 2 in the all-active limit test); only the serialization shape test is updated (Task 5) to include the new `status` key. bandit is part of the Task 6 gate (CI `security` job).
