# Live Monitoring validation

Date: 2026-05-31
Branch: `feat/live-monitoring`

## Commands

```text
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
cd src-tauri && cargo test live_monitor
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pip show bandit >/dev/null 2>&1 || uv pip install "bandit[toml]"
.venv/bin/python -m bandit -r src
fixture="/tmp/simanalysis-live-monitor-fixture"; rm -rf "$fixture"; mkdir -p "$fixture/Mods"; printf "old crash" > "$fixture/lastException.txt"; .venv/bin/simanalysis-bridge live-monitor "$fixture" --once > /tmp/simanalysis-live-monitor-once.ndjson; test ! -e "$fixture/_Simanalysis_Treatment"
.venv/bin/simanalysis-bridge live-monitor "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4" --once > /tmp/simanalysis-live-monitor-real-once.ndjson
```

## Results

- Focused Live Monitoring and bridge tests: PASS; 42 passed in 0.08s.
- Focused Treatment safety tests: PASS; 2 passed in 0.03s.
- Rust live monitor sidecar tests: PASS; 2 passed, 0 failed, 14 filtered out in `src-tauri` unit tests.
- Full Python unit suite: PASS; 354 passed in 1.44s. Coverage output was produced by default pytest options.
- Bandit setup: PASS; Bandit was missing from the worktree virtualenv and `uv pip install "bandit[toml]"` installed `bandit==1.9.4` and `stevedore==5.8.0`.
- Bandit: PASS; `No issues identified`, with 0 low, 0 medium, and 0 high severity findings. Bandit also reported comment-parsing warnings for non-test words in comments; these were warnings, not findings.
- Synthetic bridge validation: PASS; command exited 0, emitted `recommended_next_action: "waiting"`, watched 1 log, had `changed_logs: []`, and `_Simanalysis_Treatment` was not created.
- Real-folder read-only validation: PASS; command exited 0, emitted `recommended_next_action: "waiting"`, watched 10 logs, had `changed_logs: []`, and reported `manifest_path: null`. No Sims folder mutation command was performed.

## Notes

- Live Monitoring runs Treatment planning with `save=false`.
- `--once` establishes a fresh baseline and reports `waiting` when no log changes during that invocation.
- Live Monitoring does not create a Treatment manifest and does not move files.
- Real-folder validation used only the read-only command requested for `/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4`.
