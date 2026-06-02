# Live Monitoring UI - design

**Status:** Design approved; awaiting written-spec review before implementation planning
**Date:** 2026-06-01
**Roadmap:** Follow-up to the shipped Live Monitoring backend. This turns the backend monitor into a manual desktop workflow for game-test sessions, without release or packaging work.

## Goal

Add a manual Live Monitoring page to the desktop app.

The user chooses or confirms the Sims 4 folder, clicks Start, and the app watches for new or changed crash logs:

- `lastException*.txt`
- `lastUIException*.txt`

When a log changes, the app uses the existing Live Monitoring backend to run Doctor and dry-run Treatment planning. The UI shows a compact result and recommends whether to keep waiting, review Doctor, or open Treatment.

## Why now

Treatment + Auto-Bisect and the Live Monitoring backend are already shipped. The missing piece is the user-facing loop: while testing The Sims 4, the app should quietly watch the folder and surface the next useful action when a new crash appears.

There is no release rush for this cycle. The priority is a calm, trustworthy workflow that helps with real mod recovery sessions.

## Product Decisions

- Monitoring is manually started and stopped by the user.
- Monitoring does not auto-start when the app opens.
- The app may remember or prefill the last Sims 4 folder if existing app settings support that, but the user still presses Start.
- The monitor keeps running if the user navigates away from the Live Monitoring page.
- The monitor stops when the user presses Stop, when the app closes, or when the monitor process exits.
- Live Monitoring is read-only. It must not move files, write Treatment manifests, or mutate the Sims folder.

## Scope

**In:**

- Dedicated desktop route and sidebar item for Live Monitoring.
- Sims 4 folder input or picker.
- Start and Stop controls.
- Running status with watched log count and last check time.
- Latest monitor event display.
- Event history for the current app session.
- Doctor summary in the event view.
- Treatment dry-run summary in the event view.
- Recommendation display using backend `recommended_next_action`.
- Open Treatment button only when the recommendation is `open_treatment`.
- Clear error and stopped states.

**Out:**

- Auto-start on app launch.
- Permanent background daemon behavior.
- OS notifications.
- Launching The Sims 4.
- Recursive log monitoring unless already supported cleanly by the backend command.
- Persisting monitor history across app restarts.
- Release packaging, signing, notarization, auto-update, or installer work.
- Network lookups, creator identity resolution, or mod update checks.
- Any file move, restore, delete, quarantine, or Treatment manifest creation.

## User Flow

1. The user opens `Live Monitor`.
2. The page shows the current Sims 4 folder if known, or lets the user choose it.
3. The user clicks Start.
4. The page enters Watching state and shows:
   - selected Sims 4 folder
   - watched log count
   - last check time
   - current recommendation
5. If no log changes, the page stays quiet and indicates it is waiting.
6. If a new or changed crash log appears, the page shows an event card with:
   - changed log names
   - script crash count
   - UI finding count
   - active evidence count
   - dry-run Treatment candidate count
   - recommendation
7. If the recommendation is `open_treatment`, the event card offers Open Treatment.
8. If the recommendation is `review_doctor`, the event card nudges the user toward Doctor review.
9. If the recommendation is `no_movable_candidates`, the event card explains that there is evidence but nothing safe to move.
10. The user can press Stop at any time. Stop ends the running monitor process and leaves the latest event visible.

## Page Structure

The Live Monitor page should feel like a tool surface, not a marketing page.

Recommended layout:

- Header row: `Live Monitor`, folder selector, Start/Stop button.
- Status strip: Idle, Watching, Event detected, Error, or Stopped.
- Current event panel: latest result and recommendation.
- Session history: compact list of detected events from the current monitor run.

Text should be plain and low-jargon. The UI should avoid implying that a culprit is confirmed. It can say "Treatment has candidates to test" but not "this mod is the culprit" unless a separate Treatment session has proven that through user-confirmed game testing.

## UI States

`idle`

- Folder is chosen or can be chosen.
- Start is enabled when the folder path is non-empty.
- No monitor process is running.

`watching`

- Monitor process is running.
- Start is disabled.
- Stop is enabled.
- The UI shows watched log count and last check time when available.

`event_detected`

- A monitor result contains changed logs.
- The latest event card becomes the primary content.
- Recommendation and next action are visible.

`needs_review`

- Doctor saw evidence, but Treatment dry-run cannot produce a safe move candidate.
- The UI should guide the user to review Doctor rather than starting Treatment.

`error`

- Folder is invalid, command fails, backend emits an error, or the process exits unexpectedly.
- Stop should clean up any running handle if possible.
- The latest successful event remains visible if one exists.

`stopped`

- User stopped monitoring cleanly.
- The latest event and session history remain visible until a new run starts.

## Architecture

The UI should be a thin layer over the backend that landed in PR #14.

Suggested files:

- `web/src/views/LiveMonitor.jsx`
- `web/src/api.js`
- `web/src/App.jsx`
- `web/src/components/Sidebar.jsx`

The React view should use the existing `runAnalysis` transport pattern. It should start the `live-monitor` bridge command with the selected Sims 4 folder, optional Mods path if the app already exposes one, and a polling interval.

The backend logic should remain in:

- `src/simanalysis/live_monitoring.py`
- `src/simanalysis/bridge/commands.py`
- `src-tauri/src/lib.rs`

Do not duplicate Doctor or Treatment logic in React. The frontend consumes monitor events and renders them.

## Process Lifetime

The monitor is app-session state.

- Starting creates a running sidecar command.
- Stopping cancels the sidecar command through the existing app command-runner path.
- Navigating away from the Live Monitor route does not stop monitoring.
- Closing the app stops the sidecar as part of normal process cleanup.

If the current command-runner abstraction cannot preserve a running command across route unmounts, this slice should add the smallest shared state needed to keep the monitor handle at app scope.

## Event Handling

The UI should treat backend events as the source of truth:

- `start`: mark process as running.
- `progress`: update watched log count, last check time, and heartbeat text.
- `result`: update latest event and append to session history.
- `error`: enter error state and display the backend message.
- `done`: enter stopped state if the user requested stop, or idle/stopped with a clear message if the backend exited.

The existing backend may emit `waiting` results in one-shot mode. For a long-running UI monitor, waiting should be shown as status, not as a noisy event card.

## Recommendation Rules

Use the backend `recommended_next_action` values directly:

- `open_treatment`: show Open Treatment as the primary action.
- `review_doctor`: show Review Doctor as the primary action.
- `no_movable_candidates`: show a calm explanation and no mutation action.
- `waiting`: show quiet Watching status.

If the backend returns an unknown value, render it as `review_doctor` style: show the result, avoid Treatment actions, and make no mutation claims.

## Safety Model

Live Monitoring UI is read-only.

It may:

- read crash logs through the backend
- run Doctor through the backend
- run Treatment planning with `save=false`
- display summaries and recommendations
- route the user to Treatment when candidates exist

It must not:

- create `_Simanalysis_Treatment`
- create a Treatment manifest
- move, restore, rename, delete, or quarantine files
- start a Treatment session automatically
- infer that a candidate is confirmed without user-reported game-test outcome
- launch The Sims 4

Tests must preserve the existing backend guarantee that monitoring does not create `_Simanalysis_Treatment`.

## Error Handling

- Missing or invalid Sims 4 folder: show an inline error and keep Start disabled or fail cleanly.
- Missing Mods folder: show the monitor result, but do not offer Treatment unless the backend has candidates.
- Backend error event: show the message and keep the last successful event visible.
- Unexpected process exit: enter Error or Stopped state with a plain explanation.
- Stop failure: show the error and allow retry.

## Testing

Frontend/unit testing should cover:

- Live Monitor route renders.
- Start is disabled without a folder.
- Start calls the live-monitor API with the selected folder.
- Progress events update watched count and heartbeat status.
- Waiting results do not create noisy event cards.
- New script-log result creates an event card.
- New UI-log result creates an event card.
- `open_treatment` shows Open Treatment.
- `review_doctor` does not show Open Treatment.
- `no_movable_candidates` does not show Open Treatment.
- Stop calls the cancellation path and enters Stopped state.
- Error events render an error state without clearing prior results.

Backend and integration checks should cover:

- Existing Live Monitoring unit tests still pass.
- Existing Treatment dry-run safety tests still pass.
- Existing bridge command tests still pass.
- Tauri command mapping for `live-monitor` still passes.
- A synthetic monitor run does not create `_Simanalysis_Treatment`.
- A real-folder one-shot validation remains read-only.

## Validation Plan

Use the existing shipped backend validation as the base, then add UI validation:

1. Run focused Python tests for Live Monitoring, Treatment safety, bridge commands, and bridge main.
2. Run Rust tests for live-monitor command argument mapping.
3. Run frontend tests or build checks used by the repo.
4. Start the desktop app locally.
5. Open Live Monitor.
6. Select the real Sims 4 folder.
7. Start monitoring and confirm the UI enters Watching state.
8. Stop monitoring and confirm the UI enters Stopped state.
9. Run a synthetic fixture or controlled bridge event test to confirm an event card renders for a changed log.
10. Confirm no `_Simanalysis_Treatment` folder is created by monitor-only validation.

Real-folder validation must remain read-only.

## Later Work

- OS-level notifications.
- Persisted monitor history across app restarts.
- Optional auto-start after explicit user opt-in.
- Optional recursive monitoring.
- Directly pass the latest dry-run result into Treatment.
- Suggested Treatment outcome after a monitored game test, still requiring user confirmation.
- A larger guided test-session flow that combines Live Monitor and Treatment into one screen.
