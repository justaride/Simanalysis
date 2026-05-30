# UI Crash Autopsy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI-first UI Crash Autopsy that parses `lastUIException*.txt`, extracts UI resource keys, resolves them against active and disabled/quarantined `.package` DBPF indexes, and reports active/disabled/not-found/no-key findings.

**Architecture:** Mirror the shipped Crash Autopsy shape: parser -> analyzer -> models -> serialization -> CLI. The parser handles UI/desync XML-style logs; the analyzer reads only DBPF indexes from `.package` files and classifies each unique UI finding by resource-key ownership. No file moves, desktop UI, live monitoring, or auto-bisect actions are included.

**Tech Stack:** Python 3.9+, stdlib `re`/`html`/`hashlib`/`pathlib`, existing `click` CLI, existing `DBPFReader`, pytest, ruff, mypy, bandit.

---

## Design Of Record

Spec: `docs/superpowers/specs/2026-05-30-ui-crash-autopsy-design.md`

Branch: `feat/ui-crash-autopsy`

Important repo facts:

- Work in `/Users/gabrielfreeman/src/Simanalysis`, not the bare mirror at `/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4/Simanalysis.git`.
- Reuse `.venv`.
- Run bandit before pushing because CI has a security job.
- The real Sims folder for manual validation is `/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4`.

## File Structure

- Create `src/simanalysis/parsers/ui_exception_log.py`
  - Tolerant `<report>` parser for `lastUIException*.txt`.
  - Returns `UIExceptionReport` objects without indexing packages.
- Create `src/simanalysis/analyzers/ui_crash_analyzer.py`
  - Discovers package roots.
  - Builds `resource_instance -> UIResourceHit[]`.
  - Dedupe/collapse reports and classify findings.
- Modify `src/simanalysis/models.py`
  - Add `UIStackFrame`, `UIExceptionReport`, `UIResourceHit`, `UIFinding`, `UIAnalysisResult`.
- Modify `src/simanalysis/serialization.py`
  - Add `ui_result_to_dict`.
- Modify `src/simanalysis/cli.py`
  - Add `simanalysis ui-crash`.
- Create `tests/unit/parsers/test_ui_exception_log.py`
- Create `tests/unit/analyzers/test_ui_crash_analyzer.py`
- Modify `tests/unit/test_serialization.py`
- Modify `tests/unit/test_cli.py`
- Create `docs/superpowers/2026-05-30-ui-crash-autopsy-validation.md` after real-log validation.

## Task 1: UI Models

**Files:**
- Modify: `src/simanalysis/models.py`
- Test: `tests/unit/test_models.py`

- [x] **Step 1: Write the failing model test**

Append this test to `tests/unit/test_models.py`:

```python
def test_ui_crash_models_defaults() -> None:
    from simanalysis.models import (
        UIAnalysisResult,
        UIExceptionReport,
        UIFinding,
        UIResourceHit,
        UIStackFrame,
    )

    stack = UIStackFrame(
        raw="gamedata.Gameplay.InteractionMenu::InteractionCategory/Create()",
        namespace="gamedata.Gameplay.InteractionMenu::InteractionCategory",
        function="Create",
    )
    report = UIExceptionReport(
        source_file="lastUIException.txt",
        report_type="desync",
        message="Error: Failed to locate category info for interaction category with key: 15023068382072182982",
        category_id="(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory",
        keys=[15023068382072182982],
        stack=[stack],
        modded=True,
        signature="sig",
    )
    hit = UIResourceHit(
        key=15023068382072182982,
        package_name="adeepindigo_base_generalpiemenus_v3-2.package",
        package_path="/Sims/_Quarantine_UI/adeepindigo_base_generalpiemenus_v3-2.package",
        resource_type=0x03E9D964,
        resource_group=0,
        status="disabled",
    )
    finding = UIFinding(report=report, status="disabled", keys=report.keys, hits=[hit])
    result = UIAnalysisResult(summary={"unique_findings": 1}, findings=[finding])

    assert report.occurrences == 1
    assert report.source_files == []
    assert finding.hits[0].status == "disabled"
    assert result.parse_errors == []
    assert result.index_errors == []
```

- [x] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_models.py::test_ui_crash_models_defaults -q
```

Expected: FAIL with an import error for `UIAnalysisResult` or another new UI model.

- [x] **Step 3: Add UI model dataclasses**

Insert these dataclasses in `src/simanalysis/models.py` immediately after `CrashAnalysisResult`:

```python
@dataclass
class UIStackFrame:
    """One frame from an ActionScript/UI desync stack."""

    raw: str
    namespace: Optional[str] = None
    function: Optional[str] = None


@dataclass
class UIExceptionReport:
    """A single parsed UI exception/desync report."""

    source_file: str
    report_type: str
    message: str
    category_id: Optional[str] = None
    keys: list[int] = field(default_factory=list)
    stack: list[UIStackFrame] = field(default_factory=list)
    created: Optional[str] = None
    game_version: Optional[str] = None
    session_id: Optional[str] = None
    desync_id: Optional[str] = None
    modded: Optional[bool] = None
    signature: str = ""
    occurrences: int = 1
    source_files: list[str] = field(default_factory=list)


@dataclass
class UIResourceHit:
    """A DBPF package resource whose instance matches a UI exception key."""

    key: int
    package_name: str
    package_path: str
    resource_type: int
    resource_group: int
    status: str


