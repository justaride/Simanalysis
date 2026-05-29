# Crash Autopsy v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sweep all `lastException*.txt` Sims 4 crash logs, attribute each crash to the most-likely culprit `.ts4script`, and emit a whole-library ranked report with per-crash drill-down — via a new `simanalysis crash` CLI command.

**Architecture:** A tolerant `exception_log` parser (BE/vanilla XML → `CrashReport`s) feeds a `CrashAnalyzer` that builds a module index from installed `.ts4script`s (full internal zip paths), attributes each traceback frame by longest-suffix module match, down-weights injector/framework mods (curated list + a self-calibrating "appears in ≥50% of crashes" rule), selects a per-crash culprit, and aggregates a ranked list. Pure engine + CLI; structured output is desktop-ready.

**Tech Stack:** Python 3.9+ (stdlib `re`, `html`, `zipfile`, `hashlib`), `click` CLI, pytest. Spec: `docs/superpowers/specs/2026-05-29-crash-autopsy-design.md`.

**Verified APIs:** `ScriptAnalyzer(path).module_paths` and `ScriptModule.path` give **full internal zip paths** (`script.py:238/252`). CLI uses `@cli.command()` + `@click.argument`/`@click.option` (`cli.py`). `models.py` uses `Optional[...]` + `list[...]` (no `X | None`).

---

## File Structure
- Modify `src/simanalysis/models.py` — add `TracebackFrame`, `CrashReport`, `Suspect`, `CrashFinding`, `CrashAnalysisResult`.
- Create `src/simanalysis/parsers/exception_log.py` — `parse_exception_file(path) -> list[CrashReport]`.
- Create `src/simanalysis/analyzers/crash_analyzer.py` — `CrashAnalyzer` (`build_module_index`, `classify_frame`, `analyze`).
- Modify `src/simanalysis/serialization.py` — add `crash_result_to_dict`.
- Modify `src/simanalysis/cli.py` — add the `crash` command.
- Create `tests/unit/parsers/test_exception_log.py`, `tests/unit/analyzers/test_crash_analyzer.py`; modify `tests/unit/test_cli.py`.

---

## Task 1: Prerequisites & branch

**Files:** none (environment).

