# Live Monitoring UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual desktop Live Monitor page that starts and stops the shipped `live-monitor` backend, keeps watching across route changes, and shows read-only Doctor/Treatment recommendations when new crash logs appear.

**Architecture:** Reuse the existing Tauri sidecar transport and React route pattern. Add a small streaming-safe transport adjustment for `live-monitor`, a pure view-model module for monitor summaries, a React context that owns the running monitor handle at app scope, and a dedicated `LiveMonitor` view that renders folder controls, status, latest event, and current-session history.

**Tech Stack:** React 18, React Router, Tailwind, lucide-react, Framer Motion, Tauri v2, Rust unit tests, Node built-in test runner for pure frontend logic, existing Python bridge tests.

---

## Scope Check

The approved spec covers one subsystem: the desktop UI workflow for the already-shipped Live Monitoring backend. Release packaging, OS notifications, game launching, mod update lookup, creator identity resolution, and automatic Treatment mutation are out of scope.

## File Structure

- Modify `src-tauri/src/lib.rs` to make `live-monitor` result events non-terminal while preserving terminal handling for one-shot commands.
- Modify `web/src/api.js` to expose `api.monitorLive(...)` and route `done` events to callbacks.
- Create `web/src/views/liveMonitorModel.js` for pure status, recommendation, and summary helpers.
- Create `web/src/views/liveMonitorModel.test.js` with Node tests for helper behavior.
- Create `web/src/context/LiveMonitorContext.jsx` to own monitor process state across route changes.
- Modify `web/src/main.jsx` to wrap the app with `LiveMonitorProvider`.
- Create `web/src/views/LiveMonitor.jsx` for the dedicated UI route.
- Modify `web/src/App.jsx` to lazy-load the route.
- Modify `web/src/components/Sidebar.jsx` to add the Live Monitor nav item.
- No Python backend changes are planned unless validation proves the current backend event shape is missing required fields.

---

### Task 1: Make the Tauri Transport Streaming-Safe for Live Monitor

**Files:**
- Modify: `src-tauri/src/lib.rs`

- [ ] **Step 1: Write the failing Rust test**

In `src-tauri/src/lib.rs`, change the test import and replace the terminal-event test at the end of the `tests` module:

```rust
use super::{
    build_args, drain_complete_lines, is_terminal_bridge_event, should_emit_crash_error,
    AnalysisOptions,
};
use serde_json::json;

#[test]
fn bridge_error_event_counts_as_terminal_output() {
    assert!(is_terminal_bridge_event("doctor-scan", &json!({"type": "error"})));
    assert!(is_terminal_bridge_event("doctor-scan", &json!({"type": "result"})));
    assert!(!is_terminal_bridge_event("doctor-scan", &json!({"type": "progress"})));
}

#[test]
fn live_monitor_result_event_is_not_terminal_output() {
    assert!(!is_terminal_bridge_event("live-monitor", &json!({"type": "result"})));
    assert!(is_terminal_bridge_event("live-monitor", &json!({"type": "error"})));
    assert!(!is_terminal_bridge_event("live-monitor", &json!({"type": "progress"})));
}

#[test]
fn cancelled_task_does_not_emit_crash_error() {
    assert!(!should_emit_crash_error(1, false, true));
}

#[test]
fn non_cancelled_nonzero_exit_without_terminal_event_emits_crash_error() {
    assert!(should_emit_crash_error(1, false, false));
}
```

- [ ] **Step 2: Run the Rust test and confirm it fails**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/src-tauri
cargo test live_monitor_result_event_is_not_terminal_output --lib
```

Expected: FAIL or compile error because `is_terminal_bridge_event` currently accepts only one argument and `should_emit_crash_error` does not exist yet.

- [ ] **Step 3: Update terminal-event detection**

In `src-tauri/src/lib.rs`, replace the current `is_terminal_bridge_event` and `forward_line` definitions with:

```rust
fn is_terminal_bridge_event(kind: &str, value: &Value) -> bool {
    let event_type = value.get("type").and_then(|t| t.as_str());
    match (kind, event_type) {
        ("live-monitor", Some("result")) => false,
        (_, Some("result" | "error")) => true,
        _ => false,
    }
}

fn should_emit_crash_error(code: i32, saw_terminal_event: bool, was_cancelled: bool) -> bool {
    code != 0 && !saw_terminal_event && !was_cancelled
}