@dataclass
class UIFinding:
    """One deduped UI exception finding and its resource-key matches."""

    report: UIExceptionReport
    status: str
    keys: list[int] = field(default_factory=list)
    hits: list[UIResourceHit] = field(default_factory=list)
    reason: str = ""


@dataclass
class UIAnalysisResult:
    """Whole-folder UI exception analysis output."""

    summary: dict = field(default_factory=dict)
    findings: list[UIFinding] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    index_errors: list[str] = field(default_factory=list)
```

- [x] **Step 4: Run the model test**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_models.py::test_ui_crash_models_defaults -q
```

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add src/simanalysis/models.py tests/unit/test_models.py
git commit -m "feat: add UI crash analysis models"
```

## Task 2: UI Exception Parser

**Files:**
- Create: `src/simanalysis/parsers/ui_exception_log.py`
- Test: `tests/unit/parsers/test_ui_exception_log.py`

- [x] **Step 1: Write parser tests**

Create `tests/unit/parsers/test_ui_exception_log.py`:

```python
from pathlib import Path

from simanalysis.parsers.ui_exception_log import parse_ui_exception_file


UI_XML = (
    '<?xml version="1.0" ?><root>'
    "<report><version>2</version><sessionid>abc123</sessionid><type>desync</type>"
    "<createtime>2026-05-29 12:32:36</createtime>"
    "<buildsignature>Local.Unknown.Unknown.1.124.63.1220-1.300.000.241.Release</buildsignature>"
    "<categoryid>(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory</categoryid>"
    "<desyncid>abc123</desyncid>"
    "<desyncdata>Error: Failed to locate category info for interaction category with key: 15023068382072182982&#13;&#10;"
    "&#9;at gamedata.Gameplay.InteractionMenu::InteractionCategory/Create()&#13;&#10;"
    "&#9;at widgets.Gameplay.PieMenu::PieMenuMain/HandlePieMenuCreate()&#13;&#10;"
    "Modded: True&#13;&#10;"
    "</desyncdata></report>"
    "<report><type>desync</type><categoryid>widgets.NoKey</categoryid>"
    "<desyncdata>Error: UI failed without a resource key&#13;&#10;"
    "&#9;at widgets.GameTray.controls::HUDCheatSheet/InitializeCheatSheetItemList()&#13;&#10;"
    "Modded: False&#13;&#10;"
    "</desyncdata></report>"
    "</root>"
)


