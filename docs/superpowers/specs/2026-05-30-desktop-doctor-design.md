# Desktop Doctor Integration - design

**Status:** Design approved and ready for implementation
**Date:** 2026-05-30
**Roadmap:** First desktop slice after Crash Autopsy v1, status-aware Crash Autopsy, and UI Crash Autopsy. This moves the shipped CLI-only diagnosis into the app without adding treatment or file mutation.

## Goal

Add a read-only desktop "Doctor" view that runs both existing autopsies from one Sims 4 folder scan:

- script crash autopsy from `lastException*.txt`
- UI/freeze autopsy from `lastUIException*.txt`

The result should tell the user what still needs attention, what is already disabled or quarantined, and what could not be resolved. It must not move files, quarantine packages, restore mods, launch The Sims 4, or auto-bisect.

## Scope

**In:**

- Add a desktop bridge command that composes existing crash and UI analyzers.
- Add Tauri routing for one new analysis kind.
- Add a React Doctor route with one folder picker and one scan button.
- Group findings by practical status:
  - active findings that need attention
  - disabled/quarantined findings that are likely already handled
  - missing/unknown findings that need manual interpretation
- Export the combined JSON report from the Doctor view.
- Validate against the real Sims 4 folder.

**Out:**

- Native macOS DiagnosticReports parsing.
- Live filesystem monitoring.
- Any file mutation, quarantine, rollback, restore, or auto-bisect action.
- Rewriting the shipped crash/UI analyzers.
- Changing existing CLI output.

## Architecture

The feature is a composition layer over shipped analysis code:

```text
React Doctor view
  -> web/src/api.js runAnalysis("doctor-scan", sims4_dir, options)
  -> Tauri start_analysis(kind="doctor-scan")
  -> simanalysis-bridge doctor-scan <sims4_dir> [--mods PATH]
  -> existing CrashAnalyzer + UICrashAnalyzer
  -> combined JSON result
```

The bridge remains process-per-task. stdout stays pure NDJSON. The frontend receives the same `start` / `progress` / `result` / `error` / `done` event shape as existing scans.

## Result Shape

The bridge result data is:

```json
{
  "summary": {
    "script_reports": 0,
    "script_active": 0,
    "script_disabled": 0,
    "script_not_installed": 0,
    "script_base_game_only": 0,
    "ui_findings": 0,
    "ui_occurrences": 0,
    "ui_active": 0,
    "ui_disabled": 0,
    "ui_not_found": 0,
    "ui_no_key": 0,
    "parse_errors": 0,
    "index_errors": 0
  },
  "script_crashes": {},
  "ui_crashes": {}
}
```

`script_crashes` is exactly `serialization.crash_result_to_dict(...)`.
`ui_crashes` is exactly `serialization.ui_result_to_dict(...)`.

## UI Behavior

The Doctor page:

- uses the existing dark operational app style
- adds a sidebar item labelled `Doctor`
- defaults the path input to `~/Documents/Electronic Arts/The Sims 4`
- saves no new persistent setting in this slice
- shows a compact summary band after scan
- renders grouped result lists:
  - `Needs Attention`
  - `Already Disabled`
  - `Missing or Unknown`
  - `Errors`
- shows raw evidence paths/keys in compact detail areas
- exports the combined JSON report with a `simanalysis-doctor-YYYY-MM-DD.json` filename

## Testing

- Unit-test the bridge command result shape and error handling.
- Unit-test the bridge parser accepts `doctor-scan`.
- Unit-test combined summary counting from synthetic script/UI payloads.
- Add frontend build coverage by ensuring the new route compiles.
- Validate manually with the real Sims 4 folder and record the result in `docs/superpowers/2026-05-30-desktop-doctor-validation.md`.

## Safety

Doctor v1 is read-only. It may read logs, `.ts4script` archives, and `.package` DBPF indexes. It must not write under the Sims 4 folder. Export writes only when the user uses browser download behavior.