fn forward_line(kind: &str, on_event: &Channel<Value>, line: &[u8]) -> bool {
    let text = match std::str::from_utf8(line) {
        Ok(t) => t.trim(),
        Err(_) => return false,
    };
    if text.is_empty() {
        return false;
    }
    match serde_json::from_str::<Value>(text) {
        Ok(value) => {
            let is_terminal = is_terminal_bridge_event(kind, &value);
            let _ = on_event.send(value);
            is_terminal
        }
        Err(e) => {
            eprintln!("dropping non-JSON stdout line: {e}: {text}");
            false
        }
    }
}
```

Then update both call sites inside `start_analysis`:

```rust
if forward_line(&kind, &on_event, &line) {
    saw_terminal_event = true;
}
```

and:

```rust
if forward_line(&kind, &on_event, &buf) {
    saw_terminal_event = true;
}
```

Because `kind` is moved into the spawned async block, keep the existing `kind` binding from `start_analysis` and use it inside that block. Do not clone it unless the compiler requires it.

In the `CommandEvent::Terminated(payload)` arm, replace the existing nonzero-exit check with a cancellation-aware check:

```rust
let code = payload.code.unwrap_or(-1);
let was_cancelled = !reader_app
    .state::<ChildRegistry>()
    .0
    .lock()
    .unwrap()
    .contains_key(&task_id);
if should_emit_crash_error(code, saw_terminal_event, was_cancelled) {
    let _ = on_event.send(serde_json::json!({
        "v": 1, "type": "error", "code": "CRASHED",
        "message": format!("analyzer exited with code {code}; see logs")
    }));
}
```

This keeps manual Stop from turning into a fake crash error after `cancel_analysis` removes and kills the child.

- [ ] **Step 4: Run focused Rust tests**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/src-tauri
cargo test live_monitor --lib
cargo test bridge_error_event_counts_as_terminal_output --lib
cargo test cancelled_task_does_not_emit_crash_error --lib
```

Expected: all three commands PASS.

- [ ] **Step 5: Commit Task 1**

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git add src-tauri/src/lib.rs
git commit -m "fix: keep live monitor stream open"
```

---

### Task 2: Add Pure Live Monitor View-Model Helpers

**Files:**
- Create: `web/src/views/liveMonitorModel.js`
- Create: `web/src/views/liveMonitorModel.test.js`

- [ ] **Step 1: Create the failing Node tests**

Create `web/src/views/liveMonitorModel.test.js`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {
    describeRecommendation,
    summarizeMonitorEvent,
    shouldRecordMonitorEvent,
    statusText,
} from './liveMonitorModel.js';

test('waiting results are not recorded as noisy events', () => {
    assert.equal(
        shouldRecordMonitorEvent({ changed_logs: [], recommended_next_action: 'waiting' }),
        false,
    );
});

test('changed log results are recorded as events', () => {
    assert.equal(
        shouldRecordMonitorEvent({
            changed_logs: [{ name: 'lastException.txt' }],
            recommended_next_action: 'review_doctor',
        }),
        true,
    );
});

test('open treatment recommendation is primary and safe-worded', () => {
    assert.deepEqual(describeRecommendation('open_treatment'), {
        tone: 'emerald',
        title: 'Treatment has candidates to test',
        body: 'A new crash log produced active movable candidates. Open Treatment when you are ready to run a reversible test step.',
        primaryAction: 'open_treatment',
    });
});

test('unknown recommendation falls back to doctor review', () => {
    assert.deepEqual(describeRecommendation('surprise'), {
        tone: 'amber',
        title: 'Review the Doctor evidence',
        body: 'Simanalysis found evidence, but it is not safe to turn it into a Treatment action from this monitor event.',
        primaryAction: 'review_doctor',
    });
});

test('summarize monitor event extracts stable counts', () => {
    const summary = summarizeMonitorEvent({
        changed_logs: [{ name: 'lastUIException.txt' }],
        watched_log_count: 10,
        doctor_summary: {
            script_reports: 2,
            script_active: 1,
            ui_findings: 3,
            ui_active: 2,
        },
        treatment: {
            candidate_count: 4,
            first_batch_count: 2,
            manifest_path: null,
        },
        recommended_next_action: 'open_treatment',
    });

    assert.deepEqual(summary, {
        changedLogNames: ['lastUIException.txt'],
        watchedLogCount: 10,
        scriptReports: 2,
        scriptActive: 1,
        uiFindings: 3,
        uiActive: 2,
        candidateCount: 4,
        firstBatchCount: 2,
        manifestPath: null,
        recommendation: 'open_treatment',
    });
});

test('status text is plain and low-jargon', () => {
    assert.equal(statusText('idle'), 'Ready to watch');
    assert.equal(statusText('watching'), 'Watching for new crash logs');
    assert.equal(statusText('event_detected'), 'New crash evidence detected');
    assert.equal(statusText('needs_review'), 'Doctor review needed');
    assert.equal(statusText('error'), 'Monitor needs attention');
    assert.equal(statusText('stopped'), 'Monitoring stopped');
});
```