def test_parse_ui_exception_file_extracts_key_stack_and_metadata(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_1.txt"
    log.write_text(UI_XML, encoding="utf-8")

    reports = parse_ui_exception_file(log)

    assert len(reports) == 2
    r0 = reports[0]
    assert r0.source_file == str(log)
    assert r0.report_type == "desync"
    assert r0.created == "2026-05-29 12:32:36"
    assert r0.game_version == "Local.Unknown.Unknown.1.124.63.1220-1.300.000.241.Release"
    assert r0.category_id == "(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory"
    assert r0.session_id == "abc123"
    assert r0.desync_id == "abc123"
    assert r0.modded is True
    assert r0.keys == [15023068382072182982]
    assert "Failed to locate category info" in r0.message
    assert len(r0.stack) == 2
    assert r0.stack[0].namespace == "gamedata.Gameplay.InteractionMenu::InteractionCategory"
    assert r0.stack[0].function == "Create"
    assert r0.signature
    assert r0.source_files == [str(log)]


def test_parse_ui_exception_file_allows_no_key_reports(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_1.txt"
    log.write_text(UI_XML, encoding="utf-8")

    reports = parse_ui_exception_file(log)

    r1 = reports[1]
    assert r1.keys == []
    assert r1.category_id == "widgets.NoKey"
    assert r1.modded is False
    assert r1.stack[0].function == "InitializeCheatSheetItemList"


def test_parse_ui_exception_file_malformed_returns_empty(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_bad.txt"
    log.write_text("<root><report><desyncdata>Error", encoding="utf-8")

    assert parse_ui_exception_file(log) == []
```

- [x] **Step 2: Run parser tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/parsers/test_ui_exception_log.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simanalysis.parsers.ui_exception_log'`.

- [x] **Step 3: Implement parser**

Create `src/simanalysis/parsers/ui_exception_log.py`:

```python
"""Tolerant parser for Sims 4 lastUIException*.txt UI/desync logs."""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from simanalysis.models import UIExceptionReport, UIStackFrame

_REPORT_RE = re.compile(r"<report>(.*?)</report>", re.DOTALL)
_STACK_RE = re.compile(r"^\s*at\s+(.+?)\s*$", re.IGNORECASE)
_KEY_RE = re.compile(r"\b(?:key|resource)\s*:?\s*(\d{10,20})\b", re.IGNORECASE)
_MODDED_RE = re.compile(r"\bModded:\s*(True|False)\b", re.IGNORECASE)


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def _parse_stack_line(line: str) -> UIStackFrame | None:
    m = _STACK_RE.match(line)
    if not m:
        return None
    raw = m.group(1).strip()
    namespace = raw
    function: str | None = None
    if "/" in raw:
        namespace, function_part = raw.rsplit("/", 1)
        function = function_part.removesuffix("()")
    return UIStackFrame(raw=raw, namespace=namespace or None, function=function or None)


def _extract_modded(data: str) -> bool | None:
    m = _MODDED_RE.search(data)
    if not m:
        return None
    return m.group(1).lower() == "true"


def _signature(category_id: str | None, message: str, keys: list[int], stack: list[UIStackFrame]) -> str:
    stack_sig = "|".join(frame.raw for frame in stack)
    payload = f"{category_id or ''}|{message}|{','.join(str(k) for k in keys)}|{stack_sig}"
    return hashlib.sha1(
        payload.encode("utf-8", "replace"),
        usedforsecurity=False,
    ).hexdigest()


def parse_ui_exception_file(path: str | Path) -> list[UIExceptionReport]:
    """Parse one lastUIException*.txt into UIExceptionReport objects."""
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")

    reports: list[UIExceptionReport] = []
    for block in _REPORT_RE.findall(text):
        data = _tag(block, "desyncdata") or ""
        lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
        message = lines[0] if lines else ""
        stack = [frame for line in lines if (frame := _parse_stack_line(line)) is not None]
        keys = list(dict.fromkeys(int(m) for m in _KEY_RE.findall(data)))
        category_id = _tag(block, "categoryid")

        report = UIExceptionReport(
            source_file=str(source),
            report_type=_tag(block, "type") or "unknown",
            message=message,
            category_id=category_id,
            keys=keys,
            stack=stack,
            created=_tag(block, "createtime"),
            game_version=_tag(block, "buildsignature"),
            session_id=_tag(block, "sessionid"),
            desync_id=_tag(block, "desyncid"),
            modded=_extract_modded(data),
            source_files=[str(source)],
        )
        report.signature = _signature(category_id, message, keys, stack)
        reports.append(report)

    return reports
```

- [x] **Step 4: Run parser tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/parsers/test_ui_exception_log.py -q
```

Expected: PASS.

- [x] **Step 5: Run lint/type checks for new parser**

Run:

```bash
.venv/bin/python -m ruff check src/simanalysis/parsers/ui_exception_log.py tests/unit/parsers/test_ui_exception_log.py
.venv/bin/python -m mypy src/simanalysis/parsers/ui_exception_log.py
```

Expected: both commands pass.

- [x] **Step 6: Commit**

Run:

```bash
git add src/simanalysis/parsers/ui_exception_log.py tests/unit/parsers/test_ui_exception_log.py
git commit -m "feat: parse Sims UI exception logs"
```

## Task 3: UI Crash Analyzer

**Files:**
- Create: `src/simanalysis/analyzers/ui_crash_analyzer.py`
- Test: `tests/unit/analyzers/test_ui_crash_analyzer.py`

- [x] **Step 1: Write analyzer tests**

Create `tests/unit/analyzers/test_ui_crash_analyzer.py`:

```python
import struct
from pathlib import Path

from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer
from simanalysis.models import UIExceptionReport


TARGET_KEY = 15023068382072182982


def _write_dbpf_package(path: Path, key: int, resource_type: int = 0x03E9D964) -> None:
    payload = b"resource"
    index = bytearray()
    index += struct.pack("<I", 0)  # mnIndexType: no constants
    index += struct.pack("<I", resource_type)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", key >> 32)
    index += struct.pack("<I", key & 0xFFFFFFFF)
    index += struct.pack("<I", 96 + 4 + 32)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)

    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", len(index))
    header[64:68] = struct.pack("<I", 96)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(index)
        f.write(payload)


def _report(key: int | None = TARGET_KEY, signature: str = "sig") -> UIExceptionReport:
    message = "Error: Failed to locate category info"
    if key is not None:
        message += f" for interaction category with key: {key}"
    return UIExceptionReport(
        source_file="lastUIException.txt",
        report_type="desync",
        message=message,
        category_id="(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory",
        keys=[] if key is None else [key],
        signature=signature,
        source_files=["lastUIException.txt"],
    )


def test_build_resource_index_records_active_hit(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    pkg = mods / "Active.package"
    _write_dbpf_package(pkg, TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)

    hit = index[TARGET_KEY][0]
    assert hit.package_name == "Active.package"
    assert hit.status == "active"
    assert hit.resource_type == 0x03E9D964
    assert analyzer.index_errors == []


def test_disabled_only_hit_classifies_disabled(tmp_path: Path) -> None:
    (tmp_path / "Mods").mkdir()
    disabled = tmp_path / "_Quarantine_UI"
    _write_dbpf_package(disabled / "adeepindigo_base_generalpiemenus_v3-2.package", TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(tmp_path / "Mods", extra_roots=[disabled])
    result = analyzer.analyze([_report()], index)

    finding = result.findings[0]
    assert finding.status == "disabled"
    assert finding.hits[0].package_name == "adeepindigo_base_generalpiemenus_v3-2.package"
    assert result.summary["disabled_findings"] == 1


def test_active_beats_disabled_for_same_key(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    disabled = tmp_path / "_Disabled_Old"
    _write_dbpf_package(mods / "Active.package", TARGET_KEY)
    _write_dbpf_package(disabled / "Old.package", TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods, extra_roots=[disabled])
    result = analyzer.analyze([_report()], index)

    assert result.findings[0].status == "active"
    assert result.summary["active_findings"] == 1


def test_not_found_and_no_key_statuses(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)
    result = analyzer.analyze([_report(1234567890123, "missing"), _report(None, "nokey")], index)

    assert [f.status for f in result.findings] == ["not_found", "no_key"]
    assert result.summary["not_found_findings"] == 1
    assert result.summary["no_key_findings"] == 1


def test_duplicate_reports_are_collapsed(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    _write_dbpf_package(mods / "Active.package", TARGET_KEY)
    reports = [_report(signature="same"), _report(signature="same"), _report(signature="same")]

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)
    result = analyzer.analyze(reports, index)

    assert len(result.findings) == 1
    assert result.findings[0].report.occurrences == 3
    assert result.summary["occurrences"] == 3


def test_corrupt_package_is_recorded_not_raised(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()
    (mods / "Bad.package").write_text("not dbpf", encoding="utf-8")

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)

    assert index == {}
    assert len(analyzer.index_errors) == 1
    assert "Bad.package" in analyzer.index_errors[0]
```

- [x] **Step 2: Run analyzer tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/analyzers/test_ui_crash_analyzer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simanalysis.analyzers.ui_crash_analyzer'`.

- [x] **Step 3: Implement analyzer**

Create `src/simanalysis/analyzers/ui_crash_analyzer.py`:

```python
"""Analyze Sims 4 UI exception reports by resolving resource keys to packages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from simanalysis.analyzers.crash_analyzer import STATUS_ACTIVE, STATUS_DISABLED, _is_disabled_name
from simanalysis.exceptions import DBPFError
from simanalysis.models import (
    UIAnalysisResult,
    UIExceptionReport,
    UIFinding,
    UIResourceHit,
)
from simanalysis.parsers.dbpf import DBPFReader

STATUS_NOT_FOUND = "not_found"
STATUS_NO_KEY = "no_key"
_EXCLUDED_COPY_PREFIXES = ("_cachebackup", "_recovered")


def _is_excluded_copy_path(path: Path) -> bool:
    return any(part.lower().startswith(_EXCLUDED_COPY_PREFIXES) for part in path.parts)


def _status_for_package(path: Path) -> str:
    return STATUS_DISABLED if any(_is_disabled_name(part) for part in path.parts) else STATUS_ACTIVE


def discover_disabled_roots(base: str | Path) -> list[Path]:
    """Find intentional disabled/quarantine folders under a Sims 4 directory."""
    root = Path(base)
    if not root.exists():
        return []
    return sorted(
        d
        for d in root.glob("**/_*")
        if d.is_dir() and _is_disabled_name(d.name) and not _is_excluded_copy_path(d)
    )


def _read_package_hits(path: Path) -> tuple[list[UIResourceHit], str | None]:
    try:
        resources = DBPFReader(path).read_index()
    except (DBPFError, OSError, ValueError) as exc:
        return [], f"{path}: {exc}"

    status = _status_for_package(path)
    hits = [
        UIResourceHit(
            key=resource.instance,
            package_name=path.name,
            package_path=str(path),
            resource_type=resource.type,
            resource_group=resource.group,
            status=status,
        )
        for resource in resources
    ]
    return hits, None


class UICrashAnalyzer:
    """Resolve UI exception resource keys against active and disabled packages."""

    def __init__(self) -> None:
        self.index_errors: list[str] = []

    def build_resource_index(
        self, mods_dir: str | Path, extra_roots: Iterable[str | Path] = ()
    ) -> dict[int, list[UIResourceHit]]:
        self.index_errors = []
        index: dict[int, list[UIResourceHit]] = {}
        seen: set[Path] = set()

        roots = [Path(mods_dir), *(Path(root) for root in extra_roots)]
        for root in roots:
            if not root.exists() or _is_excluded_copy_path(root):
                continue
            for package in sorted(root.rglob("*.package")):
                resolved = package.resolve()
                if resolved in seen or _is_excluded_copy_path(package):
                    continue
                seen.add(resolved)
                hits, error = _read_package_hits(package)
                if error:
                    self.index_errors.append(error)
                    continue
                for hit in hits:
                    index.setdefault(hit.key, []).append(hit)

        return index

    def analyze(
        self, reports: list[UIExceptionReport], index: dict[int, list[UIResourceHit]]
    ) -> UIAnalysisResult:
        collapsed = self._collapse_reports(reports)
        findings = [self._finding_for(report, index) for report in collapsed]
        summary = self._summary(findings)
        return UIAnalysisResult(
            summary=summary,
            findings=findings,
            index_errors=self.index_errors,
        )

    def _collapse_reports(self, reports: list[UIExceptionReport]) -> list[UIExceptionReport]:
        by_signature: dict[str, UIExceptionReport] = {}
        for report in reports:
            signature = report.signature or f"{report.category_id}|{report.message}|{report.keys}"
            if signature not in by_signature:
                if not report.source_files:
                    report.source_files = [report.source_file]
                by_signature[signature] = report
                continue
            existing = by_signature[signature]
            existing.occurrences += report.occurrences
            for source in report.source_files or [report.source_file]:
                if source not in existing.source_files:
                    existing.source_files.append(source)
        return list(by_signature.values())

    def _finding_for(
        self, report: UIExceptionReport, index: dict[int, list[UIResourceHit]]
    ) -> UIFinding:
        if not report.keys:
            return UIFinding(
                report=report,
                status=STATUS_NO_KEY,
                keys=[],
                reason="UI report contains no resource-like key",
            )

        hits: list[UIResourceHit] = []
        for key in report.keys:
            hits.extend(index.get(key, []))

        if not hits:
            return UIFinding(
                report=report,
                status=STATUS_NOT_FOUND,
                keys=report.keys,
                reason="No indexed active or disabled package contains the referenced key",
            )

        status = STATUS_ACTIVE if any(hit.status == STATUS_ACTIVE for hit in hits) else STATUS_DISABLED
        reason = (
            "Referenced key is present in active Mods"
            if status == STATUS_ACTIVE
            else "Referenced key is found only in disabled/quarantined packages"
        )
        return UIFinding(report=report, status=status, keys=report.keys, hits=hits, reason=reason)

    def _summary(self, findings: list[UIFinding]) -> dict[str, int]:
        occurrences = sum(f.report.occurrences for f in findings)
        return {
            "unique_findings": len(findings),
            "occurrences": occurrences,
            "active_findings": sum(1 for f in findings if f.status == STATUS_ACTIVE),
            "disabled_findings": sum(1 for f in findings if f.status == STATUS_DISABLED),
            "not_found_findings": sum(1 for f in findings if f.status == STATUS_NOT_FOUND),
            "no_key_findings": sum(1 for f in findings if f.status == STATUS_NO_KEY),
        }
```

- [x] **Step 4: Run analyzer tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/analyzers/test_ui_crash_analyzer.py -q
```

Expected: PASS.

- [x] **Step 5: Run targeted lint/type checks**

Run:

```bash
.venv/bin/python -m ruff check src/simanalysis/analyzers/ui_crash_analyzer.py tests/unit/analyzers/test_ui_crash_analyzer.py
.venv/bin/python -m mypy src/simanalysis/analyzers/ui_crash_analyzer.py
```

Expected: both commands pass.

- [x] **Step 6: Commit**

Run:

```bash
git add src/simanalysis/analyzers/ui_crash_analyzer.py tests/unit/analyzers/test_ui_crash_analyzer.py
git commit -m "feat: resolve UI exception keys to package resources"
```

## Task 4: Serialization

**Files:**
- Modify: `src/simanalysis/serialization.py`
- Modify: `tests/unit/test_serialization.py`

- [ ] **Step 1: Write serialization test**

Append this test to `tests/unit/test_serialization.py`:

```python
def test_ui_result_to_dict_shape():
    from simanalysis import serialization
    from simanalysis.models import (
        UIAnalysisResult,
        UIExceptionReport,
        UIFinding,
        UIResourceHit,
        UIStackFrame,
    )

    report = UIExceptionReport(
        source_file="lastUIException.txt",
        report_type="desync",
        message="Error: Failed to locate category info for interaction category with key: 15023068382072182982",
        category_id="(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory",
        keys=[15023068382072182982],
        stack=[UIStackFrame(raw="widgets.Gameplay.PieMenu::PieMenuMain/HandlePieMenuCreate()")],
        created="2026-05-29 12:32:36",
        game_version="Local.1.124.63.1220",
        session_id="session",
        desync_id="desync",
        modded=True,
        signature="sig",
        occurrences=27,
        source_files=["lastUIException.txt"],
    )
    hit = UIResourceHit(
        key=15023068382072182982,
        package_name="adeepindigo_base_generalpiemenus_v3-2.package",
        package_path="/Sims/_Quarantine_UI/adeepindigo_base_generalpiemenus_v3-2.package",
        resource_type=0x03E9D964,
        resource_group=0,
        status="disabled",
    )
    result = UIAnalysisResult(
        summary={"unique_findings": 1, "occurrences": 27},
        findings=[UIFinding(report=report, status="disabled", keys=report.keys, hits=[hit])],
        parse_errors=["bad log"],
        index_errors=["bad package"],
    )

    out = serialization.ui_result_to_dict(result)

    assert out["summary"] == {"unique_findings": 1, "occurrences": 27}
    assert out["parse_errors"] == ["bad log"]
    assert out["index_errors"] == ["bad package"]
    f0 = out["findings"][0]
    assert f0["status"] == "disabled"
    assert f0["keys"][0] == {"decimal": 15023068382072182982, "hex": "0xD07CA9190DD098C6"}
    assert f0["report"]["occurrences"] == 27
    assert f0["hits"][0]["package_name"] == "adeepindigo_base_generalpiemenus_v3-2.package"
    assert f0["hits"][0]["resource_type_hex"] == "0x03E9D964"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_serialization.py::test_ui_result_to_dict_shape -q
```

Expected: FAIL with `AttributeError: module 'simanalysis.serialization' has no attribute 'ui_result_to_dict'`.

- [ ] **Step 3: Implement `ui_result_to_dict`**

Append this function to `src/simanalysis/serialization.py`:

```python
def _ui_key_to_dict(key: int) -> dict[str, Any]:
    return {"decimal": key, "hex": f"0x{key:016X}"}


def ui_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "summary": result.summary,
        "parse_errors": result.parse_errors,
        "index_errors": result.index_errors,
        "findings": [
            {
                "status": finding.status,
                "reason": finding.reason,
                "keys": [_ui_key_to_dict(key) for key in finding.keys],
                "report": {
                    "source_file": finding.report.source_file,
                    "source_files": finding.report.source_files,
                    "report_type": finding.report.report_type,
                    "message": finding.report.message,
                    "category_id": finding.report.category_id,
                    "created": finding.report.created,
                    "game_version": finding.report.game_version,
                    "session_id": finding.report.session_id,
                    "desync_id": finding.report.desync_id,
                    "modded": finding.report.modded,
                    "occurrences": finding.report.occurrences,
                    "signature": finding.report.signature,
                    "stack": [
                        {
                            "raw": frame.raw,
                            "namespace": frame.namespace,
                            "function": frame.function,
                        }
                        for frame in finding.report.stack
                    ],
                },
                "hits": [
                    {
                        "key": _ui_key_to_dict(hit.key),
                        "package_name": hit.package_name,
                        "package_path": hit.package_path,
                        "resource_type": hit.resource_type,
                        "resource_type_hex": f"0x{hit.resource_type:08X}",
                        "resource_group": hit.resource_group,
                        "resource_group_hex": f"0x{hit.resource_group:08X}",
                        "status": hit.status,
                    }
                    for hit in finding.hits
                ],
            }
            for finding in result.findings
        ],
    }
```

- [ ] **Step 4: Run serialization tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_serialization.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint/type checks**

Run:

```bash
.venv/bin/python -m ruff check src/simanalysis/serialization.py tests/unit/test_serialization.py
.venv/bin/python -m mypy src/simanalysis/serialization.py
```

Expected: both commands pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/simanalysis/serialization.py tests/unit/test_serialization.py
git commit -m "feat: serialize UI crash analysis results"
```

## Task 5: CLI Command

**Files:**
- Modify: `src/simanalysis/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Append these tests to `tests/unit/test_cli.py`:

```python
def test_ui_crash_command_json_reports_disabled_resource(tmp_path):
    import json
    import struct

    from click.testing import CliRunner

    from simanalysis.cli import cli

    target_key = 15023068382072182982
    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    disabled = sims4 / "_Quarantine_UI"
    disabled.mkdir()

    payload = b"resource"
    index = bytearray()
    index += struct.pack("<I", 0)
    index += struct.pack("<I", 0x03E9D964)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", target_key >> 32)
    index += struct.pack("<I", target_key & 0xFFFFFFFF)
    index += struct.pack("<I", 96 + 4 + 32)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)
    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", len(index))
    header[64:68] = struct.pack("<I", 96)
    with open(disabled / "adeepindigo_base_generalpiemenus_v3-2.package", "wb") as f:
        f.write(header)
        f.write(index)
        f.write(payload)

    (sims4 / "lastUIException_1.txt").write_text(
        "<root><report><type>desync</type>"
        "<categoryid>(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory</categoryid>"
        "<desyncdata>Error: Failed to locate category info for interaction category with key: "
        f"{target_key}&#13;&#10;"
        "at gamedata.Gameplay.InteractionMenu::InteractionCategory/Create()&#13;&#10;"
        "Modded: True&#13;&#10;"
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["ui-crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["summary"]["disabled_findings"] == 1
    finding = data["findings"][0]
    assert finding["status"] == "disabled"
    assert finding["keys"][0]["hex"] == "0xD07CA9190DD098C6"
    assert finding["hits"][0]["package_name"] == "adeepindigo_base_generalpiemenus_v3-2.package"


def test_ui_crash_command_txt_groups_status_and_limit(tmp_path):
    from click.testing import CliRunner

    from simanalysis.cli import cli

    (tmp_path / "Mods").mkdir()
    for i in range(2):
        key = 1234567890123 + i
        (tmp_path / f"lastUIException_{i}.txt").write_text(
            "<root><report><type>desync</type><categoryid>cat</categoryid>"
            f"<desyncdata>Error: missing key: {key}&#13;&#10;</desyncdata></report></root>",
            encoding="utf-8",
        )

    result = CliRunner().invoke(cli, ["ui-crash", str(tmp_path), "--limit", "1"])
    assert result.exit_code == 0, result.output
    assert "UI Crash Autopsy" in result.output
    assert "[NOT FOUND]" in result.output
    assert result.output.count("message: Error: missing key") == 1
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py::test_ui_crash_command_json_reports_disabled_resource tests/unit/test_cli.py::test_ui_crash_command_txt_groups_status_and_limit -q
```

Expected: FAIL because `ui-crash` is not registered.

- [ ] **Step 3: Add CLI formatter helpers**

First change the typing import near the top of `src/simanalysis/cli.py`:

```python
from typing import Any, Optional
```

Then insert these helpers immediately before the existing `crash` command:

```python
def _format_ui_key(key: int) -> str:
    return f"0x{key:016X} ({key})"


def _ui_findings_for_status(result: Any, status: str) -> list[Any]:
    return [finding for finding in result.findings if finding.status == status]


def _format_ui_txt(log_count: int, result: Any, limit: int = 20) -> str:
    s = result.summary
    lines = [
        f"UI Crash Autopsy - {log_count} log file(s), "
        f"{s['unique_findings']} unique UI finding(s), {s['occurrences']} occurrence(s)",
        f"   active: {s['active_findings']} | disabled: {s['disabled_findings']} "
        f"| not-found: {s['not_found_findings']} | no-key: {s['no_key_findings']}",
        "",
    ]
    sections = [
        ("active", "[ACTIVE] referenced resources are present in active Mods"),
        ("disabled", "[DISABLED] referenced resources found only in disabled/quarantined packages"),
        ("not_found", "[NOT FOUND] referenced resources were not found in indexed packages"),
        ("no_key", "[NO KEY] UI reports without a resource-like key"),
    ]
    any_shown = False
    for status, header in sections:
        findings = _ui_findings_for_status(result, status)
        if not findings:
            continue
        any_shown = True
        lines.append(f"{header}:")
        for finding in findings[:limit]:
            key_text = ", ".join(_format_ui_key(key) for key in finding.keys) or "no key"
            lines.append(f"  - {key_text}")
            lines.append(f"    message: {finding.report.message}")
            if finding.report.category_id:
                lines.append(f"    category: {finding.report.category_id}")
            lines.append(f"    occurrences: {finding.report.occurrences}")
            if finding.hits:
                packages = sorted({hit.package_name for hit in finding.hits})
                lines.append(f"    found in: {', '.join(packages[:5])}")
                if len(packages) > 5:
                    lines.append(f"    additional packages: {len(packages) - 5}")
        hidden = len(findings) - limit
        if hidden > 0:
            lines.append(f"    ... {hidden} more finding(s) hidden by --limit")
        lines.append("")
    if not any_shown:
        lines.append("  (no UI exception reports found)")
    if result.parse_errors:
        lines.append(f"Parse errors: {len(result.parse_errors)}")
    if result.index_errors:
        lines.append(f"Package index errors: {len(result.index_errors)}")
    return "\n".join(lines).rstrip()
```

- [ ] **Step 4: Add `ui-crash` command**

Insert this command in `src/simanalysis/cli.py` immediately before the existing `crash` command:

```python
@cli.command("ui-crash")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--mods", type=click.Path(file_okay=False), default=None, help="Mods dir")
@click.option("--recursive", is_flag=True, help="Scan subfolders for lastUIException logs")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
@click.option("--limit", type=int, default=20, help="Findings to show per status group (txt)")
def ui_crash(
    sims4_dir: str,
    mods: Optional[str],
    recursive: bool,
    fmt: str,
    output: Optional[str],
    limit: int,
) -> None:
    """Autopsy lastUIException logs: explain UI/desync resource-key failures."""
    import json

    from simanalysis import serialization
    from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
    from simanalysis.parsers.ui_exception_log import parse_ui_exception_file

    base = Path(sims4_dir)
    mods_dir = Path(mods) if mods else base / "Mods"
    pattern = "**/lastUIException*.txt" if recursive else "lastUIException*.txt"
    log_files = sorted(base.glob(pattern))

    reports = []
    parse_errors = []
    for log_file in log_files:
        try:
            reports.extend(parse_ui_exception_file(log_file))
        except Exception as exc:
            parse_errors.append(f"{log_file.name}: {exc}")

    analyzer = UICrashAnalyzer()
    extra_roots = discover_disabled_roots(base)
    index = analyzer.build_resource_index(mods_dir, extra_roots=extra_roots)
    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors

    if fmt == "json":
        text = json.dumps(serialization.ui_result_to_dict(result), indent=2)
    else:
        text = _format_ui_txt(len(log_files), result, limit=limit)

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Wrote report to {output}")
    else:
        click.echo(text)
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py::test_ui_crash_command_json_reports_disabled_resource tests/unit/test_cli.py::test_ui_crash_command_txt_groups_status_and_limit -q
```

Expected: PASS.

- [ ] **Step 6: Run full targeted UI test set**

Run:

```bash
.venv/bin/python -m pytest tests/unit/parsers/test_ui_exception_log.py tests/unit/analyzers/test_ui_crash_analyzer.py tests/unit/test_serialization.py::test_ui_result_to_dict_shape tests/unit/test_cli.py::test_ui_crash_command_json_reports_disabled_resource tests/unit/test_cli.py::test_ui_crash_command_txt_groups_status_and_limit -q
```

Expected: PASS.

- [ ] **Step 7: Run lint/type checks for touched Python**

Run:

```bash
.venv/bin/python -m ruff check src/simanalysis/cli.py tests/unit/test_cli.py
.venv/bin/python -m mypy src/simanalysis/cli.py
```

Expected: both commands pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add src/simanalysis/cli.py tests/unit/test_cli.py
git commit -m "feat: add ui-crash CLI report"
```

## Task 6: Real Sims Log Validation

**Files:**
- Create: `docs/superpowers/2026-05-30-ui-crash-autopsy-validation.md`

- [ ] **Step 1: Run UI Crash Autopsy on the real Sims folder**

Run:

```bash
.venv/bin/python -m simanalysis.cli ui-crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --format json --output /tmp/simanalysis-ui-crash-real.json
.venv/bin/python -m simanalysis.cli ui-crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --limit 10
```

Expected:

- JSON command writes `/tmp/simanalysis-ui-crash-real.json`.
- TXT command prints `UI Crash Autopsy`.
- Summary includes one disabled finding for the current root logs.
- Output includes `0xD07CA9190DD098C6`.
- Output includes `adeepindigo_base_generalpiemenus_v3-2.package`.

- [ ] **Step 2: Verify JSON with a small Python assertion**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/simanalysis-ui-crash-real.json")
data = json.loads(path.read_text(encoding="utf-8"))
assert data["summary"]["disabled_findings"] >= 1, data["summary"]
matches = [
    finding
    for finding in data["findings"]
    if any(key["hex"] == "0xD07CA9190DD098C6" for key in finding["keys"])
]
assert matches, "expected current interaction-menu key"
assert matches[0]["status"] == "disabled", matches[0]
packages = {hit["package_name"] for hit in matches[0]["hits"]}
assert "adeepindigo_base_generalpiemenus_v3-2.package" in packages, packages
print(data["summary"])
print(matches[0]["status"])
print(sorted(packages))
PY
```

Expected: prints the JSON summary, `disabled`, and a package list including `adeepindigo_base_generalpiemenus_v3-2.package`.

- [ ] **Step 3: Write validation note**

Create `docs/superpowers/2026-05-30-ui-crash-autopsy-validation.md`:

```markdown
# UI Crash Autopsy Validation (2026-05-30)

Command:

```bash
.venv/bin/python -m simanalysis.cli ui-crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --format json --output /tmp/simanalysis-ui-crash-real.json
```

Result:

- Root `lastUIException*.txt` logs parsed successfully.
- Repeated interaction-menu reports collapsed by signature.
- Key `15023068382072182982` / `0xD07CA9190DD098C6` was detected.
- The finding classified as `disabled`.
- The matching disabled/quarantined package included `adeepindigo_base_generalpiemenus_v3-2.package`.

Interpretation:

The current UI exception points at a pie-menu category resource that is not active in `Mods` but is present in a quarantined adeepindigo package. This is evidence for a missing/disabled resource relationship, not proof that any file should be moved automatically. Treatment and auto-bisect remain out of scope for this cycle.
```

If the real output differs because logs changed after the spec was written, update only the bullet values that are directly observed from the command output. Keep the interpretation evidence-only.

- [ ] **Step 4: Commit validation note**

Run:

```bash
git add docs/superpowers/2026-05-30-ui-crash-autopsy-validation.md
git commit -m "docs: record UI crash autopsy real-log validation"
```

## Task 7: Full Verification, Security Gate, Push, PR, Auto-Merge

**Files:**
- No source files created unless verification reveals a defect.

- [ ] **Step 1: Run focused UI tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/parsers/test_ui_exception_log.py tests/unit/analyzers/test_ui_crash_analyzer.py tests/unit/test_serialization.py::test_ui_result_to_dict_shape tests/unit/test_cli.py::test_ui_crash_command_json_reports_disabled_resource tests/unit/test_cli.py::test_ui_crash_command_txt_groups_status_and_limit -q
```

Expected: PASS.

- [ ] **Step 2: Run full Python unit/integration suite**

Run:

```bash
.venv/bin/python -m pytest
```

Expected: PASS. If a DBPF performance benchmark fails on a micro-timing threshold while the functional tests pass, rerun the failed benchmark once before changing code:

```bash
.venv/bin/python -m pytest tests/performance/test_dbpf_benchmarks.py --last-failed -q
```

- [ ] **Step 3: Run lint, format check, type check**

Run:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src/simanalysis
```

Expected: all pass.

- [ ] **Step 4: Run local security gate**

Run:

```bash
.venv/bin/python -m bandit -r src/simanalysis -c pyproject.toml
```

Expected: `No issues identified.`

- [ ] **Step 5: Run desktop CI-equivalent smoke gates if dependencies are available**

Run:

```bash
npm --prefix web run build
export PATH="$(brew --prefix)/bin:$PATH"
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings
cargo test --manifest-path src-tauri/Cargo.toml
```

Expected: all pass. If local Rust or Node dependencies are unavailable, record the exact blocker in the PR body and rely on CI for that platform gate.

- [ ] **Step 6: Push branch**

Run:

```bash
git status --short --branch
git push -u github feat/ui-crash-autopsy
```

Expected: branch pushes to GitHub.

- [ ] **Step 7: Open PR**

Run:

```bash
gh pr create \
  --base main \
  --head feat/ui-crash-autopsy \
  --title "feat: add UI Crash Autopsy" \
  --body-file /tmp/ui-crash-autopsy-pr.md
```

Before running the command, create `/tmp/ui-crash-autopsy-pr.md` with:

```markdown
## Summary

- add `simanalysis ui-crash` for `lastUIException*.txt` UI/desync reports
- resolve UI resource keys against active and disabled/quarantined `.package` DBPF indexes
- serialize TXT/JSON output and validate against the real adeepindigo interaction-menu log case

## Validation

- `.venv/bin/python -m pytest`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m ruff format --check .`
- `.venv/bin/python -m mypy src/simanalysis`
- `.venv/bin/python -m bandit -r src/simanalysis -c pyproject.toml`
- real-log validation documented in `docs/superpowers/2026-05-30-ui-crash-autopsy-validation.md`
```

- [ ] **Step 8: Enable auto-merge once CI is green**

Run:

```bash
gh pr checks --watch
gh pr merge --auto --squash --delete-branch
```

Expected: auto-merge is enabled and the branch is deleted after all required checks pass. If CI shows a flaky DBPF performance benchmark failure only, rerun the failed job once with:

```bash
gh run rerun <run-id> --failed
```

- [ ] **Step 9: Sync local main after merge**

Run after the PR merges:

```bash
git switch main
git pull --ff-only github main
git status --short --branch
```

Expected: local `main` is up to date and clean.

## Self-Review Checklist

- Spec coverage:
  - Parser, metadata extraction, key extraction, signatures: Task 2.
  - DBPF resource indexing, active/disabled/not-found/no-key classification: Task 3.
  - TXT/JSON report and CLI options: Tasks 4 and 5.
  - Real-log validation against the adeepindigo interaction-menu case: Task 6.
  - Full gates, bandit, PR, auto-merge: Task 7.
- Scope check:
  - No file moves.
  - No quarantine command.
  - No live monitoring.
  - No desktop UI or Tauri bridge change.
- Type consistency:
  - Models use `UIExceptionReport`, `UIResourceHit`, `UIFinding`, `UIAnalysisResult`.
  - Serialization exports `ui_result_to_dict`.
  - CLI command name is `ui-crash`.
