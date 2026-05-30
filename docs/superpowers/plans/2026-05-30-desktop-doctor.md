# Desktop Doctor Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or execute these tasks task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only desktop Doctor scan that runs existing script-crash and UI-crash autopsies together from the Tauri app.

**Architecture:** Keep the existing sidecar protocol. Add a Python bridge composition command, expose it through Tauri `start_analysis`, and add a React route that renders grouped findings from the combined JSON result.

**Tech Stack:** Python 3.11 local validation, package target Python 3.9+, pytest, ruff, mypy, bandit, Rust/Tauri v2, React 18, Vite.

---

## Task 1: Python Bridge Composition

**Files:**
- Modify `src/simanalysis/bridge/commands.py`
- Modify `src/simanalysis/bridge/__init__.py`
- Modify `tests/unit/test_bridge_commands.py`
- Modify `tests/unit/test_bridge_main.py`

- [ ] Write tests that `doctor-scan` emits a combined result and rejects an invalid Sims 4 directory.
- [ ] Run those tests and verify they fail before implementation.
- [ ] Implement `doctor_scan(args, emit)` by reusing `parse_exception_file`, `CrashAnalyzer`, `parse_ui_exception_file`, `UICrashAnalyzer`, and existing serialization functions.
- [ ] Add parser support for `simanalysis-bridge doctor-scan <sims4_dir> [--mods PATH] [--recursive]`.
- [ ] Run the focused bridge tests and commit.

## Task 2: Tauri + Frontend API Wiring

**Files:**
- Modify `src-tauri/src/lib.rs`
- Modify `web/src/api.js`

- [ ] Add a Rust unit test or extend existing `build_args` coverage so `doctor-scan` maps to sidecar arguments.
- [ ] Run the Rust test and verify it fails before implementation if the helper is testable.
- [ ] Add `doctor-scan` to `build_args`, forwarding `options.modsPath` when provided and `--recursive` when requested.
- [ ] Add `api.scanDoctor(sims4Path, modsPath, callbacks)` in `web/src/api.js`.
- [ ] Run focused Rust tests where available and commit.

## Task 3: React Doctor View

**Files:**
- Modify `web/src/App.jsx`
- Modify `web/src/components/Sidebar.jsx`
- Create `web/src/views/Doctor.jsx`

- [ ] Add the Doctor route and sidebar item.
- [ ] Build `Doctor.jsx` with one Sims 4 path input, one optional Mods path input, one scan button, progress/error states, grouped findings, and JSON export.
- [ ] Keep the page read-only: no move/delete/quarantine controls.
- [ ] Run `npm --prefix web run build` and commit.

## Task 4: Full Validation

**Files:**
- Create `docs/superpowers/2026-05-30-desktop-doctor-validation.md`

- [ ] Run the Python test suite.
- [ ] Run ruff, mypy, and bandit.
- [ ] Run the web build.
- [ ] Run `simanalysis-bridge doctor-scan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"` and save a temporary JSON sample outside the repo.
- [ ] Record real-log validation notes in the validation doc and commit.
- [ ] Push to `github`, open a PR, wait for CI, fix failures, and enable auto-merge or merge when green.