- [ ] **Step 1: Worktree off the latest main + reuse the venv**
```bash
cd ~/src/Simanalysis
git fetch github main
git worktree add ~/src/Simanalysis-crash -b feat/crash-autopsy github/main
```
- [ ] **Step 2: Baseline green** (run from the worktree; reuse the existing venv)
```bash
cd ~/src/Simanalysis-crash
~/src/Simanalysis/.venv/bin/python -m pytest tests/unit -q --no-cov
```
Expected: all pass (the worktree's `tests/conftest.py` puts its own `src` first). Define `PY=~/src/Simanalysis/.venv/bin` for later steps. Commit messages end with:
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## Task 2: Data models

**Files:** Modify `src/simanalysis/models.py`

- [ ] **Step 1: Add the dataclasses** (append after `DBPFResource`; keep the file's `Optional[...]` + `list[...]` style — do NOT use `X | None`):
```python
@dataclass
class TracebackFrame:
    """One frame of a crash traceback."""

    raw_path: str
    module_path: Optional[str] = None  # normalized package-relative tail, if attributed
    line: Optional[int] = None
    func: Optional[str] = None
    kind: str = "unknown"  # "game" | "mod" | "unknown"
    mod_name: Optional[str] = None  # set when kind == "mod"


@dataclass
class CrashReport:
    """A single parsed crash (one <report> block)."""

    source_file: str
    report_type: str
    message: str
    frames: list[TracebackFrame] = field(default_factory=list)
    exception_class: Optional[str] = None
    creator_tag: Optional[str] = None
    created: Optional[str] = None
    game_version: Optional[str] = None
    be_advice: Optional[str] = None
    signature: str = ""  # dedupe key


@dataclass
class Suspect:
    """A mod implicated in a crash, with confidence."""

    mod_name: str
    confidence: str  # "high" | "medium" | "low"
    reason: str
    evidence: list[TracebackFrame] = field(default_factory=list)


@dataclass
class CrashFinding:
    """One analyzed crash and its ranked suspects (empty => base-game/unattributable)."""

    report: CrashReport
    suspects: list[Suspect] = field(default_factory=list)


@dataclass
class CrashAnalysisResult:
    """Whole-library crash analysis output."""

    summary: dict = field(default_factory=dict)
    ranked_mods: list[dict] = field(default_factory=list)
    findings: list[CrashFinding] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
```
- [ ] **Step 2: Verify import + no regressions**
```bash
$PY/python -c "from simanalysis.models import TracebackFrame, CrashReport, Suspect, CrashFinding, CrashAnalysisResult; print('ok')"
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```
Expected: `ok`; suite still green.
- [ ] **Step 3: Commit**
```bash
git add src/simanalysis/models.py
git commit -m "feat: add crash-analysis data models" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Exception-log parser

**Files:** Create `src/simanalysis/parsers/exception_log.py`; Create `tests/unit/parsers/test_exception_log.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/parsers/test_exception_log.py
from pathlib import Path

from simanalysis.parsers.exception_log import parse_exception_file

BE_XML = (
    '<?xml version="1.0" ?><root>\n'
    "<BetterExceptions><Advice>This is likely due to bad tuning.</Advice></BetterExceptions>"
    "<report><version>2</version><type>desync</type>"
    "<createtime>2026-05-25 21:17:18</createtime>"
    "<buildsignature>Local.1.124.55.1230</buildsignature>"
    "<categoryid>injector.py:26</categoryid>"
    "<desyncdata>[cjiang] Error occurred within the tag (UnavailablePackSafeResourceError)&#13;&#10;"
    "Traceback (most recent call last):&#13;&#10;"
    '  File "Core\\sims4\\utils.py", line 179, in wrapper&#13;&#10;'
    '  File "E:\\x\\NisaK\\utilities\\nisa_injector.py", line 25, in _inject&#13;&#10;'
    '  File "F:\\y\\modcool\\thing.py", line 7, in run&#13;&#10;'
    "</desyncdata></report>"
    # duplicate of the same crash -> should dedupe
    "<report><type>desync</type>"
    "<desyncdata>[cjiang] Error occurred within the tag (UnavailablePackSafeResourceError)&#13;&#10;"
    "Traceback (most recent call last):&#13;&#10;"
    '  File "Core\\sims4\\utils.py", line 179, in wrapper&#13;&#10;'
    '  File "E:\\x\\NisaK\\utilities\\nisa_injector.py", line 25, in _inject&#13;&#10;'
    '  File "F:\\y\\modcool\\thing.py", line 7, in run&#13;&#10;'
    "</desyncdata></report>"
    # a pure UI desync with no traceback -> should be skipped
    "<report><type>desync</type><desyncdata>Error: no category&#13;&#10;</desyncdata></report>"
    "</root>"
)


def test_parses_be_xml_dedupes_and_skips_non_traceback(tmp_path: Path):
    f = tmp_path / "lastException_1.txt"
    f.write_text(BE_XML, encoding="utf-8")

    reports = parse_exception_file(f)

    assert len(reports) == 1  # duplicate deduped, no-traceback skipped
    r = reports[0]
    assert r.report_type == "desync"
    assert r.exception_class == "UnavailablePackSafeResourceError"
    assert r.creator_tag == "cjiang"
    assert r.created == "2026-05-25 21:17:18"
    assert r.game_version == "Local.1.124.55.1230"
    assert r.be_advice == "This is likely due to bad tuning."
    assert [fr.line for fr in r.frames] == [179, 25, 7]
    assert r.frames[1].func == "_inject"
    assert "nisa_injector.py" in r.frames[1].raw_path
    assert r.signature  # set


def test_malformed_file_does_not_raise(tmp_path: Path):
    f = tmp_path / "lastException_bad.txt"
    f.write_text("<root><report><desyncdata>Traceback (most recent", encoding="utf-8")
    assert parse_exception_file(f) == []  # truncated/unterminated -> nothing, no exception
```
- [ ] **Step 2: Run — expect failure** (`ModuleNotFoundError`)
```bash
$PY/python -m pytest tests/unit/parsers/test_exception_log.py -q --no-cov
```
- [ ] **Step 3: Implement**
```python
# src/simanalysis/parsers/exception_log.py
"""Tolerant parser for Sims 4 lastException*.txt crash logs (Better-Exceptions or vanilla XML)."""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from simanalysis.models import CrashReport, TracebackFrame

_REPORT_RE = re.compile(r"<report>(.*?)</report>", re.DOTALL)
_ADVICE_RE = re.compile(r"<Advice>(.*?)</Advice>", re.DOTALL)
_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\S+))?')
_EXC_RE = re.compile(r"\(([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\)")
_CREATOR_RE = re.compile(r"^\s*\[([^\]]+)\]")


