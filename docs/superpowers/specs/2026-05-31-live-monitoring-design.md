# Live Monitoring - design

**Status:** Design approved; awaiting written-spec review before implementation planning
**Date:** 2026-05-31
**Roadmap:** Sub-project #2 of the "ultimate Sims doctor" roadmap. Builds on Doctor and Treatment by noticing new crash logs, running Doctor automatically, and producing a dry-run Treatment plan when there are active movable candidates.

## Goal

Add a read-only Live Monitoring backend that watches a Sims 4 folder for new or changed crash logs:

- `lastException*.txt`
- `lastUIException*.txt`

When a new crash log appears, Simanalysis should run the existing Doctor scan and then run Treatment planning in dry-run mode. The monitor should report whether there are active movable candidates ready for Treatment, without creating a Treatment manifest or moving files.

## Why now

Treatment + Auto-Bisect is ready, but real dry-run validation found no current active candidates to move. Live Monitoring makes Treatment useful at the moment a new crash appears: instead of asking the user to manually rerun Doctor after every game test, the app can detect the fresh log, explain it, and tell the user whether Treatment is now worth opening.

## Scope

**In:**

- Add a monitoring engine that polls a Sims 4 folder for new or changed `lastException*.txt` and `lastUIException*.txt` files.
- Use the existing Doctor builder for diagnosis after a log change.
- Use existing Treatment planning with `save=false` only.
- Emit structured bridge events so the desktop app can consume monitor results later.
- Support a one-shot mode for deterministic tests and manual validation.
- Avoid reprocessing unchanged logs within one monitor session.
- Return plain recommended next actions such as `open_treatment`, `no_movable_candidates`, and `review_doctor`.

**Out:**

- Desktop UI controls for starting or stopping monitoring.
- Launching The Sims 4.
- File moves, restores, quarantine actions, or Treatment session starts.
- Writing `_Simanalysis_Treatment` manifests.
- Mutating the real Sims folder.
- Permanent background daemon behavior.
- Network lookups, mod update checks, or creator identity resolution.

## Architecture

V1 should be CLI/bridge-first and stdlib-only.

```text
simanalysis.bridge
  live-monitor command
        |
        v
simanalysis.live_monitoring
  discover log files
  fingerprint files
  detect changed logs
  build Doctor payload
  build dry-run Treatment plan
  return monitor event
```

The monitoring module should not know about React or Tauri. It should expose a small service API that the bridge command can drive.

Suggested core units:

- `LogFingerprint`: path, size, modified timestamp, and optional content digest.
- `MonitorSnapshot`: current known fingerprints for matching log files.
- `MonitorEvent`: changed log metadata, Doctor summary, dry-run Treatment summary, warnings, and recommended action.
- `LiveMonitor`: stateful polling helper for a single Sims 4 folder.

The bridge command owns event emission and loop behavior. The service owns file discovery, change detection, and payload construction.

## Change Detection

The monitor scans only the selected Sims 4 folder root by default, matching the existing Doctor v1 default. A future option can add recursive monitoring if real logs require it.

For each matching log file, store:

- absolute path
- file size
- `mtime_ns`
- a short content digest when the file can be read

The size and timestamp make common changes cheap to detect. The digest protects against edge cases where timestamp resolution or replacement behavior is odd. Read failures should not crash the monitor; they should produce a warning and skip that file for the current poll.

At startup, the monitor should build a baseline snapshot. It should not immediately treat old logs as new unless `--include-existing` is added in a later version. V1 should respond to changes after monitoring starts. Tests can use one-shot mode with an injected prior snapshot.

## Commands

Add one bridge command:

```text
simanalysis-bridge live-monitor <sims4_dir> [--mods PATH] [--interval SECONDS] [--once]
```

Behavior:

- `--mods` defaults to `<sims4_dir>/Mods`, consistent with Doctor and Treatment.
- `--interval` defaults to a small human-friendly polling interval, such as `2.0` seconds.
- `--once` performs one poll after creating the monitor and returns immediately. It is mainly for tests and manual validation.

Bridge event shape should reuse existing NDJSON events:

- `start`: command started, with total unset or unknown.
- `progress`: heartbeat or poll status, including watched log count.
- `result`: emitted when a changed log triggers a Doctor/Treatment dry-run result.
- `done`: emitted only when `--once` finishes or the process exits cleanly.
- `error`: emitted for invalid input or unrecoverable failures.

