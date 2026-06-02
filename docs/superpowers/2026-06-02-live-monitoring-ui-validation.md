# Live Monitoring UI validation

Date: 2026-06-02
Branch: `codex/live-monitoring-ui`

## Commands

```text
cd web && node --test src/views/liveMonitorModel.test.js
cd web && npm run lint -- --quiet
cd web && npm run build
cd src-tauri && cargo test live_monitor --lib
cd src-tauri && cargo test bridge_error_event_counts_as_terminal_output --lib
cd src-tauri && cargo test cancelled_task_does_not_emit_crash_error --lib
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
.venv/bin/python -m bandit -r src/simanalysis -c pyproject.toml
fixture="/tmp/simanalysis-live-monitor-ui-fixture"; rm -rf "$fixture"; mkdir -p "$fixture/Mods"; printf "old crash" > "$fixture/lastException.txt"; .venv/bin/simanalysis-bridge live-monitor "$fixture" --once > /tmp/simanalysis-live-monitor-ui-once.ndjson; test ! -e "$fixture/_Simanalysis_Treatment"
```

## Results

- Frontend helper tests: PASS; 8 tests passed.
- Frontend lint: PASS.
- Frontend build: PASS; Vite built the production bundle.
- Rust live-monitor tests: PASS; 3 tests passed.
- Rust terminal-event regression test: PASS; 1 test passed.
- Rust cancellation regression test: PASS; 1 test passed.
- Focused Python Live Monitoring and bridge tests: PASS; 42 tests passed.
- Focused Treatment safety tests: PASS; 2 tests passed.
- Bandit security scan: PASS; no issues identified.
- Synthetic read-only monitor validation: PASS; `_Simanalysis_Treatment` was not created.

## Browser QA

- Desktop route check at `http://127.0.0.1:5299/live-monitor`: PASS. The route rendered, the sidebar included Live Monitor, and `scrollWidth` equaled `clientWidth` at `1280x720`.
- Manual Start/Stop check: PASS. Start changed the status to `Watching for new crash logs`, Stop changed it to `Monitoring stopped`, and no progress panel remained visible after Stop.
- Responsive check at `390x844`: PASS. The route remained usable with a collapsed sidebar, stacked controls, visible status cards, and no horizontal overflow (`scrollWidth=390`, `clientWidth=390`).

## Synthetic Monitor Output

```json
{"type":"start","task":"live-monitor","total":0,"v":1}
{"type":"progress","current":1,"total":1,"stage":"waiting","v":1}
{"type":"result","data":{"changed_logs":[],"watched_log_count":1,"doctor_summary":{},"treatment":{"candidate_count":0,"first_batch_count":0,"manifest_path":null,"warnings":[],"blockers":[]},"recommended_next_action":"waiting","warnings":[]},"v":1}
{"type":"done","v":1}
```

## Notes

- The Live Monitor UI is manual start/stop.
- Route changes do not cancel the monitor because the process handle lives in `LiveMonitorContext`.
- Live Monitoring remains read-only and only opens Treatment when the backend recommendation is `open_treatment`.
- Post-review validation added `Review Doctor` action coverage for `review_doctor` recommendations and surfaces monitor warnings plus Treatment blockers in the latest event card.
- Plain-browser QA logs the existing update-check error from `src/components/Layout.jsx` because Tauri `invoke` is unavailable outside the desktop shell. The Live Monitor route and controls still rendered and passed the checks above.
