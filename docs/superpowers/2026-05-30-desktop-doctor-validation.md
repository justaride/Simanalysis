# Desktop Doctor validation

Date: 2026-05-30
Branch: `feat/desktop-doctor`
Command:

```bash
.venv/bin/simanalysis-bridge doctor-scan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

The raw NDJSON output was written outside the repo at `/tmp/simanalysis-doctor-real.ndjson`.

## Result

The sidecar emitted valid NDJSON in the expected sequence:

1. `start`
2. `progress` for `script-crashes`
3. `progress` for `ui-crashes`
4. `result`
5. `done`

Combined summary:

```json
{
  "script_reports": 92,
  "script_active": 0,
  "script_disabled": 82,
  "script_not_installed": 10,
  "script_base_game_only": 0,
  "ui_findings": 1,
  "ui_occurrences": 27,
  "ui_active": 0,
  "ui_disabled": 1,
  "ui_not_found": 0,
  "ui_no_key": 0,
  "parse_errors": 0,
  "index_errors": 2
}
```

## Script crash autopsy

The top ranked script result was already disabled:

- `delimaci_teenparamediccareer.ts4script`
- top suspect in 82 crash reports
- seen in 82 crash reports
- status `disabled`

The remaining ranked entries were best-effort `not_installed` references from Basemental Gangs paths:

- `cosasimstra.py`
- `fsg.py`
- `nct.py`
- `simkuza.py`
- `tuning_enums.py`

This matches the expected read-only Doctor behavior: it explains historical crash evidence without changing the mod tree.

## UI crash autopsy

The UI result reproduced the known pie-menu failure:

- message: `Failed to locate category info for interaction category with key: 15023068382072182982`
- key: `0xD07CA9190DD098C6`
- occurrences: 27
- status: `disabled`
- package: `adeepindigo_base_generalpiemenus_v3-2.package`
- path: `/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4/_Quarantine_UI_Breakage_20260525/Sms 22.04/Mod Files/adeepindigo_base_generalpiemenus_v3-2.package`

No active UI package hit was reported for that key.

## Index errors

Two disabled/quarantined package index errors were surfaced without aborting the scan:

- `_Disabled_Khlas_CorruptThumbnail_20260529-214732/!OPTIONAL_Khlas_Virile_Thumbnail.package`
- `_Quarantine_Bad_Files_20260526_004405/Felixandre_December_2017.package`

These are non-fatal and appear in the combined Doctor report as `index_errors`.
