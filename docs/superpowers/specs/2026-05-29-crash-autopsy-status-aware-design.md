# Crash Autopsy — status-aware attribution (fast-follow) — design

**Status:** Design approved (brainstorming), pending spec review
**Date:** 2026-05-29
**Roadmap:** Completes sub-project #1 (Crash Autopsy). Builds on v1 (`simanalysis crash`, merged in PR #8).

## Goal
Surface crash culprits that are **not currently active** in `Mods/` — instead of silently bucketing them as "unknown" / base-game. Every named suspect gets a **status** so the user sees what to act on vs what's already handled.

## Why (grounding from the v1 real-log validation)
On 156 real crashes, a mod's deepest traceback frame often points to a `.ts4script` that isn't under `Mods/` right now, so v1 classified it "unknown" and dropped it. Concretely, **adeepindigo appeared in 135 crash frames but was never named** because the user had moved it into a `_Disabled_*` folder. Two cases:
- **Disabled/quarantined:** the `.ts4script` still exists, just under a deliberate `_Disabled_*` / `_Quarantine_*` folder (sibling of `Mods/`, or under `Mods/`).
- **Not installed:** no `.ts4script` anywhere on disk; only the crash log's path remains.

## Scope
**In:** a per-suspect `status` (`active` | `disabled` | `not_installed`); auto-scanning the user's `_Disabled_*`/`_Quarantine_*` folders so disabled culprits are named precisely; best-effort culprit naming from the frame path when nothing matches on disk; a status-grouped report (txt) + `status` in JSON.

**Out (later):** UI/desync (`lastUIException`) attribution; the desktop "Crash Doctor" view; treatment/auto-quarantine (#3); scanning `_CacheBackup_*`/`_Recovered_*` (cache copies → duplicates/noise — deliberately excluded).

## Design

### 1. Status-aware module index
`CrashAnalyzer.build_module_index` scans, by default:
- `<sims4>/Mods/` → status `active`.
- sibling dirs matching `_Disabled*` / `_Quarantine*` (case-insensitive), e.g. `<sims4>/_Disabled_adeepindigo_*`, `<sims4>/_Quarantine_*` → status `disabled`.
- Any matched mod whose own path contains a `_disabled`/`_quarantine` segment (e.g. `Mods/_Quarantine_*/…`) is `disabled` regardless of which root found it.

The index keeps the v1 shape — `dict[normalized_module_path → ts4script_filename]` (still `.pyc`→`.py` normalized) — **plus** a parallel `dict[ts4script_filename → status]`. **Precedence:** if the same module path is found both active and disabled, `active` wins (it's installed now). These are returned together (exact container shape decided in the plan; the v1 `(index)` callers and tests are updated accordingly).

Cost note: only the small `.ts4script` zip namelists are read (not `.package` CC), so widening the scan stays fast even with many `_*` folders.

### 2. Frame classification + best-effort naming
- `TracebackFrame` gains `mod_status: Optional[str]`, set alongside `mod_name` when a frame matches the index (active or disabled).
- When the deepest non-game frame matches **no** indexed module and isn't base-game, derive a **best-effort culprit name** from the normalized path: prefer the segment just before the leaf (the package dir), else the leaf filename; fix the v1 prototype's `cosasimstra.py/cosasimstra.py` doubling (don't repeat the leaf). Mark `mod_status = "not_installed"`. Such a frame becomes a real (low-confidence) suspect instead of being ignored.

### 3. Analyzer + suspects
- `Suspect` gains `status: str` (`active` | `disabled` | `not_installed`), propagated from the implicating frame.
- Per-crash culprit selection now considers disabled-mod frames and (as a last resort) best-effort not-installed frames, not just active-mod frames. The existing deepest-non-framework selection and framework down-weighting are unchanged and apply across all statuses.
- Aggregate `ranked_mods` entries gain `status`. `summary` gains counts per status (e.g. `active_culprits`, `disabled_culprits`, `not_installed_culprits`); the misleading "base_game_only" now means genuinely game-only (frames all base-game), since not-installed frames are no longer swept into it.

### 4. CLI / report
- Auto-scan disabled/quarantine folders **by default** (no flag). (A future `--mods-only` could narrow it; not required now.)
- txt report **groups suspects by status**, actionable first:
  - `🔴 Active mods still implicated` (what to fix) — e.g. `delimaci_teenparamediccareer`.
  - `🟡 Already disabled / quarantined` (likely handled) — e.g. `adeepindigo_*`.
  - `⚪ Referenced but not installed` (best-guess names).
- JSON: each suspect/ranked entry includes `status`; `summary` includes the per-status counts.

## Data flow
sims4 dir → discover `lastException*.txt` → parse → build status-aware index (Mods + `_Disabled*`/`_Quarantine*`) → classify frames (active/disabled mod, best-effort not-installed, game) → per-crash culprit + aggregate with status → status-grouped txt / JSON.

## Error handling / edges
- Missing/zero disabled folders → behaves like v1 (active-only), no error.
- Same mod active and disabled → `active` wins.
- Best-effort name must never be a bare game path or empty; if no usable token, leave the crash unattributed (counted, not mislabeled).
- All existing v1 guarantees hold: never raise on a bad log; corrupt archives skipped; sweep never aborts.

## Testing
- **Index/status:** a mod under `Mods/` → active; the same-named module under a sibling `_Disabled_*` → disabled; active-beats-disabled precedence; a `Mods/_Quarantine_*` mod → disabled.
- **Classification:** disabled-mod frame → `mod` + `status=disabled`; an unmatched non-game deepest frame → best-effort name + `status=not_installed` (and no `x.py/x.py` doubling).
- **Analyzer:** a crash whose only culprit is a disabled mod is named (not dropped); status propagates to `Suspect` and `ranked_mods`; per-status summary counts; framework down-weighting still applies.
- **CLI:** txt groups by status (active section present, disabled section present); JSON carries `status`.
- **Real-log re-validation (manual):** re-run over the dev machine's logs; confirm `adeepindigo_*` now surfaces as a **disabled** culprit and `delimaci` remains the top **active** culprit.