If no new logs are detected in `--once` mode, return a result with `changed_logs: []` and `recommended_next_action: "waiting"`.

## Monitor Result Shape

The result should be compact and stable:

```json
{
  "changed_logs": [
    {
      "path": "/.../lastException.txt",
      "name": "lastException.txt",
      "kind": "script",
      "size": 12345,
      "mtime_ns": 1760000000000000000
    }
  ],
  "doctor_summary": {
    "script_reports": 1,
    "script_active": 1,
    "ui_findings": 0,
    "ui_active": 0
  },
  "treatment": {
    "candidate_count": 1,
    "first_batch_count": 1,
    "manifest_path": null,
    "warnings": []
  },
  "recommended_next_action": "open_treatment"
}
```

Recommended action rules:

1. `open_treatment` when the dry-run Treatment plan has one or more active candidates.
2. `review_doctor` when Doctor found current evidence, but Treatment could not turn that evidence into a safe move candidate because of unresolved active evidence, parse errors, or index errors.
3. `no_movable_candidates` when Doctor has findings, but they are already disabled, not installed, not found, no-key, or otherwise non-actionable.
4. `waiting` when no logs changed during the current poll.

The result may include the full Doctor payload later, but V1 should start with summary-first output to keep bridge messages small.

## Safety Model

Live Monitoring is read-only.

It may read:

- crash logs in the selected Sims 4 folder
- active `Mods`
- disabled/quarantined roots that Doctor already indexes

It must not:

- write under the Sims 4 folder
- create `_Simanalysis_Treatment`
- create a Treatment manifest
- move, restore, rename, delete, or quarantine files
- infer that a candidate is confirmed without a game test

The implementation should call Treatment planning with `save=false` only. Tests must assert that monitoring does not create `_Simanalysis_Treatment`.

## Error Handling

- Invalid Sims 4 folder: bridge returns `INVALID_INPUT`.
- Missing Mods folder: monitor can still report the changed log, but Doctor/Treatment summaries should explain that no movable candidates are available.
- Log read error: skip that file for the poll and include a warning.
- Doctor parse/index errors: surface existing Doctor summary counts and warnings rather than failing the monitor.
- Treatment planning error: return the Doctor summary and a Treatment warning so the user still sees the new crash evidence.
- Keyboard interruption or cancellation: exit cleanly without writing files.

## Testing

- Unit-test fingerprint creation for readable logs.
- Unit-test changed-log detection for new files, modified files, unchanged files, and unreadable files.
- Unit-test that startup baseline does not immediately process old logs.
- Unit-test `--once` result when no logs changed.
- Unit-test that a new script log triggers Doctor plus dry-run Treatment.
- Unit-test that a new UI log triggers Doctor plus dry-run Treatment.
- Unit-test recommended-action selection.
- Unit-test bridge parser and dispatch for `live-monitor`.
- Unit-test that monitoring never creates `_Simanalysis_Treatment`.
- Run the focused Doctor/Treatment bridge tests.
- Run Bandit before pushing.

## Validation Plan

Use a synthetic Sims 4 fixture under `/tmp` for mutation-safe validation:

```text
simanalysis-bridge live-monitor /tmp/simanalysis-live-monitor-fixture --once
```

Expected validation evidence:

- old baseline logs are ignored
- `--once` emits a waiting/no-change result after establishing a fresh baseline
- `_Simanalysis_Treatment` is not created

Use a second synthetic validation with the monitor running while a new log is written:

```text
simanalysis-bridge live-monitor /tmp/simanalysis-live-monitor-fixture --interval 0.2
```

Expected validation evidence:

- newly written logs are detected after startup
- Doctor summary is emitted
- Treatment dry-run summary has `manifest_path: null`
- `_Simanalysis_Treatment` is still not created

Real-folder validation may be read-only:

```text
simanalysis-bridge live-monitor "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --once
```

Expected real-folder behavior is a waiting/no-change event unless a new crash log appears during the check. This must not mutate the real Sims folder.

## Later Work

- Desktop UI controls for starting/stopping monitoring.
- Notification-style UI when a new crash appears.
- Optional recursive log monitoring.
- Persisted monitor state across app restarts.
- Direct "Open Treatment" handoff using the dry-run result.
- Suggested Treatment outcome after a monitored game test, still requiring user confirmation before any file movement.
