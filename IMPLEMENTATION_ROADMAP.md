# Simanalysis Masterplan

**Project:** Simanalysis
**Status:** Active development, safety-first Sims Doctor foundation
**Masterplan date:** 2026-06-04
**Current shipped baseline:** Through Live Monitoring UI, PR #15

**Public v3 execution:** `docs/public-v3-workplan.md` tracks the slice plan,
`docs/simanalysis-public-v3-presentation.html` is the executive version, and
`docs/release-smoke.md` / `scripts/release_smoke.py` track the Tauri + sidecar
release smoke path. `docs/release-security.md` / `scripts/release_security.py`
track the SBOM/security/signing evidence gate.

---

## 1. Product Direction

Simanalysis is evolving from a static conflict scanner into a local Sims 4 Doctor:
a desktop tool that reads the user's Sims 4 folder, explains mod and CC risk, helps
test likely culprits, and performs only reversible actions.

The long-term ambition is an "ultimate Sims 4 modder tool", but the project should
not jump straight to cloud, AI, automatic updates, or a Rust rewrite. The correct
path is to strengthen local truth first:

1. Know what files exist.
2. Know what changed.
3. Know what resources each package contains.
4. Explain conflicts and crash evidence.
5. Stage every action.
6. Mutate only with explicit user intent.
7. Keep rollback possible.

The core operating sentence is:

> Analyze first, stage second, mutate third, rollback always.

---

## 2. Current Product State

### Shipped foundation

The following features are already part of the current product baseline and should
not be re-planned as future first-time work:

- Tauri desktop shell with a Python sidecar bridge.
- React desktop UI routes for Dashboard, Mods, Tray, Saves, Conflicts, Doctor,
  Treatment, Live Monitor, and Settings.
- DBPF package reader with Sims 4 index flag handling, resource keys, and zlib
  resource extraction.
- `.package` and `.ts4script` scanning with SHA-256 hashing.
- Resource and tuning conflict detection.
- Crash Autopsy for `lastException*.txt` script traces.
- Status-aware attribution for active, disabled, quarantined, and not-installed
  suspects.
- UI Crash Autopsy for `lastUIException*.txt` resource-key attribution.
- Desktop Doctor scan that combines script and UI evidence.
- Treatment + Auto-Bisect with dry-run planning, manifest-first moves, restore,
  outcome recording, Sims-process guard, and symlink/path guards.
- Read-only Live Monitoring backend that watches crash logs and runs Doctor plus
  Treatment planning with `save=false`.
- Live Monitoring UI with manual start/stop, event cards, Doctor review handoff,
  and Treatment handoff.

### Partially present but not complete

- Save analysis exists, but Save Protector does not yet protect launch workflows
  or bind saves to profiles.
- Update checking exists for the application itself, but not for user mods.
- Thumbnail and config services exist, but there is no full local inventory
  database.
- Conflict detection exists, but it is not yet profile-aware, patch-aware, or
  backed by scan history.
- Treatment has reversible session moves, but there is no general action engine
  for cleanup, quarantine, profile activation, or cache reset.

### Missing foundation

- Persistent local SQLite inventory.
- Scan snapshots and event log.
- General backup/quarantine/restore engine.
- Cleanup planner for duplicates, archives, misplaced files, and clutter.
- Profile manager.
- Patch Day Shield.
- Classification confidence model.
- Cache Doctor.
- Performance Doctor.
- Static script security risk scanner.
- Safe mod update staging.
- Creator Mode.
- Cloud compatibility layer.
- AI Doctor explanation layer.

---

## 3. Architecture Direction

### Current architecture to keep

The current architecture is the right base for the next stage:

```text
React/Tauri desktop UI
        |
Tauri Rust shell and sidecar process control
        |
Python simanalysis-bridge NDJSON commands
        |
Python analysis core
        |
Local Sims 4 folder
```

This keeps the app shippable and lets the existing analyzers continue to improve.
The next architectural step is not a rewrite. It is adding a durable local data
layer that all scanners, Doctor flows, Treatment flows, and future profile flows
can share.

### Next architectural addition

Add a local SQLite-backed inventory and event system:

- `files`: path identity, size, timestamps, extension, SHA-256, scan status.
- `packages`: DBPF parse status, resource count, compression flags, package-kind
  hints.