def _tag(block: str, name: str) -> "str | None":
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def parse_exception_file(path: "str | Path") -> list[CrashReport]:
    """Parse one lastException*.txt into deduped CrashReports (script exceptions only)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    advice_m = _ADVICE_RE.search(text)
    be_advice = html.unescape(advice_m.group(1)).strip() if advice_m else None

    reports: list[CrashReport] = []
    seen: set[str] = set()

    for block in _REPORT_RE.findall(text):
        data = _tag(block, "desyncdata") or ""
        if "Traceback" not in data:
            continue  # pure UI/desync, no script traceback -> out of v1 scope
        frames = [
            TracebackFrame(raw_path=p, line=int(ln), func=fn or None)
            for (p, ln, fn) in _FRAME_RE.findall(data)
        ]
        if not frames:
            continue

        lines = [ln for ln in data.splitlines() if ln.strip()]
        message = lines[0] if lines else ""
        exc_m = _EXC_RE.search(message) or _EXC_RE.search(data)
        cre_m = _CREATOR_RE.match(message)

        report = CrashReport(
            source_file=str(path),
            report_type=_tag(block, "type") or "unknown",
            message=message,
            frames=frames,
            exception_class=exc_m.group(1) if exc_m else None,
            creator_tag=cre_m.group(1) if cre_m else None,
            created=_tag(block, "createtime"),
            game_version=_tag(block, "buildsignature"),
            be_advice=be_advice,
        )
        report.signature = hashlib.sha1(
            (
                str(report.exception_class)
                + report.message
                + "|".join(f.raw_path for f in frames)
            ).encode("utf-8", "replace")
        ).hexdigest()

        if report.signature in seen:
            continue
        seen.add(report.signature)
        reports.append(report)

    return reports
```
- [ ] **Step 4: Run — expect pass** (2 tests)
```bash
$PY/python -m pytest tests/unit/parsers/test_exception_log.py -q --no-cov
```
- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/parsers/exception_log.py tests/unit/parsers/test_exception_log.py
git commit -m "feat: tolerant lastException parser (BE/vanilla XML -> CrashReport)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: CrashAnalyzer (module index, frame classification, analyze)

**Files:** Create `src/simanalysis/analyzers/crash_analyzer.py`; Create `tests/unit/analyzers/test_crash_analyzer.py`

- [ ] **Step 1: Write the failing test**
```python
# tests/unit/analyzers/test_crash_analyzer.py
import zipfile
from pathlib import Path

from simanalysis.analyzers.crash_analyzer import CrashAnalyzer
from simanalysis.models import CrashReport, TracebackFrame


def _report(*frame_paths: str) -> CrashReport:
    return CrashReport(
        source_file="x.txt",
        report_type="desync",
        message="boom (ValueError)",
        frames=[TracebackFrame(raw_path=p) for p in frame_paths],
    )


def test_build_module_index_from_ts4script(tmp_path: Path):
    ts = tmp_path / "CoolMod.ts4script"
    with zipfile.ZipFile(ts, "w") as zf:
        zf.writestr("coolmod/sub/thing.py", "x = 1\n")
        zf.writestr("coolmod/__init__.py", "")
    index = CrashAnalyzer().build_module_index(tmp_path)
    assert index["coolmod/sub/thing.py"] == "CoolMod.ts4script"


def test_classify_frame_game_mod_unknown():
    a = CrashAnalyzer()
    index = {"coolmod/sub/thing.py": "CoolMod.ts4script"}
    game = TracebackFrame(raw_path=r"Core\sims4\utils.py")
    mod = TracebackFrame(raw_path=r"F:\proj\coolmod\sub\thing.py")
    unk = TracebackFrame(raw_path=r"C:\whatever\mystery.py")
    a.classify_frame(game, index)
    a.classify_frame(mod, index)
    a.classify_frame(unk, index)
    assert game.kind == "game"
    assert mod.kind == "mod" and mod.mod_name == "CoolMod.ts4script"
    assert unk.kind == "unknown"


def test_analyze_ranks_and_downweights_framework():
    index = {
        "injector/hook.py": "Injector.ts4script",
        "moda/a.py": "ModA.ts4script",
        "modb/b.py": "ModB.ts4script",
    }
    reports = [
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\moda\a.py"),
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\modb\b.py"),
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\moda\a.py"),
        _report(r"Core\sims4\utils.py"),  # base-game only
    ]
    result = CrashAnalyzer().analyze(reports, index)

    # Injector is in 3/3 attributable crashes -> down-weighted, never the culprit
    assert result.ranked_mods[0]["mod"] == "ModA.ts4script"
    assert result.ranked_mods[0]["top_suspect_count"] == 2
    assert "Injector.ts4script" not in [m["mod"] for m in result.ranked_mods]
    assert result.summary["base_game_only"] == 1
    assert result.summary["attributable"] == 3
    # the base-game-only crash has no suspects
    assert result.findings[-1].suspects == []
    # top suspect of crash 0 is ModA, high confidence (exact module-path match)
    assert result.findings[0].suspects[0].mod_name == "ModA.ts4script"
    assert result.findings[0].suspects[0].confidence == "high"
```
- [ ] **Step 2: Run — expect failure**
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov
```
- [ ] **Step 3: Implement**
```python
# src/simanalysis/analyzers/crash_analyzer.py
"""Attribute Sims 4 crashes to the most-likely culprit .ts4script and rank across a library."""
from __future__ import annotations

from pathlib import Path

from simanalysis.models import (
    CrashAnalysisResult,
    CrashFinding,
    CrashReport,
    Suspect,
    TracebackFrame,
)
from simanalysis.parsers.script import ScriptAnalyzer

# Base-game path roots (lowercased, '/'-separated) — never a mod.
GAME_PREFIXES = ("core/sims4", "core/", "server/", "gamedata", "widgets", "olympus", "sims4/")
# Mods that hook broadly and appear in most stacks; not the per-crash culprit.
CURATED_FRAMEWORKS = ("betterexceptions", "xmlinjector", "xml injector")
# A mod implicated in >= this fraction of attributable crashes is treated as a framework.
FRAMEWORK_CRASH_FRACTION = 0.5


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./").lstrip("/").lower()


class CrashAnalyzer:
    def __init__(self, framework_fraction: float = FRAMEWORK_CRASH_FRACTION) -> None:
        self.framework_fraction = framework_fraction

    def build_module_index(self, mods_dir: "str | Path") -> dict[str, str]:
        """Map each installed .ts4script's internal module path -> the .ts4script filename."""
        index: dict[str, str] = {}
        for ts4 in Path(mods_dir).rglob("*.ts4script"):
            try:
                for module_path in ScriptAnalyzer(ts4).module_paths:
                    index[_norm(module_path)] = ts4.name
            except Exception:
                continue  # corrupt/non-zip archive — skip
        return index

    def classify_frame(self, frame: TracebackFrame, index: dict[str, str]) -> None:
        norm = _norm(frame.raw_path)
        if any(norm.startswith(g) or f"/{g}" in norm for g in GAME_PREFIXES):
            frame.kind = "game"
            return
        if ".ts4script/" in norm:
            frame.kind = "mod"
            frame.module_path = norm
            frame.mod_name = norm.split(".ts4script/")[0].split("/")[-1] + ".ts4script"
            return
        best: "str | None" = None
        for key in index:
            if norm == key or norm.endswith("/" + key):
                if best is None or len(key) > len(best):
                    best = key
        if best is not None:
            frame.kind = "mod"
            frame.module_path = best
            frame.mod_name = index[best]
            return
        frame.kind = "unknown"

    def analyze(
        self, reports: list[CrashReport], index: dict[str, str]
    ) -> CrashAnalysisResult:
        for r in reports:
            for f in r.frames:
                self.classify_frame(f, index)

        total = len(reports) or 1
        mod_in_crash: dict[str, int] = {}
        attributable = 0
        for r in reports:
            mods = {f.mod_name for f in r.frames if f.kind == "mod" and f.mod_name}
            if mods:
                attributable += 1
            for m in mods:
                mod_in_crash[m] = mod_in_crash.get(m, 0) + 1

        frameworks: set[str] = set()
        for m, count in mod_in_crash.items():
            ml = m.lower()
            if any(cf in ml for cf in CURATED_FRAMEWORKS) or (count / total) >= self.framework_fraction:
                frameworks.add(m)

        findings: list[CrashFinding] = []
        top_counts: dict[str, int] = {}
        base_game_only = 0

        for r in reports:
            mod_frames = [f for f in r.frames if f.kind == "mod" and f.mod_name]
            if not mod_frames:
                base_game_only += 1
                findings.append(CrashFinding(report=r))
                continue
            ordered = list(reversed(mod_frames))  # most-recent-call-last => deepest first
            non_fw = [f for f in ordered if f.mod_name not in frameworks]
            picked = non_fw if non_fw else ordered

            suspects: list[Suspect] = []
            seen: set[str] = set()
            for i, f in enumerate(picked):
                if f.mod_name in seen:
                    continue
                seen.add(f.mod_name)
                if f.mod_name in frameworks:
                    conf = "low"
                elif i == 0 and f.module_path in index:
                    conf = "high"
                else:
                    conf = "medium"
                suspects.append(
                    Suspect(
                        mod_name=f.mod_name,
                        confidence=conf,
                        reason=f"implicated at: {f.raw_path}",
                        evidence=[f],
                    )
                )
            if suspects:
                top_counts[suspects[0].mod_name] = top_counts.get(suspects[0].mod_name, 0) + 1
            findings.append(CrashFinding(report=r, suspects=suspects))

        ranked = sorted(
            [
                {"mod": m, "top_suspect_count": top_counts[m], "crash_count": mod_in_crash.get(m, 0)}
                for m in top_counts
            ],
            key=lambda d: (d["top_suspect_count"], d["crash_count"]),
            reverse=True,
        )
        summary = {
            "reports": len(reports),
            "attributable": attributable,
            "base_game_only": base_game_only,
            "frameworks_downweighted": sorted(frameworks),
            "game_versions": sorted({r.game_version for r in reports if r.game_version}),
        }
        return CrashAnalysisResult(summary=summary, ranked_mods=ranked, findings=findings)