- [ ] **Step 2: Run the Node tests and confirm they fail**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
node --test src/views/liveMonitorModel.test.js
```

Expected: FAIL with module-not-found for `liveMonitorModel.js`.

- [ ] **Step 3: Create the helper module**

Create `web/src/views/liveMonitorModel.js`:

```javascript
const RECOMMENDATIONS = {
    open_treatment: {
        tone: 'emerald',
        title: 'Treatment has candidates to test',
        body: 'A new crash log produced active movable candidates. Open Treatment when you are ready to run a reversible test step.',
        primaryAction: 'open_treatment',
    },
    review_doctor: {
        tone: 'amber',
        title: 'Review the Doctor evidence',
        body: 'Simanalysis found evidence, but it is not safe to turn it into a Treatment action from this monitor event.',
        primaryAction: 'review_doctor',
    },
    no_movable_candidates: {
        tone: 'blue',
        title: 'No movable candidates',
        body: 'The new evidence does not point at anything Simanalysis can safely move. Keep the log for review.',
        primaryAction: null,
    },
    waiting: {
        tone: 'gray',
        title: 'Waiting for a new crash log',
        body: 'No new crash evidence has appeared since monitoring started.',
        primaryAction: null,
    },
};

const STATUS_TEXT = {
    idle: 'Ready to watch',
    watching: 'Watching for new crash logs',
    event_detected: 'New crash evidence detected',
    needs_review: 'Doctor review needed',
    error: 'Monitor needs attention',
    stopped: 'Monitoring stopped',
};

export function describeRecommendation(action) {
    return RECOMMENDATIONS[action] || RECOMMENDATIONS.review_doctor;
}

export function shouldRecordMonitorEvent(data) {
    return (data?.changed_logs || []).length > 0;
}

export function summarizeMonitorEvent(data = {}) {
    const doctor = data.doctor_summary || {};
    const treatment = data.treatment || {};
    return {
        changedLogNames: (data.changed_logs || []).map((log) => log.name || log.path || 'crash log'),
        watchedLogCount: data.watched_log_count || 0,
        scriptReports: doctor.script_reports || 0,
        scriptActive: doctor.script_active || 0,
        uiFindings: doctor.ui_findings || 0,
        uiActive: doctor.ui_active || 0,
        candidateCount: treatment.candidate_count || 0,
        firstBatchCount: treatment.first_batch_count || 0,
        manifestPath: treatment.manifest_path || null,
        recommendation: data.recommended_next_action || 'waiting',
    };
}

export function statusText(status) {
    return STATUS_TEXT[status] || STATUS_TEXT.idle;
}
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
node --test src/views/liveMonitorModel.test.js
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git add web/src/views/liveMonitorModel.js web/src/views/liveMonitorModel.test.js
git commit -m "test: add live monitor view model"
```

---

### Task 3: Add Live Monitor API and App-Scope Context

**Files:**
- Modify: `web/src/api.js`
- Create: `web/src/context/LiveMonitorContext.jsx`
- Modify: `web/src/main.jsx`

- [ ] **Step 1: Add API support for done events and monitorLive**

In `web/src/api.js`, update the `channel.onmessage` switch so `result` and `done` are handled like this:

```javascript
      case 'result':
        callbacks?.onResult?.(msg.data);
        callbacks?.onComplete?.(msg.data);
        break;
      case 'done':
        callbacks?.onDone?.();
        break;