- `resources`: package resource keys and resource metadata.
- `scans`: each scan run, root folder, timing, totals, and warnings.
- `snapshots`: point-in-time file lists and hashes.
- `event_log`: scan, plan, action, restore, and user-confirmed events.

This should start read-only. Mutating features can use it only after the inventory
is stable and validated against real Sims folders.

### What not to rewrite now

- Do not rewrite the core in Rust now.
- Do not replace the existing Tauri sidecar model now.
- Do not introduce cloud as a required dependency.
- Do not make AI a core dependency.
- Do not make symlink-based profiles the default.

Rust can later be used for narrow hot paths if Python scanning becomes a measured
blocker. Until then, the product risk is local state correctness and rollback,
not raw language performance.

---

## 4. Development Tracks

### Track A: Local Truth And Snapshots

Goal: make Simanalysis know exactly what exists and what changed.

Milestones:

1. **Local Inventory + Snapshot v1**
   - Add SQLite storage for file inventory, package parse status, resources,
     scans, snapshots, and event log.
   - Keep v1 read-only.
   - Index the Sims 4 folder and Mods folder without changing files.
   - Record `first_seen`, `last_seen`, size, mtime, extension, and SHA-256.
   - Persist DBPF parse success, parse error, and resource counts.
   - Export snapshot JSON for support and validation.

2. **Changed Since Last Scan**
   - Show added, removed, moved, modified, and unchanged files.
   - Detect same hash at a new path as probable move/duplicate.
   - Surface parse regressions after updates or imports.

3. **Inventory UI**
   - Add a calm desktop view for scan history and current folder health.
   - Show totals, warnings, parse errors, largest folders, largest files, and
     changed-since-last-scan.

### Track B: Cleanup And Reversible Actions

Goal: turn file chaos into safe plans, not one-click destruction.

Milestones:

1. **Cleanup Planner v1**
   - Detect exact duplicates by SHA-256.
   - Detect `.zip`, `.rar`, `.7z`, previews, notes, shortcuts, duplicate
     Resource.cfg files, and likely misplaced Tray files.
   - Generate a plan only. Do not move files by default.
   - Explain every suggested action with a reversible destination.

2. **General Quarantine + Restore v1**
   - Extend Treatment's safety principles to a general action engine.
   - Keep manifest-first recording.
   - Refuse mutation while The Sims 4 is running.
   - Reject path escape, symlinked units, missing sources, and conflicting
     destinations.
   - Support restore by action manifest.

3. **Cache Doctor v1**
   - Treat cache reset as reversible quarantine, not delete.
   - Move cache files to a Simanalysis-owned cache quarantine folder.
   - Recommend cache reset after mod changes, patch events, UI/script crashes,
     and CC removal.

### Track C: Profiles And Patch Safety

Goal: stop treating `Mods` as one giant permanent state.

Milestones:

1. **Profile Manager Light**
   - Support Vanilla, Safe After Patch, CAS Only, Build/Buy Only, Gameplay
     Minimal, Creator Test, and Full profiles.
   - Use physical move/copy strategy in v1.
   - Keep symlink/hardlink activation as an advanced later option.
   - Require snapshot before activation.
   - Make profile activation reversible.

2. **Patch Day Shield v0**
   - Detect a changed game version or patch marker.
   - Mark script, UI, gameplay, and tuning mods as unknown-after-patch.
   - Recommend vanilla test and save-copy test.
   - Never automatically re-enable unknown mods.

3. **Patch Day Shield v1**
   - Bind patch state to profiles.
   - Add safe-after-patch workflow in the desktop UI.
   - Explain what changed since the last known game version.
   - Recommend cache reset through Cache Doctor.

### Track D: Classification, Conflicts, And Performance

Goal: improve explanations from "these files overlap" to "this is what is risky
and why".

Milestones:

1. **Classification v1**
   - Classify files as CAS, Build/Buy, gameplay tuning, UI, script, localization,
     default replacement, animation, dependency, or unknown.
   - Use DBPF resource types, file names, folder names, companion scripts, and
     known dependency hints.
   - Include confidence and signals for every classification.
   - Initial implementation is available as a conservative evidence layer in
     Doctor, Patch Day, and Update Desk; it does not mark files safe.

