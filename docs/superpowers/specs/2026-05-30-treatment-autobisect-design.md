# Treatment + Auto-Bisect - design

**Status:** Design approved; awaiting written-spec review before implementation planning
**Date:** 2026-05-30
**Roadmap:** Sub-project #3 of the "ultimate Sims doctor" roadmap. Builds on the shipped desktop Doctor scan, Crash Autopsy, and UI Crash Autopsy by turning likely suspects into reversible test plans.

## Goal

Add an assisted Treatment + Auto-Bisect workflow that takes Doctor suspects and helps prove the culprit by safely toggling candidate mods in batches.

The app should do the mechanical work: choose a batch, move it out of active `Mods`, record exactly what changed, and narrow the candidate set after the user tests in The Sims 4 and reports the outcome. It should not pretend to prove a result without a game test.

## Why now

The desktop Doctor can already explain both script crashes and UI/freeze logs:

- script suspects from `lastException*.txt`
- UI/package suspects from `lastUIException*.txt`
- per-suspect status: active, disabled/quarantined, not installed, or unresolved

That gives Simanalysis enough evidence to propose treatment. The missing step is confirmation: "this suspect is probably involved" should become "this suspect group was tested and the issue changed."

## Scope

**In:**

- Create a treatment engine for dry-run planning, reversible batch application, restore, and outcome handling.
- Start from active Doctor findings only.
- Default bisect unit is a top-level mod folder or standalone file under `Mods`, not an individual file inside a creator folder.
- Store a durable session manifest in the Sims 4 folder once the user starts a bisect session, so every move can be audited and undone.
- Move disabled test batches into a Simanalysis-owned sibling folder named `_Disabled_Simanalysis_Bisect_<timestamp>`.
- Support three user outcomes after each game test:
  - `same_issue`: the current removed batch is probably innocent; restore it and test the other half.
  - `issue_gone`: the culprit is probably inside the removed batch; keep it out and bisect that half.
  - `different_issue`: stop automatic narrowing and mark the session as needing manual review.
- Add bridge commands so the desktop app can create a plan, apply the next step, record an outcome, restore the latest step, and summarize an active session.
- Add a desktop Treatment view linked from Doctor findings.
- Validate dry-run planning against the real Sims 4 folder and logs.

**Out:**

- Launching The Sims 4.
- Watching the Sims folder for new logs automatically.
- Deleting files.
- Permanent quarantine as a one-click action before a culprit is confirmed.
- Moving disabled/quarantined historical suspects back into active `Mods`.
- Single-file bisect inside a folder by default.
- Network lookups, mod update checks, or creator identity resolution.

## Safety Model

Treatment is the first intentionally mutating feature in the Doctor flow, so safety is the design constraint.

### Dry-run first

Every session starts with a dry-run plan. Planning is read-only by default and lists:

- Sims 4 folder
- active `Mods` folder
- candidate units
- the first proposed batch
- destination folder
- warnings and blockers

No Sims-folder write or file move happens during default planning. A manifest is written only when the user explicitly saves/starts the session, and no mod file moves until the user explicitly applies a step.

### Reversible moves

Applying a step moves whole units from `Mods` to the session disabled folder. The manifest records every source and destination path before the move. Restore operations use that manifest, not a fresh scan, so a step can be undone even if the candidate names are ambiguous.

### Sims process guard

Before any mutating command, Simanalysis checks whether The Sims 4 appears to be running. If it is running, the command refuses to move files and returns a clear error. Read-only planning remains allowed.

The process check is best effort and platform-specific. On macOS it should look for known Sims process names using `ps`. If the check cannot run, the command should refuse mutation unless a future explicit override exists. V1 does not add an override.

### Path guard

Mutating commands may only move:

- files or directories directly under the chosen `Mods` folder
- to the active session's `_Disabled_Simanalysis_Bisect_<timestamp>` folder

They must reject symlinks, paths that escape the Mods folder, missing source paths, and destinations that already exist.

### Manifest-first discipline

Before any file move, the command writes a pending step entry to the manifest. After each successful move, it updates that item as moved. If a move fails mid-step, the manifest contains enough detail to attempt repair or manual recovery.