```
- [ ] **Step 4: Run — expect pass** (3 tests)
```bash
$PY/python -m pytest tests/unit/analyzers/test_crash_analyzer.py -q --no-cov
```
- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/analyzers/crash_analyzer.py tests/unit/analyzers/test_crash_analyzer.py
git commit -m "feat: CrashAnalyzer — module index, frame attribution, framework down-weighting, ranking" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Serialization

**Files:** Modify `src/simanalysis/serialization.py`; Modify `tests/unit/test_serialization.py`

- [ ] **Step 1: Write the failing test** (append):
```python
def test_crash_result_to_dict_shape():
    from simanalysis import serialization
    from simanalysis.models import (
        CrashAnalysisResult, CrashFinding, CrashReport, Suspect, TracebackFrame,
    )

    frame = TracebackFrame(raw_path="x/moda/a.py", line=7, func="run", kind="mod", mod_name="ModA.ts4script")
    report = CrashReport(source_file="l.txt", report_type="desync", message="boom (ValueError)",
                         frames=[frame], exception_class="ValueError")
    finding = CrashFinding(report=report,
                           suspects=[Suspect(mod_name="ModA.ts4script", confidence="high", reason="r", evidence=[frame])])
    result = CrashAnalysisResult(
        summary={"reports": 1}, ranked_mods=[{"mod": "ModA.ts4script", "top_suspect_count": 1, "crash_count": 1}],
        findings=[finding],
    )
    out = serialization.crash_result_to_dict(result)
    assert out["summary"] == {"reports": 1}
    assert out["ranked_mods"][0]["mod"] == "ModA.ts4script"
    f0 = out["findings"][0]
    assert f0["exception_class"] == "ValueError"
    assert f0["suspects"][0] == {"mod": "ModA.ts4script", "confidence": "high",
                                 "reason": "r", "evidence": ["x/moda/a.py"]}
