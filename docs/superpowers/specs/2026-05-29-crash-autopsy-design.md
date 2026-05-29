# Crash Autopsy v1 — design

**Status:** Design approved (brainstorming), pending spec review
**Date:** 2026-05-29
**Roadmap:** Sub-project #1 of the "ultimate Sims doctor" vision. Wedge chosen for highest pain × lowest risk (no network, no mod-identity, fully verifiable headlessly).

## Goal

Sweep every `lastException*.txt` crash log in a Sims 4 user folder, attribute each crash to the most-likely culprit `.ts4script` mod, and produce a **whole-library ranked report** of the most-implicated / likely-broken mods, with **per-crash drill-down** (suspects + evidence + the traceback frames). CLI + report only.

## Scope

**In v1:** script exceptions (`lastException*.txt`), whole-library sweep + aggregate ranking + per-crash detail, CLI command, txt/JSON report, structured output ready for a later desktop view.

**Out of v1 (each a later cycle):** desktop "Crash Doctor" UI; UI exceptions / desyncs (`lastUIException*.txt`); recommended actions / auto-quarantine (Treatment sub-project #3); deep parsing of Better Exceptions' HTML report (v1 uses only the inline `<Advice>`/`categoryid` hints).

## Grounding: the real log format (from 146 real logs on the dev machine)

`lastException*.txt` are **XML**, typically Better-Exceptions-enriched:

```xml
<?xml version="1.0" ?><root>
<BetterExceptions><BEversion>v3.16</BEversion><Advice>This is likely due to bad tuning…</Advice></BetterExceptions>
<report><type>desync</type><createtime>2026-05-25 21:17:18</createtime>
  <buildsignature>Local.…1.124.55.1230…</buildsignature>
  <categoryid>injector.py:26</categoryid>
  <desyncdata>[cjiang] Error occurred within the tag named 'final_product' (value: U) (UnavailablePackSafeResourceError)&#13;&#10;Traceback (most recent call last):&#13;&#10;
  File "Core\sims4\utils.py", line 179, in wrapper&#13;&#10;
  File "F:\Projects\Sims 4 Modding\Mods\TMEX Mods\Tmex-BetterExceptions\PublicUnlock.py", line 13, in _unlock&#13;&#10;
  File "E:\…\NisaK\utilities\nisa_injector.py", line 25 …
  </desyncdata></report>
</root>
```

Key realities that shape the design:
1. **One file may contain multiple `<report>` blocks**, often duplicates of the same crash (saw 3 identical). Dedupe by `desyncid`/message+stack hash.
2. **Frame paths are the *creator's* build machine**, not the user's disk: `F:\Projects\…\Tmex-BetterExceptions\PublicUnlock.py`, `E:\…\NisaK\…\nisa_injector.py`, `\Users\Kseniia\…\ksuinjector.py`, `.\WickedWhims_v185i\wickedwhims\main\…\tuning_class_injection.py`, `/Delimaci_TeenParamedicCareer.ts4script/…py`, `Mods/simrealist_snb/interactions.py`, `Core\sims4\utils.py`. We must match on the **package-relative module path** (the path *suffix*), not the absolute path.
3. **Every stack passes through several mods**, and *injectors/frameworks* (Better Exceptions, XML Injector, NisaK, …) hook broadly, so they appear in nearly every traceback — naive "blame any mod in the stack" would wrongly accuse them.
4. Entities are encoded (`&#13;&#10;` = CRLF). Files can be large (~600 KB) and not strictly well-formed.

## Components

```
src/simanalysis/
  parsers/exception_log.py     NEW  tolerant parser: file -> list[CrashReport]
  analyzers/crash_analyzer.py  NEW  CrashAnalyzer: attribute + rank + aggregate
  models.py                    EDIT add CrashReport/TracebackFrame/Suspect/CrashAnalysisResult
  serialization.py             EDIT add crash_result_to_dict (desktop-ready output)
  cli.py                       EDIT add `crash` command
tests/unit/parsers/test_exception_log.py     NEW
tests/unit/analyzers/test_crash_analyzer.py  NEW
tests/unit/test_cli.py                        EDIT (crash command)
```

Reuses `scanners/mod_scanner.py` + the script parser to enumerate installed `.ts4script`s and their internal module paths. New analyzer sits alongside `ModAnalyzer`/`SaveAnalyzer`/`TrayAnalyzer`/`MeshAnalyzer`.

### `parsers/exception_log.py`
- Tolerant extraction (regex/streaming over `<report>…</report>` blocks; do **not** assume strict XML — Sims logs are often malformed/truncated).
- Per report, extract: `report_type` (desync/etc.), exception class (e.g. `UnavailablePackSafeResourceError` from the trailing `(…Error)`), the human message + leading `[creator]` tag, the decoded `Traceback` → ordered `TracebackFrame`s, `createtime`, `buildsignature` (game version), and BE hints (`<Advice>`, `<categoryid>`) when present.
- Decode entities (`&#13;&#10;` → newline). Skip blocks with no `Traceback` (those are pure UI/desyncs → counted, not analyzed in v1).
- Returns `list[CrashReport]`; never raises on a single bad block (collect + count parse failures).

### `analyzers/crash_analyzer.py`
1. **Module index** — from the installed mods (`ModScanner`), build `{normalized internal module path → Mod}` for every `.py` inside each `.ts4script` (using the zip namelist / script parser). *Note for the plan:* confirm the script parser exposes full internal module paths (e.g. `wickedwhims/main/…/x.py`); if it only exposes leaf filenames, extend it.
2. **Frame classification** — normalize separators (`\`→`/`), lower-case; classify each frame:
   - **game**: prefix in `{core/sims4, server/, gamedata, widgets, olympus, sims4/…}` → ignore.
   - **mod**: the frame path *ends with* a known internal module path (longest-suffix match wins) → attribute to that `.ts4script`. (Also catch explicit `…/<name>.ts4script/…` segments.)
   - **unknown**: a `.py` matching no installed mod and not base-game → record as "referenced but not installed / renamed."
3. **Framework down-weighting** — two signals: a small curated allow-list (Better Exceptions, XML Injector, …) **and** a self-calibrating statistical rule: a mod implicated in a large share of *all* crashes (starting threshold ≥ 50%, to be tuned against the 146 real logs) is treated as a hook framework and down-weighted as a per-crash culprit. Down-weighted ≠ excluded — such a mod can still be the top suspect if it's the *only* non-game frame.
4. **Per-crash culprit** — rank `mod` frames by depth (closest to the error = strongest), excluding game and down-weighting frameworks; corroborate with BE `<Advice>`/`categoryid` and the `[creator]` tag. Produce a ranked `Suspect` list with confidence:
   - **high**: exact internal-module-path suffix match + deepest non-framework frame.
   - **medium**: leaf-filename-only match, or framework-adjacent.
   - **low / none**: only base-game frames → flag **"not your mods — likely a base-game bug."**
5. **Aggregate** — across all crashes, rank mods by how often they're the *top* suspect in a distinct crash (weighted by confidence + recency). Output the ranked "most-implicated / likely-broken" list + a summary (total logs, crashes, attributable %, top suspects, base-game-only count). Surface BE's broken-mods advice when available.

### Data models (`models.py`)
```python
@dataclass
class TracebackFrame:
    raw_path: str
    module_path: str | None   # normalized package-relative tail, if extracted
    line: int | None
    func: str | None
    kind: str                 # "game" | "mod" | "unknown"
    mod_name: str | None      # set when kind == "mod"

@dataclass
class CrashReport:
    source_file: str
    report_type: str          # "desync", etc.
    exception_class: str | None
    message: str
    creator_tag: str | None   # e.g. "cjiang"
    frames: list[TracebackFrame]
    created: str | None
    game_version: str | None
    be_advice: str | None

@dataclass
class Suspect:
    mod_name: str
    confidence: str           # "high" | "medium" | "low"
    reason: str
    evidence: list[TracebackFrame]

@dataclass
class CrashFinding:            # one analyzed crash
    report: CrashReport
    suspects: list[Suspect]    # ranked; empty => base-game / unattributable

@dataclass
class CrashAnalysisResult:
    summary: dict              # totals, attributable %, base-game-only count, game_version(s)
    ranked_mods: list[dict]    # aggregate: {mod, crash_count, top_suspect_count, confidence}
    findings: list[CrashFinding]
    parse_errors: list[str]
```

## CLI

`simanalysis crash <sims4_dir> [--mods DIR] [--recursive] [--format txt|json] [--output FILE] [--limit N]`
- Default `--mods` = `<sims4_dir>/Mods`. Discovers `lastException*.txt` directly under `<sims4_dir>` by default; `--recursive` also scans subfolders (e.g. quarantine/log dirs).
- txt: a ranked summary ("Top suspects across 146 logs") + per-crash detail; json: `crash_result_to_dict(...)`.

## Data flow
sims4 dir → discover `lastException*.txt` → `exception_log` parser → `CrashReport`s (deduped) → `CrashAnalyzer` (module index from `ModScanner` + classify + rank + aggregate) → `CrashAnalysisResult` → txt/JSON report.

## Error handling / edges
- Malformed/truncated log or `<report>` block → skip + record in `parse_errors` (sweep never aborts).
- No/empty Mods dir → still parse; attribution falls back to raw module/package names as suspects (lower confidence).
- Reports with no `Traceback` (pure UI/desync) → skipped + counted (v1 scope).
- Frames matching no installed mod → "unknown module (not installed / renamed)" — a useful signal (missing dependency).
- Large files → bounded/streamed read; cap frames per report.
- Duplicate reports within/across files → deduped by `desyncid` or `(exception_class, message, frame-signature)` hash.

## Testing
- **Parser unit tests:** synthetic BE-enriched and vanilla `<report>` samples — entity decoding, multiple + duplicate reports, missing-traceback (skipped), malformed/truncated (no raise), creator-tag + exception-class extraction.
- **Attribution unit tests:** given a synthetic module index + crafted tracebacks — longest-suffix module match; base-game frames → unattributable; the **statistical framework down-weighting** (a mod in most crashes isn't the culprit); confidence tiers; aggregate ranking.
- **CLI test:** runs over a temp dir of synthetic logs → expected ranked output + exit code.
- **Real-log validation (manual, not committed):** run `simanalysis crash "<the dev Sims 4 folder>"` over the 146 real logs and sanity-check that the ranked culprits match the user's hand-triaged suspects — the ground-truth check (mirrors the 200-package DBPF verification).

## Fast-follows (next cycles, not v1)
Desktop "Crash Doctor" view (bridge command + React screen); UI/desync attribution via resource-instance keys (now possible post-DBPF-fix); recommended actions + auto-quarantine (Treatment #3); deep Better-Exceptions HTML report parsing; the AI "Derrick" plain-language layer over findings.
