# UI Crash Autopsy — design

**Status:** Design approved and self-reviewed; awaiting user review before implementation planning
**Date:** 2026-05-30
**Roadmap:** Fast-follow to Crash Autopsy (#1) in the "ultimate Sims doctor" roadmap. It covers the UI/desync failures that `lastException*.txt` script-crash attribution deliberately left out.

## Goal

Scan `lastUIException*.txt` logs, explain UI/desync failures in plain terms, and resolve resource-like keys against active and quarantined Sims 4 packages so the report can say whether the referenced resource is active, already disabled/quarantined, or missing from disk.

This cycle is CLI-first and evidence-only. It does not move files, quarantine packages, auto-toggle mods, launch the game, or build the desktop view.

## Why now

Crash Autopsy v1 + status-aware attribution is shipped, and the current real Sims logs no longer point at an active script-crash culprit. The high-signal remaining failure is UI-side:

- 5 root `lastUIException*.txt` files contain 27 repeated reports.
- All reports have category `(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory`.
- All reports say `Failed to locate category info for interaction category with key: 15023068382072182982`.
- The key is `0xD07CA9190DD098C6`.
- A DBPF index-only check found no active `Mods` owner for that key.
- The same key exists in `_Quarantine_UI_Breakage_20260525/.../adeepindigo_base_generalpiemenus_v3-2.package`.

That means the useful feature is not a parser-only log reader. It needs DBPF resource-key attribution so the report can explain the missing/quarantined adeepindigo pie-menu resource instead of repeating an opaque numeric key.

## Scope

**In:**

- Parse `lastUIException*.txt` root logs by default.
- Extract UI/desync report metadata: source file, report type, created time, game version, category ID, first error message, UI stack lines, session ID/desync ID, `Modded` flag, resource-like decimal keys, and a stable signature.
- Dedupe repeated reports across files by message/key/category/stack signature and keep an occurrence count plus source files.
- Build a DBPF package resource index from:
  - `<sims4_dir>/Mods` as `active`.
  - sibling or nested `_Disabled*` / `_Quarantine*` directories as `disabled`.
- Match extracted keys against package resource instances.
- Preserve active precedence when the same key appears active and disabled.
- Output TXT and JSON reports with status groups: `active`, `disabled`, `not_found`, and `no_key`.
- Add unit tests, CLI tests, serialization tests, and manual validation against the real Sims folder.

**Out:**

- File moves, quarantine commands, auto-bisect, or treatment actions.
- Live monitoring / filesystem watching.
- Desktop React view or Tauri bridge command.
- Deep Better Exceptions HTML parsing beyond the XML-style `lastUIException*.txt` reports.
- Full resource extraction; the analyzer reads DBPF indexes only.

## Components

```text
src/simanalysis/
  parsers/ui_exception_log.py      NEW  tolerant parser for lastUIException*.txt
  analyzers/ui_crash_analyzer.py   NEW  DBPF resource-key attribution + grouping
  models.py                        EDIT add UI report/finding/resource models
  serialization.py                 EDIT add ui_result_to_dict
  cli.py                           EDIT add `ui-crash` command

tests/unit/parsers/test_ui_exception_log.py     NEW
tests/unit/analyzers/test_ui_crash_analyzer.py  NEW
tests/unit/test_serialization.py                EDIT
tests/unit/test_cli.py                          EDIT
```

The feature reuses `DBPFReader.read_index()` instead of the full `ModScanner` path because UI attribution only needs package resource keys. This keeps the scan bounded and avoids extracting resource payloads.

## Data models

Add small UI-specific models beside the existing Crash Autopsy models:

```python
@dataclass
class UIStackFrame:
    raw: str
    namespace: str | None = None
    function: str | None = None

@dataclass
class UIExceptionReport:
    source_file: str
    report_type: str
    message: str
    category_id: str | None = None
    keys: list[int] = field(default_factory=list)
    stack: list[UIStackFrame] = field(default_factory=list)
    created: str | None = None
    game_version: str | None = None
    session_id: str | None = None
    desync_id: str | None = None
    modded: bool | None = None
    signature: str = ""
    occurrences: int = 1
    source_files: list[str] = field(default_factory=list)

@dataclass
class UIResourceHit:
    key: int
    package_name: str
    package_path: str
    resource_type: int
    resource_group: int
    status: str  # "active" | "disabled"

@dataclass
class UIFinding:
    report: UIExceptionReport
    status: str  # "active" | "disabled" | "not_found" | "no_key"
    keys: list[int] = field(default_factory=list)
    hits: list[UIResourceHit] = field(default_factory=list)
    reason: str = ""

@dataclass
class UIAnalysisResult:
    summary: dict = field(default_factory=dict)
    findings: list[UIFinding] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    index_errors: list[str] = field(default_factory=list)
```

Status vocabulary intentionally differs only where DBPF resources differ from script suspects:

- `active`: key is present in at least one active package.
- `disabled`: key is found only in `_Disabled*` / `_Quarantine*` package copies.
- `not_found`: key was extracted from the UI log but no indexed package contains it.
- `no_key`: the UI report parsed, but it did not contain a resource-like decimal key.

## Parser

`parse_ui_exception_file(path)` should be tolerant like `parse_exception_file`:

- Read with `encoding="utf-8", errors="replace"`.
- Extract `<report>...</report>` blocks with regex rather than strict XML parsing.
- Decode HTML entities so `&#13;&#10;` becomes normal line breaks.
- Extract tags with the same helper pattern used by `exception_log.py`.
- Parse the first non-empty desync line as `message`.
- Extract `categoryid`, `createtime`, `buildsignature`, `sessionid`, and `desyncid`.
- Extract `Modded: True` / `Modded: False` from `desyncdata` when present.
- Extract stack lines beginning with `at ...`.
- Extract decimal keys using patterns that cover the current real format:
  - `key: 15023068382072182982`
  - future-safe variants such as `key 15023068382072182982` or `resource 15023068382072182982`.
- Create a signature from category, message, keys, and stack lines using `hashlib.sha1(..., usedforsecurity=False)`.

The parser should never raise on one malformed report. Bad files can be caught by the CLI and surfaced as parse errors.

## Analyzer

`UICrashAnalyzer` builds a package resource index:

```text
resource instance int
  -> list[UIResourceHit]
```

Scanning rules:

- Scan active `<sims4_dir>/Mods/**/*.package`.
- Auto-discover `_Disabled*` / `_Quarantine*` directories at any depth under `<sims4_dir>`.
- Exclude `_CacheBackup*` and `_Recovered*` folders because they are copies/noise, not intentional status roots.
- Read only DBPF indexes with `DBPFReader.read_index()`.
- Corrupt packages are skipped and recorded in `index_errors`.
- If the same key is found active and disabled, the finding status is `active`.

Finding classification:

- Any report with no extracted keys becomes `no_key`.
- Any report with one or more active hits becomes `active`.
- Any report with no active hits but at least one disabled hit becomes `disabled`.
- Any report with keys and no hits becomes `not_found`.

The current real-log expectation is a `disabled` finding for key `0xD07CA9190DD098C6`, with hits pointing at `adeepindigo_base_generalpiemenus_v3-2.package`.

## CLI

Add:

```text
simanalysis ui-crash <sims4_dir> [--mods DIR] [--recursive] [--format txt|json] [--output FILE] [--limit N]
```

Defaults:

- `--mods` defaults to `<sims4_dir>/Mods`.
- Non-recursive scans only root `lastUIException*.txt`.
- `--recursive` scans archived/log folders too.
- `--limit` limits per-status TXT sections.

TXT report shape:

```text
UI Crash Autopsy - 5 log file(s), 1 unique UI finding(s), 27 occurrence(s)
   active: 0 | disabled: 1 | not-found: 0 | no-key: 0

[DISABLED] referenced resources found only in disabled/quarantined packages:
  - 0xD07CA9190DD098C6 (15023068382072182982)
    message: Failed to locate category info for interaction category with key: ...
    category: (AS)gamedata.Gameplay.InteractionMenu::InteractionCategory
    occurrences: 27
    found in: adeepindigo_base_generalpiemenus_v3-2.package
```

JSON report uses `serialization.ui_result_to_dict(...)` and includes every model field needed for a later desktop view.

## Error handling and guarantees

- Malformed/truncated logs never abort the sweep.
- Corrupt packages never abort the sweep.
- Missing `Mods` folder still allows log parsing; every keyed report becomes `not_found`.
- Empty UI log set returns a clear zero-report summary.
- Duplicate reports are collapsed but occurrence counts and source files remain visible.
- The report should not claim the game is fixed or a mod is proven broken. It should say what the evidence shows: active owner, disabled-only owner, no owner, or no key.

## Testing

**Parser tests:**

- Parse the current interaction-menu format with `key: 15023068382072182982`.
- Decode `&#13;&#10;` entities.
- Extract category, game version, session/desync IDs, stack frames, and `Modded: True`.
- Handle repeated reports and generate stable signatures.
- Handle a UI report without any key.

**Analyzer tests:**

- Active package hit.
- Disabled-only package hit.
- Active beats disabled when the same key appears in both.
- Key not found.
- No-key report.
- Corrupt package is counted in `index_errors` and does not abort.

**CLI / serialization tests:**

- TXT report groups findings by status and includes decimal + hex keys.
- JSON includes `summary`, `findings`, `parse_errors`, and `index_errors`.
- `--recursive` changes log discovery but not default behavior.

**Manual real-log validation:**

Run against:

```text
/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4
```

Expected:

- Root UI logs collapse from 27 repeated reports to one unique finding.
- Key `15023068382072182982` / `0xD07CA9190DD098C6` is reported.
- Status is `disabled`.
- At least one hit names `adeepindigo_base_generalpiemenus_v3-2.package` under `_Quarantine_UI_Breakage_20260525`.

## Follow-ups

- Add a desktop "Crash Doctor" view that combines script crashes and UI crashes.
- Feed UI findings into Treatment + Auto-Bisect so a future command can prove or reverse a suspected package move safely.
- Add Live Monitoring after static UI Autopsy exists, so new UI logs can be interpreted automatically instead of merely detected.
