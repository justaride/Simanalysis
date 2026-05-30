# UI Crash Autopsy Validation (2026-05-30)

Command:

```bash
.venv/bin/python -m simanalysis.cli ui-crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --format json --output /tmp/simanalysis-ui-crash-real.json
.venv/bin/python -m simanalysis.cli ui-crash "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --limit 10
```

Result:

- Root `lastUIException*.txt` logs parsed successfully: 5 log files.
- Repeated interaction-menu reports collapsed by signature: 1 unique UI finding, 27 occurrences.
- Key `15023068382072182982` / `0xD07CA9190DD098C6` was detected.
- The finding classified as `disabled`.
- The matching disabled/quarantined package included `adeepindigo_base_generalpiemenus_v3-2.package` under `_Quarantine_UI_Breakage_20260525`.
- No UI log parse errors were reported.
- Two disabled/quarantine package index errors were surfaced without aborting the analysis:
  - `_Disabled_Khlas_CorruptThumbnail_20260529-214732/!OPTIONAL_Khlas_Virile_Thumbnail.package`
  - `_Quarantine_Bad_Files_20260526_004405/Felixandre_December_2017.package`

Verification:

```text
{'unique_findings': 1, 'occurrences': 27, 'active_findings': 0, 'disabled_findings': 1, 'not_found_findings': 0, 'no_key_findings': 0}
disabled
['adeepindigo_base_generalpiemenus_v3-2.package']
index_errors 2
```

Interpretation:

The current UI exception points at a pie-menu category resource that is not active in `Mods` but is present in a quarantined adeepindigo package. This is evidence for a missing/disabled resource relationship, not proof that any file should be moved automatically. Treatment and auto-bisect remain out of scope for this cycle.