2. **Conflict Engine v2**
   - Improve TGI overlap grouping.
   - Distinguish exact duplicate, likely override, default replacement ambiguity,
     UI conflict, tuning conflict, and script-family mismatch.
   - Make recommendations profile-aware.
   - Avoid labeling intentional overrides as errors.
   - Initial metadata is available for exact duplicate, likely override,
     default replacement ambiguity, UI conflict, and tuning conflict cases;
     script-family mismatch remains pending a script conflict detector.

3. **Performance Doctor**
   - Analyze file count, total size, script count, package resource count,
     package size outliers, folder depth, merged packages, and profile startup
     observations.
   - Present likely performance suspects without pretending to measure what has
     not been measured.

### Track E: Saves, Tray, And User Data Protection

Goal: protect user saves and Tray items without writing to save files.

Milestones:

1. **Save Protector v1**
   - Inventory saves read-only.
   - Bind a save to a recommended mod profile.
   - Warn when required or previously active mods are missing, quarantined, or
     unknown-after-patch.
   - Offer test-copy workflow before risky play.
   - Do not edit saves.

2. **Tray Dependency Signals**
   - Estimate likely CAS/BuildBuy dependencies for Tray items using package
     classes and prior active profiles.
   - Label results as likely/probable/unknown, not guaranteed.

### Track F: Updates And Source Binding

Goal: help users update safely without becoming a piracy or scraping platform.

Milestones:

1. **Manual Source Binding v1**
   - Let users bind a local mod family to a creator URL, GitHub release, or
     CurseForge source.
   - Store source metadata locally.
   - Do not download directly to Mods.

2. **Staging Update Pipeline**
   - Download to staging.
   - Scan archive safely.
   - Reject path traversal and suspicious archives.
   - Hash staged files.
   - Parse packages and scripts before install.
   - Generate an install plan.
   - Replace only after snapshot and user approval.

3. **CurseForge/GitHub Integration**
   - Use official APIs where available.
   - Treat unsupported creator sites as manual tracking unless the user
     explicitly supplies files.
   - Do not bypass paywalls, logins, or creator distribution rules.

### Track G: Script Safety And Logs

Goal: improve diagnosis of script mods without executing mod code.

Milestones:

1. **Script Security Analyzer v1**
   - Inspect `.ts4script` as archives.
   - Reject path traversal.
   - Extract imports, namespaces, `.py` metadata, and basic `.pyc` metadata where
     safe.
   - Flag risk signals such as subprocess, sockets, network libraries, eval,
     exec, obfuscation patterns, and unexpected binaries.
   - Use "elevated risk" language, not "malware" claims.
   - Initial implementation is available in Doctor and Update Desk as static
     elevated-risk review evidence; no script code is executed.

2. **Exception Analyzer v2**
   - Expand Doctor parsing for lastCrash, MCCC, Better Exceptions, and common EA
     error-code families.
   - Preserve evidence-first explanations.
   - Feed Treatment and Live Monitoring with better structured summaries.

### Track H: Creator Mode

Goal: support creators after the player-facing safety foundation is stable.

Milestones:

1. **Package Diff**
   - Compare two packages by added, removed, and changed resource keys.
   - Highlight same TGI with changed content hash.

2. **STBL Tools**
   - Diff, export, import, and validate string tables.
   - Detect missing translations and duplicate string keys.

3. **Release Builder**
   - Build a release zip with manifest, hashes, changelog, install notes,
     dependency list, and tested game version.

### Track I: Cloud And AI

Goal: add optional intelligence only after local correctness exists.

Milestones:

1. **Cloud Compatibility Layer**
   - Opt-in anonymous compatibility reports.
   - Send hashes and game version, not local paths, save names, household names,
     usernames, private URLs, or raw logs without redaction.
   - Track creator-confirmed, manifest-confirmed, and community-reported status
     with separate trust scores.

2. **AI Doctor**
   - Use AI as an explanation and control layer over structured evidence.
   - AI may suggest actions but must not execute mutation without user approval.
   - AI may not permanently delete, bypass creator sources, run scripts, edit
     saves, or mark unknown mods safe.

---

## 5. Near-Term Milestone Plan

### Milestone 1: Local Inventory + Snapshot v1

This is the next recommended development slice.

Definition of done:

- SQLite database is created in a Simanalysis-owned app data location.
- A read-only inventory scan records files and package parse metadata.
- Scan history shows current totals and changed-since-last-scan.
- Existing scanner behavior still works without requiring the database path from
  callers.
- Desktop bridge exposes a command for inventory scan.
- Desktop UI can show current inventory summary.
- Exported JSON snapshot can be used for support and regression validation.

Acceptance criteria:

- Scanning a synthetic Sims folder creates inventory rows without moving files.
- Running the scan twice without changes reports no changes.
- Adding, removing, modifying, and moving files produces correct summary counts.
- Corrupt or unsupported packages record parse status instead of crashing.
- Real Sims folder validation is read-only.

### Milestone 2: Cleanup Planner v1

Definition of done:

- Planner consumes the inventory database and emits a cleanup plan.
- Exact duplicates are grouped by SHA-256.
- Archives in Mods are identified as inactive files needing unpack/archive
  handling.
- Misplaced non-mod files are reported.
- Plan export is JSON.
- No files are moved in v1 planning.

### Milestone 3: General Quarantine + Restore v1

Definition of done:

- Cleanup plans can be applied only after explicit user confirmation.
- Every action writes a manifest before moving files.
- Restore uses the manifest, not a fresh scan.
- The Sims 4 process guard blocks mutation.
- Symlink and path-safety tests cover apply and restore.

### Milestone 4: Profile Manager Light

Definition of done:

- Users can create, inspect, activate, and restore simple profiles.
- Activation is based on physical move/copy strategy.
- Profile activation requires a snapshot.
- Save Protector warnings can later consume profile state.

### Milestone 5: Patch Day Shield v0

Definition of done:

- Game version changes are detected or manually recorded.
- Risk classes are marked unknown-after-patch.
- UI explains the safe test flow.
- No unknown mods are automatically marked safe.

---

## 6. Safety And Policy Boundaries

These rules apply across every future track:

1. Never permanently delete user files automatically.
2. Destructive-looking actions must route through quarantine or staged restore.
3. Every Sims-folder mutation requires a snapshot or manifest.
4. Saves are not modified directly in v1.
5. Unknown compatibility is never labeled safe.
6. External downloads go to staging, never directly to Mods.
7. Paid or private creator content is never redistributed.
8. Script mods are never executed for analysis.
9. Creator pages behind auth are not scraped or bypassed.
10. Public branding must not imply EA, Maxis, or official Sims affiliation.
11. Plumbob and EA/Maxis/Sims marks are not public product branding.
12. AI recommendations must show evidence and require approval for actions.

---

## 7. Verification Standard

Every shipped slice should include:

- Focused unit tests for new pure logic.
- Integration tests for bridge commands and file-system behavior.
- Real Sims folder validation when the feature touches Doctor, Treatment, Live
  Monitoring, inventory, profiles, or snapshots.
- `ruff check`.
- `ruff format --check`.
- MyPy where the slice touches typed Python surfaces.
- Bandit before pushing or opening PRs.
- Frontend unit tests for pure view models.
- `npm run lint -- --quiet` and `npm run build` when UI changes.
- CI-log-first debugging if GitHub checks fail.

Docs-only updates may use lighter verification, but must at least run:

```bash
git diff --check
```

---

## 8. Deferred Or Later-Only Work

These are valid ideas, but not the next development focus:

- Full Rust core rewrite.
- Required cloud account or hosted database.
- AI-first repair flows.
- Automatic mod update installation.
- Symlink-based profile activation as the default.
- Save editing.
- Full malware verdicts for script mods.
- Aggressive scraping of Patreon, Tumblr, Discord, or private creator sites.
- Community compatibility reporting without a privacy/redaction model.
- Public product names or assets that imply EA/Maxis affiliation.

---

## 9. Working Process

Simanalysis development should continue with the staged flow that has worked:

1. Choose one bounded slice from this masterplan.
2. Brainstorm and approve the design.
3. Write the design spec under `docs/superpowers/specs/`.
4. Write the implementation plan under `docs/superpowers/plans/`.
5. Implement in an isolated worktree or feature branch.
6. Validate locally and, where relevant, against real Sims evidence.
7. Push a PR.
8. Inspect CI logs precisely if red.
9. Merge only after checks are green.
10. Update validation notes or this masterplan when the shipped baseline changes.

The next bounded slice should be **Local Inventory + Snapshot v1**.