```

Then add the API method after `scanDoctor`:

```javascript
  monitorLive: (sims4Path, modsPath, interval, callbacks) =>
    runAnalysis(
      'live-monitor',
      sims4Path,
      { modsPath, interval, once: false },
      callbacks,
    ),
```

Existing one-shot commands can keep using `onComplete`. The new view should use `onResult` for monitor events.

- [ ] **Step 2: Create the LiveMonitorContext**

Create `web/src/context/LiveMonitorContext.jsx`:

```javascript
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import api from '../api';
import { shouldRecordMonitorEvent } from '../views/liveMonitorModel';

const DEFAULT_SIMS_PATH = '~/Documents/Electronic Arts/The Sims 4';
const DEFAULT_INTERVAL = 2;

const LiveMonitorContext = createContext(null);

function nextStatusFromResult(data) {
    if (data?.recommended_next_action === 'review_doctor') return 'needs_review';
    if ((data?.changed_logs || []).length > 0) return 'event_detected';
    return 'watching';
}

export function LiveMonitorProvider({ children }) {
    const handleRef = useRef(null);
    const [simsPath, setSimsPath] = useState(DEFAULT_SIMS_PATH);
    const [modsPath, setModsPath] = useState('');
    const [status, setStatus] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [latestEvent, setLatestEvent] = useState(null);
    const [history, setHistory] = useState([]);
    const [error, setError] = useState(null);

    const stop = useCallback(() => {
        handleRef.current?.cancel?.();
        handleRef.current = null;
        setStatus('stopped');
    }, []);

    const start = useCallback(() => {
        if (!simsPath.trim()) {
            setError('Enter your Sims 4 folder path.');
            setStatus('error');
            return;
        }

        handleRef.current?.cancel?.();
        setError(null);
        setProgress(null);
        setLatestEvent(null);
        setHistory([]);
        setStatus('watching');

        handleRef.current = api.monitorLive(simsPath.trim(), modsPath.trim() || null, DEFAULT_INTERVAL, {
            onStart: () => setStatus('watching'),
            onProgress: (nextProgress) => {
                setProgress(nextProgress);
                setStatus((current) => (current === 'error' ? current : 'watching'));
            },
            onResult: (data) => {
                setProgress(null);
                setStatus(nextStatusFromResult(data));
                if (!shouldRecordMonitorEvent(data)) return;
                const event = {
                    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                    receivedAt: new Date().toISOString(),
                    data,
                };
                setLatestEvent(event);
                setHistory((items) => [event, ...items].slice(0, 20));
            },
            onError: (message) => {
                setError(message);
                setProgress(null);
                setStatus('error');
                handleRef.current = null;
            },
            onDone: () => {
                handleRef.current = null;
                setStatus((current) => (current === 'error' ? current : 'stopped'));
            },
        });
    }, [modsPath, simsPath]);

    useEffect(() => () => {
        handleRef.current?.cancel?.();
        handleRef.current = null;
    }, []);

    const isWatching = status === 'watching' || status === 'event_detected' || status === 'needs_review';

    return (
        <LiveMonitorContext.Provider
            value={{
                simsPath,
                setSimsPath,
                modsPath,
                setModsPath,
                status,
                progress,
                latestEvent,
                history,
                error,
                isWatching,
                start,
                stop,
            }}
        >
            {children}
        </LiveMonitorContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useLiveMonitor() {
    const context = useContext(LiveMonitorContext);
    if (!context) {
        throw new Error('useLiveMonitor must be used within LiveMonitorProvider');
    }
    return context;
}
```

- [ ] **Step 3: Wrap the app with the provider**

In `web/src/main.jsx`, add:

```javascript
import { LiveMonitorProvider } from './context/LiveMonitorContext'
```

Then wrap `App` inside `LiveMonitorProvider`:

```jsx
                <AppProvider>
                    <LiveMonitorProvider>
                        <App />
                    </LiveMonitorProvider>
                </AppProvider>
```

- [ ] **Step 4: Run web build**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git add web/src/api.js web/src/context/LiveMonitorContext.jsx web/src/main.jsx
git commit -m "feat: add live monitor app state"
```

---

### Task 4: Add Route and Sidebar Navigation

**Files:**
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Sidebar.jsx`

- [ ] **Step 1: Add the lazy route**

In `web/src/App.jsx`, add the lazy import:

```javascript
const LiveMonitor = lazy(() => import('./views/LiveMonitor'));
```

Then add the route after Doctor:

```jsx
<Route path="/live-monitor" element={<LiveMonitor />} />
```

- [ ] **Step 2: Add the sidebar item**

In `web/src/components/Sidebar.jsx`, add `RadioTower` to the lucide imports:

```javascript
import { LayoutDashboard, Package, Home, FileSearch, AlertTriangle, Settings, ChevronLeft, ChevronRight, Microscope, Stethoscope, RadioTower } from 'lucide-react';
```

Add the nav item after Doctor and before Treatment:

```javascript
{ path: '/live-monitor', icon: RadioTower, label: 'Live Monitor' },
```

- [ ] **Step 3: Run web build**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
npm run build
```

Expected: FAIL until `web/src/views/LiveMonitor.jsx` exists. This confirms the route is wired.

- [ ] **Step 4: Do not commit this task yet**

This task intentionally leaves the app failing until the view is created in Task 5. Commit route, sidebar, and view together in Task 5.

---

### Task 5: Build the Live Monitor View

**Files:**
- Create: `web/src/views/LiveMonitor.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Sidebar.jsx`

- [ ] **Step 1: Create the view**

Create `web/src/views/LiveMonitor.jsx`:

```jsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    AlertTriangle,
    Clock,
    FileWarning,
    FolderOpen,
    History,
    Loader2,
    RadioTower,
    ShieldCheck,
    Square,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import FilePicker from '../components/FilePicker';
import { useLiveMonitor } from '../context/LiveMonitorContext';
import {
    describeRecommendation,
    statusText,
    summarizeMonitorEvent,
} from './liveMonitorModel';

function toneClasses(tone) {
    return {
        emerald: 'border-emerald-500/30 bg-emerald-950/20 text-emerald-100',
        amber: 'border-amber-500/30 bg-amber-950/20 text-amber-100',
        blue: 'border-blue-500/30 bg-blue-950/20 text-blue-100',
        gray: 'border-gray-800 bg-gray-900/50 text-gray-300',
    }[tone] || 'border-gray-800 bg-gray-900/50 text-gray-300';
}

function StatTile({ label, value, tone = 'gray' }) {
    return (
        <div className={`rounded-xl border p-4 ${toneClasses(tone)}`}>
            <p className="text-xs uppercase tracking-wider opacity-80">{label}</p>
            <p className="mt-2 break-words text-2xl font-semibold text-white">{value}</p>
        </div>
    );
}

function EventCard({ event, onOpenTreatment }) {
    if (!event) {
        return (
            <section className="flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-gray-700 bg-gray-900/40 text-center">
                <RadioTower className="mb-4 text-gray-600" size={52} />
                <h2 className="text-xl font-semibold text-white">No new crash evidence yet</h2>
                <p className="mt-2 max-w-md text-sm text-gray-500">
                    Start monitoring, then test in The Sims 4. New crash logs will appear here.
                </p>
            </section>
        );
    }

    const summary = summarizeMonitorEvent(event.data);
    const recommendation = describeRecommendation(summary.recommendation);

    return (
        <section className={`rounded-xl border p-5 ${toneClasses(recommendation.tone)}`}>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <p className="text-xs uppercase tracking-wider opacity-80">Latest event</p>
                    <h2 className="mt-2 text-2xl font-semibold text-white">{recommendation.title}</h2>
                    <p className="mt-2 max-w-3xl text-sm opacity-90">{recommendation.body}</p>
                    <p className="mt-3 flex items-center gap-2 text-xs opacity-70">
                        <Clock size={14} />
                        {new Date(event.receivedAt).toLocaleString()}
                    </p>
                </div>
                {recommendation.primaryAction === 'open_treatment' && (
                    <button
                        onClick={onOpenTreatment}
                        className="flex w-fit items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
                    >
                        <ShieldCheck size={17} />
                        Open Treatment
                    </button>
                )}
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-4">
                <StatTile label="Changed Logs" value={summary.changedLogNames.length} tone="blue" />
                <StatTile label="Script Active" value={summary.scriptActive} tone={summary.scriptActive ? 'amber' : 'gray'} />
                <StatTile label="UI Active" value={summary.uiActive} tone={summary.uiActive ? 'amber' : 'gray'} />
                <StatTile label="Treatment Candidates" value={summary.candidateCount} tone={summary.candidateCount ? 'emerald' : 'gray'} />
            </div>

            <div className="mt-5 rounded-lg border border-black/20 bg-black/20 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider opacity-70">Changed log files</p>
                <div className="flex flex-wrap gap-2">
                    {summary.changedLogNames.map((name) => (
                        <span key={name} className="rounded-md bg-black/30 px-2 py-1 font-mono text-xs text-white/80">
                            {name}
                        </span>
                    ))}
                </div>
            </div>
        </section>
    );
}

function HistoryList({ history }) {
    if (!history.length) {
        return (
            <p className="rounded-lg border border-gray-800 bg-black/20 p-4 text-sm text-gray-500">
                This monitor run has not recorded any changed crash logs.
            </p>
        );
    }

    return (
        <div className="space-y-3">
            {history.map((event) => {
                const summary = summarizeMonitorEvent(event.data);
                const recommendation = describeRecommendation(summary.recommendation);
                return (
                    <div key={event.id} className="rounded-lg border border-gray-800 bg-black/20 p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <p className="font-medium text-white">{recommendation.title}</p>
                                <p className="mt-1 text-xs text-gray-500">
                                    {summary.changedLogNames.join(', ') || 'Crash log'} · {new Date(event.receivedAt).toLocaleTimeString()}
                                </p>
                            </div>
                            <span className="w-fit rounded-md border border-gray-700 px-2 py-1 text-xs uppercase text-gray-300">
                                {summary.recommendation.replaceAll('_', ' ')}
                            </span>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function LiveMonitor() {
    const navigate = useNavigate();
    const monitor = useLiveMonitor();
    const [showSimsPicker, setShowSimsPicker] = useState(false);
    const [showModsPicker, setShowModsPicker] = useState(false);
    const watchedCount = monitor.progress?.total || monitor.latestEvent?.data?.watched_log_count || 0;

    const openTreatment = () => {
        navigate('/treatment', {
            state: {
                simsPath: monitor.simsPath,
                modsPath: monitor.modsPath,
            },
        });
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <div className="mx-auto max-w-7xl space-y-6">
                <motion.header
                    initial={{ opacity: 0, y: -12 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"
                >
                    <div>
                        <h1 className="flex items-center gap-3 text-3xl font-bold text-white">
                            <span className="rounded-xl bg-cyan-500/15 p-2 text-cyan-300">
                                <RadioTower size={28} />
                            </span>
                            Live Monitor
                        </h1>
                        <p className="mt-2 max-w-3xl text-gray-400">
                            Manually watch for new crash logs while you test. Simanalysis stays read-only until you choose Treatment.
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <button
                            onClick={monitor.start}
                            disabled={monitor.isWatching || !monitor.simsPath.trim()}
                            className="flex h-[42px] items-center justify-center gap-2 rounded-lg bg-cyan-600 px-5 font-medium text-white transition-colors hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {monitor.isWatching ? <Loader2 className="animate-spin" size={18} /> : <RadioTower size={18} />}
                            {monitor.isWatching ? 'Watching' : 'Start'}
                        </button>
                        <button
                            onClick={monitor.stop}
                            disabled={!monitor.isWatching}
                            className="flex h-[42px] items-center justify-center gap-2 rounded-lg border border-gray-700 px-5 font-medium text-gray-200 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            <Square size={16} />
                            Stop
                        </button>
                    </div>
                </motion.header>

                <section className="glass-card min-w-0 p-5">
                    <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                        <div className="min-w-0">
                            <label className="mb-2 block text-sm font-medium text-gray-300">Sims 4 Folder</label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    value={monitor.simsPath}
                                    onChange={(event) => monitor.setSimsPath(event.target.value)}
                                    disabled={monitor.isWatching}
                                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white disabled:opacity-70"
                                />
                                <button
                                    onClick={() => setShowSimsPicker(true)}
                                    disabled={monitor.isWatching}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    title="Browse for Sims 4 folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                        <div className="min-w-0">
                            <label className="mb-2 block text-sm font-medium text-gray-300">Mods Folder</label>
                            <div className="grid grid-cols-[minmax(0,1fr)_44px] gap-2">
                                <input
                                    value={monitor.modsPath}
                                    onChange={(event) => monitor.setModsPath(event.target.value)}
                                    disabled={monitor.isWatching}
                                    placeholder="Default: Sims 4 folder / Mods"
                                    className="min-w-0 rounded-lg border border-gray-700 bg-gray-900/70 px-3 py-2 text-white placeholder:text-gray-600 disabled:opacity-70"
                                />
                                <button
                                    onClick={() => setShowModsPicker(true)}
                                    disabled={monitor.isWatching}
                                    className="flex h-[42px] w-11 items-center justify-center rounded-lg border border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                                    title="Browse for Mods folder"
                                >
                                    <FolderOpen size={18} />
                                </button>
                            </div>
                        </div>
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-3">
                        <StatTile label="Status" value={statusText(monitor.status)} tone={monitor.status === 'error' ? 'amber' : 'blue'} />
                        <StatTile label="Watched Logs" value={watchedCount} tone="gray" />
                        <StatTile label="Session Events" value={monitor.history.length} tone={monitor.history.length ? 'emerald' : 'gray'} />
                    </div>

                    <AnimatePresence>
                        {monitor.error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-sm text-red-200"
                            >
                                <AlertTriangle className="mr-2 inline" size={16} />
                                {monitor.error}
                            </motion.div>
                        )}
                        {monitor.progress && !monitor.error && (
                            <motion.div
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: -4 }}
                                className="mt-4 rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-3 text-sm text-cyan-100"
                            >
                                {monitor.progress.stage || 'Waiting'} · {monitor.progress.current || 0}/{monitor.progress.total || 0}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </section>

                <EventCard event={monitor.latestEvent} onOpenTreatment={openTreatment} />

                <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
                        <History size={20} className="text-cyan-300" />
                        Session History
                    </h2>
                    <HistoryList history={monitor.history} />
                </section>

                <section className="rounded-xl border border-gray-800 bg-gray-900/40 p-5">
                    <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold text-white">
                        <FileWarning size={20} className="text-amber-300" />
                        Safety
                    </h2>
                    <p className="max-w-3xl text-sm text-gray-400">
                        Live Monitor reads crash logs, runs Doctor, and asks Treatment for a dry-run plan. It does not create a Treatment manifest or move files.
                    </p>
                </section>

                <FilePicker
                    isOpen={showSimsPicker}
                    onClose={() => setShowSimsPicker(false)}
                    onSelect={(path) => monitor.setSimsPath(path)}
                    initialPath={monitor.simsPath}
                    selectDirectory={true}
                />
                <FilePicker
                    isOpen={showModsPicker}
                    onClose={() => setShowModsPicker(false)}
                    onSelect={(path) => monitor.setModsPath(path)}
                    initialPath={monitor.modsPath || monitor.simsPath}
                    selectDirectory={true}
                />
            </div>
        </div>
    );
}

export default LiveMonitor;
```

- [ ] **Step 2: Run web helper tests and build**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
node --test src/views/liveMonitorModel.test.js
npm run build
```

Expected: both commands PASS.

- [ ] **Step 3: Commit Task 4 and Task 5 together**

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git add web/src/views/LiveMonitor.jsx web/src/App.jsx web/src/components/Sidebar.jsx
git commit -m "feat: add Live Monitor page"
```

---

### Task 6: Run Full Focused Verification and Add Validation Note

**Files:**
- Create: `docs/superpowers/2026-06-02-live-monitoring-ui-validation.md`

- [ ] **Step 1: Run frontend checks**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/web
node --test src/views/liveMonitorModel.test.js
npm run build
```

Expected: both commands PASS.

- [ ] **Step 2: Run Rust checks**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis/src-tauri
cargo test live_monitor --lib
cargo test bridge_error_event_counts_as_terminal_output --lib
cargo test cancelled_task_does_not_emit_crash_error --lib
```

Expected: all three commands PASS.

- [ ] **Step 3: Run focused Python safety checks**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
```

Expected: both commands PASS.

- [ ] **Step 4: Run synthetic read-only monitor validation**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis
fixture="/tmp/simanalysis-live-monitor-ui-fixture"
rm -rf "$fixture"
mkdir -p "$fixture/Mods"
printf "old crash" > "$fixture/lastException.txt"
.venv/bin/simanalysis-bridge live-monitor "$fixture" --once > /tmp/simanalysis-live-monitor-ui-once.ndjson
test ! -e "$fixture/_Simanalysis_Treatment"
```

Expected: command exits 0 and `_Simanalysis_Treatment` is not created.

- [ ] **Step 5: Write validation note**

Create `docs/superpowers/2026-06-02-live-monitoring-ui-validation.md`:

```markdown
# Live Monitoring UI validation

Date: 2026-06-02
Branch: `codex/live-monitoring-ui`

## Commands

```text
cd web && node --test src/views/liveMonitorModel.test.js
cd web && npm run build
cd src-tauri && cargo test live_monitor --lib
cd src-tauri && cargo test bridge_error_event_counts_as_terminal_output --lib
cd src-tauri && cargo test cancelled_task_does_not_emit_crash_error --lib
.venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
.venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
fixture="/tmp/simanalysis-live-monitor-ui-fixture"; rm -rf "$fixture"; mkdir -p "$fixture/Mods"; printf "old crash" > "$fixture/lastException.txt"; .venv/bin/simanalysis-bridge live-monitor "$fixture" --once > /tmp/simanalysis-live-monitor-ui-once.ndjson; test ! -e "$fixture/_Simanalysis_Treatment"
```

## Results

- Frontend helper tests: PASS.
- Frontend build: PASS.
- Rust live-monitor tests: PASS.
- Rust terminal-event regression test: PASS.
- Rust cancellation regression test: PASS.
- Focused Python Live Monitoring and bridge tests: PASS.
- Focused Treatment safety tests: PASS.
- Synthetic read-only monitor validation: PASS; `_Simanalysis_Treatment` was not created.

## Notes

- The Live Monitor UI is manual start/stop.
- Route changes do not cancel the monitor because the process handle lives in `LiveMonitorContext`.
- Live Monitoring remains read-only and only opens Treatment when the backend recommendation is `open_treatment`.
```

Only write PASS for commands that actually passed. If any command fails, record the failure and fix it before writing a passing result.

- [ ] **Step 6: Commit validation**

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git add docs/superpowers/2026-06-02-live-monitoring-ui-validation.md
git commit -m "docs: validate Live Monitoring UI"
```

---

### Task 7: Final Branch Review

**Files:**
- Review all changed files.

- [ ] **Step 1: Check branch status**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git status --short --branch
git log --oneline --decorate -6
```

Expected: working tree clean; recent commits include the design, plan, and task commits.

- [ ] **Step 2: Check final diff against main**

Run:

```bash
cd /Users/gabrielfreeman/src/Simanalysis
git diff --stat github/main..HEAD
git diff --check github/main..HEAD
```

Expected: diff contains only Live Monitoring UI files, docs, and the Rust streaming transport adjustment; `git diff --check` exits 0.

- [ ] **Step 3: Confirm no unintended mutation in real Sims folder**

Run:

```bash
test ! -e "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4/_Simanalysis_Treatment"
```

Expected: command exits 0. If the folder exists from earlier manual work, inspect its timestamp and contents before making any safety claim.

- [ ] **Step 4: Prepare PR summary**

Use this summary:

```text
Adds a manual Live Monitor desktop page for the shipped live-monitor backend.

- keeps the monitor process in app-scope state so route changes do not stop it
- adds Start/Stop controls, status tiles, latest event, and current-session history
- routes `open_treatment` recommendations to the existing Treatment page
- keeps Live Monitoring read-only; monitor validation confirms no Treatment folder is created
- makes Tauri terminal-event handling stream-safe for continuous live-monitor results
```

Use this test list:

```text
- cd web && node --test src/views/liveMonitorModel.test.js
- cd web && npm run build
- cd src-tauri && cargo test live_monitor --lib
- cd src-tauri && cargo test bridge_error_event_counts_as_terminal_output --lib
- cd src-tauri && cargo test cancelled_task_does_not_emit_crash_error --lib
- .venv/bin/python -m pytest tests/unit/test_live_monitoring.py tests/unit/test_bridge_main.py tests/unit/test_bridge_commands.py -q --no-cov
- .venv/bin/python -m pytest tests/unit/test_treatment.py::test_create_plan_collects_only_active_doctor_candidates_without_writing tests/unit/test_treatment.py::test_create_plan_with_save_writes_manifest -q --no-cov
- synthetic read-only monitor fixture; confirmed `_Simanalysis_Treatment` was not created
```
