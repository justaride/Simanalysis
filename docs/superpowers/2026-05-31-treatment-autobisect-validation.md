# Treatment + Auto-Bisect Real-Folder Validation

Date: 2026-05-31
Branch: `feat/treatment-autobisect`

## Command

```bash
.venv/bin/simanalysis-bridge treatment-plan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Raw NDJSON was written outside the repo at `/tmp/simanalysis-treatment-plan.ndjson`.

## Result

- NDJSON sequence:
  1. `start`
  2. `result`
  3. `done`
- Default planning did not use `--save`.
- No live mod move was attempted.
- `_Simanalysis_Treatment` did not exist before the dry run and was not created by the dry-run command.

## Candidate Summary

- status: `planned`
- manifest path: `null`
- movable candidate count: 0
- next batch count: 0
- currently removed count: 0
- warnings: `["No active Doctor candidates can be moved."]`
- blockers: `[]`

## Safety Notes

The validation stayed read-only against the real Sims folder. Mutation behavior is covered by tmp-path unit tests.