## Candidate Selection

V1 uses Doctor output as evidence, but it treats the file system as source of truth for what can be moved.

### Eligible candidates

Eligible candidates are active findings:

- script suspects with `status == "active"` whose suspect `mod` name can be resolved to an active `.ts4script` file under `Mods`
- UI findings with `status == "active"` and at least one active package hit

Disabled, quarantined, not-installed, not-found, and no-key findings are included in the explanation but are not movable candidates.

### Unit boundaries

For each active candidate path:

1. If the file is directly under `Mods`, the unit is that file.
2. If the file is under a first-level child folder of `Mods`, the unit is that first-level folder.
3. If the path is nested deeper, the unit still stays the first-level child folder.

Script candidates resolve from the suspect `.ts4script` filename because traceback evidence paths are often creator build-machine paths rather than local disk paths. UI candidates resolve from `package_path` because UI resource hits already carry the active package path.

This matches the user's real recovery workflow: restore and rollback by creator/category batches first, not by thousands of individual CC files.

### Ranking

The first plan orders candidates by evidence strength:

1. active UI/package hits from current `lastUIException` findings
2. active script top suspects with high confidence
3. active script top suspects with medium confidence
4. active script low-confidence or secondary suspects

If multiple files map to the same unit, the unit appears once with merged evidence.

## Bisect Session State

The manifest is JSON and stored under this path after the user saves/starts a session:

```text
<sims4_dir>/_Simanalysis_Treatment/bisect-<YYYYMMDD-HHMMSS>.json
```

The disabled files for that session are stored under:

```text
<sims4_dir>/_Disabled_Simanalysis_Bisect_<YYYYMMDD-HHMMSS>/
```

### Manifest shape

```json
{
  "version": 1,
  "session_id": "bisect-20260530-123456",
  "created_at": "2026-05-30T12:34:56Z",
  "updated_at": "2026-05-30T12:34:56Z",
  "sims4_dir": "/Users/example/Documents/Electronic Arts/The Sims 4",
  "mods_dir": "/Users/example/Documents/Electronic Arts/The Sims 4/Mods",
  "disabled_dir": "/Users/example/Documents/Electronic Arts/The Sims 4/_Disabled_Simanalysis_Bisect_20260530-123456",
  "status": "planned",
  "active_candidates": [
    {
      "unit_path": "/.../Mods/CreatorPack",
      "unit_name": "CreatorPack",
      "unit_kind": "folder",
      "evidence": [
        {
          "source": "ui",
          "finding": "lastUIException.txt",
          "reason": "active package hit",
          "path": "/.../Mods/CreatorPack/menu.package"
        }
      ]
    }
  ],
  "remaining_candidates": ["/.../Mods/CreatorPack", "/.../Mods/OtherPack"],
  "current_removed": [],
  "steps": []
}
```

### Step shape

```json
{
  "step_id": 1,
  "created_at": "2026-05-30T12:40:00Z",
  "status": "applied",
  "reason": "bisect first half",
  "removed_units": [
    {
      "source": "/.../Mods/CreatorPack",
      "destination": "/.../_Disabled_Simanalysis_Bisect_20260530-123456/CreatorPack",
      "unit_kind": "folder",
      "status": "moved"
    }
  ],
  "outcome": null
}
```

## Bisect Algorithm

The algorithm is deliberately simple and auditable.

1. Start with `remaining_candidates` from the Doctor-derived plan.
2. Choose the next batch as the first half of `remaining_candidates`, rounded up.
3. Apply the step by moving that batch to the session disabled folder.
4. Wait for the user to test the game.
5. If outcome is `issue_gone`, the culprit is in the removed batch:
   - keep the removed batch disabled
   - restore any previously removed units not in that batch
   - set `remaining_candidates` to the removed batch
6. If outcome is `same_issue`, the culprit is not in the removed batch:
   - restore the removed batch
   - remove that batch from `remaining_candidates`
7. If one candidate remains, mark the session `confirmed_candidate`.
8. If zero candidates remain, mark the session `inconclusive`.
9. If outcome is `different_issue`, mark the session `manual_review` and stop automatic moves.

The UI should explain the current state in plain language, for example:

```text
Step 2 removed 4 candidate folders. Run Sims and try the same action. Then tell Simanalysis whether the same issue still happens.
```

## Commands

Add bridge commands first; a later CLI wrapper can reuse the same core service if needed.

```text
simanalysis-bridge treatment-plan <sims4_dir> [--mods PATH] [--doctor-json PATH] [--save]
simanalysis-bridge treatment-apply <manifest_path>
simanalysis-bridge treatment-outcome <manifest_path> --outcome same_issue|issue_gone|different_issue
simanalysis-bridge treatment-restore <manifest_path> [--step latest|all]
simanalysis-bridge treatment-status <manifest_path>
```

`--doctor-json` is optional. If it is omitted, `treatment-plan` runs the same Doctor analysis internally. This keeps the desktop app simple: it can pass a saved Doctor result once that path exists, but planning still works from a folder alone.

Without `--save`, `treatment-plan` is read-only and returns a proposed plan with `manifest_path: null`. With `--save`, it creates `_Simanalysis_Treatment`, writes the manifest in `planned` status, and returns the manifest path.

All commands emit the existing bridge NDJSON event shape.

## Desktop UI

Add a Treatment view to the desktop app:

- available from the sidebar as `Treatment`
- linked from Doctor active findings
- shows the active Sims 4 folder and candidate count
- shows dry-run plan warnings before any move
- has one primary action at a time:
  - `Create Plan`
  - `Start Session`
  - `Apply Step`
  - `Record Result`
  - `Restore Latest Step`
- requires an explicit confirmation before any move
- displays the exact files/folders that will move
- never labels a candidate as "confirmed" until the bisect result narrows to one candidate

The UI should stay operational and compact. It is a work surface, not a landing page.

## Error Handling

- Missing Sims folder: fail before planning.
- Missing Mods folder: plan returns no movable candidates and explains why.
- No active Doctor suspects: plan returns an empty candidate list and no mutation actions.
- Apply without a saved manifest: refuse and ask the user to start the session first.
- Sims running during mutation: refuse apply/restore/outcome moves.
- Manifest missing or malformed: refuse mutation and show the parse error.
- Source path missing during apply: mark the step blocked and do not continue with later moves.
- Destination exists: block the move to avoid overwriting user data.
- Restore destination already exists in `Mods`: block restore for that unit and report it clearly.

## Testing

- Unit-test candidate extraction from synthetic Doctor JSON.
- Unit-test unit boundary selection for direct files, first-level folders, and nested files.
- Unit-test dry-run planning with active, disabled, not-installed, not-found, and no-key findings.
- Unit-test that planning without `--save` does not create `_Simanalysis_Treatment`.
- Unit-test path guards reject symlinks, path escapes, and destination collisions.
- Unit-test manifest write/update behavior for planned, applied, restored, confirmed, inconclusive, and manual-review sessions.
- Unit-test bisect outcome transitions.
- Unit-test bridge parser and command output shape.
- Unit-test Tauri argument construction for treatment commands.
- Build the desktop frontend to verify the new route compiles.
- Run Bandit locally before pushing.
- Validate against the real Sims 4 folder using dry-run planning and record the candidate summary in `docs/superpowers/2026-05-30-treatment-autobisect-validation.md`.

## Validation Plan

Real-folder validation should be dry-run by default:

```text
simanalysis-bridge treatment-plan "/Users/gabrielfreeman/Documents/Electronic Arts/The Sims 4"
```

Expected validation evidence:

- command emits valid NDJSON
- no files move
- disabled/quarantined Doctor findings are not treated as movable candidates
- any active candidates are grouped by top-level folder/file
- warnings and blockers are understandable

If live mutation validation is needed, it should be limited to a tiny synthetic Sims 4 fixture under `/tmp`, not the user's real mod stack. Mutating the real Sims folder should only happen when the user explicitly asks to run a bisect step.

## Later Work

- Permanent quarantine command after a candidate is confirmed.
- Live Monitoring integration so the app can suggest outcome from new logs.
- Optional single-file refinement inside a confirmed folder.
- CLI wrappers for users who do not run the desktop app.
- Smarter grouping by creator metadata once mod identity is reliable.