```
- [ ] **Step 2: Run — expect failure**
```bash
$PY/python -m pytest tests/unit/test_serialization.py::test_crash_result_to_dict_shape -q --no-cov
```
- [ ] **Step 3: Implement** (append to `serialization.py`):
```python
def crash_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "summary": result.summary,
        "ranked_mods": result.ranked_mods,
        "parse_errors": result.parse_errors,
        "findings": [
            {
                "source_file": f.report.source_file,
                "report_type": f.report.report_type,
                "exception_class": f.report.exception_class,
                "message": f.report.message,
                "creator_tag": f.report.creator_tag,
                "created": f.report.created,
                "game_version": f.report.game_version,
                "be_advice": f.report.be_advice,
                "suspects": [
                    {
                        "mod": s.mod_name,
                        "confidence": s.confidence,
                        "reason": s.reason,
                        "evidence": [fr.raw_path for fr in s.evidence],
                    }
                    for s in f.suspects
                ],
            }
            for f in result.findings
        ],
    }
```
- [ ] **Step 4: Run — expect pass**, then full unit suite green.
```bash
$PY/python -m pytest tests/unit/test_serialization.py -q --no-cov && $PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
```
- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/serialization.py tests/unit/test_serialization.py
git commit -m "feat: serialize CrashAnalysisResult for desktop/json output" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `simanalysis crash` CLI command

**Files:** Modify `src/simanalysis/cli.py`; Modify `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test** (append; mirror the existing `CliRunner` style in the file):
```python
def test_crash_command_sweeps_and_ranks(tmp_path):
    import json
    import zipfile
    from click.testing import CliRunner
    from simanalysis.cli import cli

    sims4 = tmp_path
    mods = sims4 / "Mods"
    mods.mkdir()
    # one installed mod whose internal module the traceback will reference
    with zipfile.ZipFile(mods / "CoolMod.ts4script", "w") as zf:
        zf.writestr("coolmod/thing.py", "x = 1\n")

    (sims4 / "lastException_1.txt").write_text(
        "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
        "Traceback (most recent call last):&#13;&#10;"
        'File "Core\\sims4\\utils.py", line 1, in w&#13;&#10;'
        'File "F:\\p\\coolmod\\thing.py", line 7, in run&#13;&#10;'
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["ranked_mods"][0]["mod"] == "CoolMod.ts4script"
```
- [ ] **Step 2: Run — expect failure** (no `crash` command)
```bash
$PY/python -m pytest tests/unit/test_cli.py::test_crash_command_sweeps_and_ranks -q --no-cov
```
- [ ] **Step 3: Implement** — add to `cli.py` (after the existing commands; reuse its imports + add `import json`):
```python
@cli.command()
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--mods", type=click.Path(), default=None, help="Mods dir (default: <sims4_dir>/Mods)")
@click.option("--recursive", is_flag=True, help="Also scan subfolders for crash logs")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
@click.option("--limit", type=int, default=20, help="Top-N mods to show in txt summary")
def crash(
    sims4_dir: str,
    mods: Optional[str],
    recursive: bool,
    fmt: str,
    output: Optional[str],
    limit: int,
) -> None:
    """Autopsy lastException crash logs: rank the mods most likely behind your crashes."""
    import json
    from pathlib import Path

    from simanalysis import serialization
    from simanalysis.analyzers.crash_analyzer import CrashAnalyzer
    from simanalysis.parsers.exception_log import parse_exception_file

    base = Path(sims4_dir)
    mods_dir = Path(mods) if mods else base / "Mods"
    pattern = "**/lastException*.txt" if recursive else "lastException*.txt"
    log_files = sorted(base.glob(pattern))

    reports = []
    parse_errors = []
    seen = set()
    for lf in log_files:
        try:
            for rep in parse_exception_file(lf):
                if rep.signature in seen:
                    continue
                seen.add(rep.signature)
                reports.append(rep)
        except Exception as exc:  # noqa: BLE001 - never abort the sweep
            parse_errors.append(f"{lf.name}: {exc}")

    analyzer = CrashAnalyzer()
    index = analyzer.build_module_index(mods_dir) if mods_dir.exists() else {}
    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors

    if fmt == "json":
        text = json.dumps(serialization.crash_result_to_dict(result), indent=2)
    else:
        lines = [
            f"🔬 Crash Autopsy — {len(log_files)} log file(s), {result.summary['reports']} crash(es)",
            f"   attributable: {result.summary['attributable']}  |  base-game-only: {result.summary['base_game_only']}",
            "",
            f"Top suspect mods (of {len(result.ranked_mods)}):",
        ]
        for entry in result.ranked_mods[:limit]:
            lines.append(
                f"  • {entry['mod']}  — top suspect in {entry['top_suspect_count']} crash(es)"
                f", seen in {entry['crash_count']}"
            )
        if not result.ranked_mods:
            lines.append("  (no mod-attributable crashes found)")
        text = "\n".join(lines)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Wrote report to {output}")
    else:
        click.echo(text)
```
- [ ] **Step 4: Run — expect pass**, then full unit suite + ruff + mypy green.
```bash
$PY/python -m pytest tests/unit/test_cli.py::test_crash_command_sweeps_and_ranks -q --no-cov
$PY/python -m pytest tests/unit -q --no-cov 2>&1 | tail -1
$PY/ruff check . && $PY/ruff format . && $PY/python -m mypy src/simanalysis 2>&1 | tail -1
```
Expected: pass; ruff clean; mypy `Success`. (If `--format`/`json` import or `Optional` lint nits appear, fix per ruff's guidance; new modules already use `from __future__ import annotations`.)
- [ ] **Step 5: Commit**
```bash
git add src/simanalysis/cli.py tests/unit/test_cli.py
git commit -m "feat: add 'simanalysis crash' command (whole-library crash autopsy)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Real-log ground-truth validation (manual — not a committed test)

**Files:** none (verification).

- [ ] **Step 1: Run the autopsy over the real 146 logs**
```bash
cd ~/src/Simanalysis-crash
$PY/python -m pip install -e . --quiet  # ensure the `simanalysis` entrypoint reflects this branch
$PY/bin/simanalysis crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --recursive | head -40
```
Expected: a ranked list of suspect mods; **base-game-only** crashes counted separately. (Use `--format json -o /tmp/autopsy.json` for detail.)
- [ ] **Step 2: Sanity-check attribution** — confirm the top suspects line up with the user's hand-triaged quarantine folders (`_Quarantine_*`, `_Logs_*`), and that injectors (Better Exceptions, NisaK) are NOT the top culprits (statistical down-weighting working). This is the ground-truth check, analogous to the 200-package DBPF verification. Record the result; if attribution is off, that's a finding to iterate on (tune `FRAMEWORK_CRASH_FRACTION`, prefixes, or matching) before merge.

---

## Self-review notes (completed)
- **Spec coverage:** parser (Task 3) ↔ spec "exception_log"; module index + attribution + framework down-weight + ranking (Task 4) ↔ spec attribution algorithm; models (Task 2); serialization (Task 5); CLI incl. `--recursive` (Task 6); manual 146-log validation (Task 7) ↔ spec testing. Out-of-scope items (desktop view, UI/desync, actions, BE-HTML) intentionally absent.
- **Placeholders:** none; every step has complete code + exact commands.
- **Type/name consistency:** `parse_exception_file`, `CrashAnalyzer.build_module_index/classify_frame/analyze`, `crash_result_to_dict`, and the model field names (`mod_name`, `module_path`, `report_type`, `signature`, `ranked_mods`, `top_suspect_count`) are consistent across tasks and tests. New modules use `from __future__ import annotations`; models use `Optional[...]`/`list[...]` to stay 3.9-safe.
- **CI note:** Task 6 runs ruff + mypy; the desktop Rust CI job is unaffected (pure-Python change). CI runs on the `feat/crash-autopsy` PR against `main`.
