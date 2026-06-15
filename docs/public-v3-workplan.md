# Simanalysis Public v3 Workplan

**Last updated:** 2026-06-15

**Baseline:** `main` at `3661967` / PR #58 merged

**Companion presentation:** [`simanalysis-public-v3-presentation.html`](simanalysis-public-v3-presentation.html)

## Purpose

This workplan turns the Public v3 roadmap into a slice-by-slice execution plan.
It is the working surface for getting Simanalysis from the current safety-first
foundation to an honest Public v3 release.

Simanalysis is not production-ready yet. The current product has local truth,
the SQLite inventory ledger, Doctor, Treatment/Auto-Bisect, Operating Table,
Patch Day Shield, Profile Manager Light, Cache Doctor, Save Protector, Tray
Protector, and Update Desk backend/CLI/bridge foundations. The remaining Public
v3 work is about closing the mutating workflows, keeping every file operation
reversible, polishing trust surfaces, and packaging a release that matches the
actual shipped behavior.

## Source Of Truth

- Product direction: [`../IMPLEMENTATION_ROADMAP.md`](../IMPLEMENTATION_ROADMAP.md)
- Current implementation status: [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md)
- Status index: [`STATUS.md`](STATUS.md)
- Release-oriented changes: [`../CHANGELOG.md`](../CHANGELOG.md)
- Executive presentation: [`simanalysis-public-v3-presentation.html`](simanalysis-public-v3-presentation.html)

## How To Work This Plan

- Use one branch per slice, with the `codex/` prefix unless a maintainer asks
  for another branch name.
- Keep PRs small. A slice should be reviewable as one product gate, not a broad
  roadmap batch.
- Prefer read-only surfaces first, then manifest-backed mutation, then desktop
  controls.
- Never mutate Sims files without a snapshot or manifest, explicit user intent,
  path/symlink/collision guards, and The Sims 4 process guard.
- Never permanently delete user files as part of v3 work. Use quarantine,
  staging, restore, or undo.
- Keep desktop claims honest: no UI should imply install/apply/restore support
  until the backend, bridge, Tauri args, web API, UI state, tests, and browser
  QA all exist.
- Run the relevant local gate before opening each PR. Inspect CI logs precisely
  if a check fails. Merge only after checks are green.

## Priority Levels

- **P0 Public v3 gates:** required before Public v3 release.
- **P1 Trust polish:** should complete before broad non-developer testing.
- **P2 Product intelligence:** begin after v3 safety workflows are stable.
- **P3 Later tracks:** valid roadmap items after player-facing local correctness
  is proven.

## P0 Public v3 Gates

### Slice 1: Desktop Update Desk Commit/Undo Controls

**Goal:** Let desktop users apply and undo explicit loose-file update actions
through the existing guarded Update Desk backend.

**Deliverable:** Update Desk desktop route with explicit action selection,
confirm-gated commit, undo/status refresh, visible manifest/result states, and
clear refusal messaging.

**Affected surfaces:** Update Desk React route, web API wrappers/view-models,
Tauri command args, bridge command contract, docs/status notes.

**Safety requirements:**

- No implicit `--all-actions` path from desktop.
- User must select action rows or explicitly choose an all-actions UI control
  with confirmation copy that names copy-only loose `.package`/`.ts4script`
  scope.
- Desktop must preserve the backend rule that staged downloads stay in place.
- Desktop must show backend refusal states for stale plan evidence, symlinks,
  path escapes, destination collisions, game-running guard, and modified files
  on undo.

**Test requirements:**

- Web model tests for selected action payloads, disabled commit states, undo
  state, and refusal rendering.
- Tauri arg tests for commit/undo arguments.
- Bridge unit tests for desktop command payloads.
- Browser QA on desktop and narrow viewport with no horizontal overflow.

**PR/merge gate:** Full local Python, Rust/Tauri, web, lint/build gate plus
green GitHub CI.

**Done when:** Desktop can safely call `update-staging-commit` and
`update-staging-undo` for explicit loose-file actions, and the route still does
not expose archive extraction or overwrite behavior.

### Slice 2: Safe ZIP Archive Install Planning

**Goal:** Move ZIP archives from review-only blockers to safe install planning
without extracting directly into Mods.

**Deliverable:** Update Desk plan output can represent safe ZIP member copy
actions into a staging/extracted-review area, while `.rar` and `.7z` remain
unsupported/review-only unless a safe engine is intentionally added.

**Affected surfaces:** Update Desk planner/backend, CLI JSON/text output,
bridge payloads, web API models, desktop preview rows, fixtures/tests, status
docs.

**Safety requirements:**

- ZIP extraction must never target Mods directly.
- Reject or block archive members with absolute paths, `..` path traversal,
  duplicate casefold destinations, directory/symlink-like entries, unsupported
  file types, corrupt ZIPs, and destination collisions.
- Archive install planning must still require snapshot-backed approval before
  any later mutation.
- `.rar` and `.7z` must stay explicitly unsupported/review-only in Public v3
  until a safe, tested extraction engine is chosen.

**Test requirements:**

- Unit tests for safe ZIP package/script members.
- Unit tests for corrupt ZIP, path escape, absolute paths, duplicate members,
  unsupported entries, and destination collisions.
- CLI/bridge/web model tests for archive-review versus planned-copy rows.
- Real-corpus gate unchanged.

**PR/merge gate:** Full backend gate and any affected web/Tauri gate. CI green.

**Done when:** A ZIP can produce safe planned actions without extracting to Mods,
and unsafe archives stay blockers with evidence.

### Slice 3: Update Desk Crash And Property Hardening

**Goal:** Prove Update Desk plan/commit/undo invariants under interrupted and
adversarial filesystem states.

**Deliverable:** Broader tests and small backend fixes for manifest states,
partial copy recovery, stale evidence, undo refusal, and no-overwrite/no-delete
guarantees.

**Affected surfaces:** Update Desk backend tests, bridge tests, Tauri arg tests,
web model tests where result shapes are exposed.

**Safety requirements:**

- Commit must refuse stale size/hash evidence.
- Undo must refuse modified installed files.
- Interrupted `copying` states may be recovered only when destination evidence
  still matches the planned installed file.
- No action may overwrite existing Mods files or delete staged downloads.

**Test requirements:**

- Temp-tree tests for interrupted manifests, partial copies, stale plan files,
  changed source, changed destination, duplicate action IDs, and missing action
  IDs.
- Property/fuzz-like tests for path normalization and action selection
  invariants.
- Regression tests for all bridge/Tauri/web payload assumptions touched by the
  hardening.

**PR/merge gate:** Full local gate and CI green.

**Done when:** Update Desk has explicit tests for happy paths, refusal paths,
  and crash-recovery paths across backend and desktop-facing contracts.

## P1 Trust Polish

### Slice 4: Cache Doctor Reversible Cleanup

**Goal:** Turn Cache Doctor from read-only status into a reversible cache reset
workflow.

**Deliverable:** Cache reset plan, manifest-backed quarantine/apply, restore,
and desktop controls.

**Affected surfaces:** Cache Doctor backend, Operating Table-style action
engine reuse, CLI/bridge/Tauri/web API, Cache Doctor route, docs.

**Safety requirements:**

- Cache reset must quarantine, not delete.
- Apply and restore must be manifest-based and blocked while The Sims 4 runs.
- Symlinked cache targets and path escapes remain hard refusals.

**Test requirements:** Unit/temp-tree tests for plan/apply/restore, process
guard, symlink refusal, no permanent delete, and desktop model states.

**PR/merge gate:** Full backend, Tauri, web, browser QA, CI green.

**Done when:** A user can quarantine and restore supported cache targets with a
recorded manifest and no permanent deletion.

**Implementation note:** This slice now has backend/CLI, bridge/Tauri/web API,
desktop controls, and docs coverage on the current development branch. Merge
still requires the full local gate, browser QA, and CI green.

### Slice 5: Patch Day Profile Workflow

**Goal:** Bind Patch Day state to Profile Manager Light and guide safe
post-patch testing.

**Deliverable:** Desktop workflow that shows game-version state, active profile,
unknown-after-patch classes, recommended safe-after-patch profile action, and
Cache Doctor recommendation.

**Affected surfaces:** Patch Day backend/view model, Settings/Profile Manager
state, Cache Doctor recommendation display, desktop route, docs.

**Safety requirements:**

- No automatic re-enable of unknown mods.
- Profile recommendations must be guidance unless a later manifest-backed
  profile operation exists.
- Recording a baseline still writes only Simanalysis state.

**Test requirements:** Patch-state/profile-state unit tests, desktop view-model
tests, browser QA for empty/missing/changed/unchanged states.

**PR/merge gate:** Full affected local gate and CI green.

**Done when:** Desktop can explain what changed after a patch and recommend a
safe test path without changing Mods automatically.

**Implementation note:** This slice now has desktop view-model and route
coverage on the current development branch. Merge still requires the full
affected local gate, browser QA, and CI green.

### Slice 6: Save Protector v1

**Goal:** Make Save Protector give launch guidance using available profile and
patch evidence while keeping saves read-only.

**Deliverable:** Save status includes profile-linked warnings when evidence is
available, unknown-after-patch warnings, and test-copy recommendations.

**Affected surfaces:** Save Protector backend, CLI/bridge/Tauri/web payloads,
desktop Save Protector route, tests, docs.

**Safety requirements:**

- Do not edit, rewrite, restore, dedupe, or delete save files.
- Recommendations must say "likely", "missing evidence", or "unknown" when
  profile linkage is incomplete.
- Any test-copy workflow remains future work unless manifest-backed in this
  slice.

**Test requirements:** Unit tests for read-only save groups, profile evidence
present/missing, patch state present/missing, iCloud/AppleDouble/symlink
signals, and desktop rendering.

**PR/merge gate:** Full affected local gate and CI green.

**Done when:** Save Protector gives actionable read-only launch guidance without
claiming guaranteed save compatibility.

**Implementation note:** Completed in the desktop Save Protector route by
combining existing read-only save status with Profile Manager Light config and
Patch Day status evidence. The shipped workflow labels active-profile match,
missing evidence, unknown-after-patch risk, and manual save-copy testing
recommendations; it still does not edit saves or create test copies.

### Slice 7: Tray Dependency Signals

**Goal:** Add cautious dependency signals for Tray items without pretending the
match is guaranteed.

**Deliverable:** Tray Protector reports likely/probable/unknown CAS and
Build/Buy dependency signals from available package classifications and prior
profile evidence.

**Affected surfaces:** Tray Protector backend, classification inputs if already
available, CLI/bridge/Tauri/web payloads, desktop Tray Protector route, tests,
docs.

**Safety requirements:**

- Dependency signals must be confidence-labeled.
- Do not edit Tray files.
- Do not claim missing dependencies as certain unless evidence is exact.

**Test requirements:** Unit tests for anchored groups, sidecar-only groups,
unknown evidence, likely/probable dependency labels, and desktop rendering.

**PR/merge gate:** Full affected local gate and CI green.

**Done when:** Tray Protector can explain sidecar-only, missing anchor, and
likely dependency states with calibrated uncertainty.

**Implementation note:** Completed with read-only dependency-scope signals on
Tray groups and top-level signals. Signals carry confidence, dependency kind,
anchor state, and evidence for likely CAS, likely Build/Buy, probable
sidecar-without-anchor, and unknown states. This slice does not perform package
classification or guarantee that a dependency is present or missing.

## P2 Product Intelligence

### Slice 8: Classification v1

**Goal:** Add reusable, evidence-labeled file classification.

**Deliverable:** Classifier that labels files as CAS, Build/Buy, gameplay
tuning, UI, script, localization, default replacement, animation, dependency,
or unknown with confidence and signals.

**Affected surfaces:** Analysis core, inventory/Doctor/Patch Day/Update Desk
consumers, CLI/JSON payloads, desktop display where used, tests, docs.

**Safety requirements:**

- Unknown must remain unknown; classification cannot mark post-patch mods safe.
- Signals must be visible enough for Doctor and desktop explanations.
- No script execution.

**Test requirements:** Unit tests for DBPF resource signals, filename/folder
signals, script signals, unknown fallback, confidence ordering, and consumer
payload stability.

**PR/merge gate:** Full backend gate plus affected UI gates. CI green.

**Done when:** Patch Day, Doctor, and Update Desk can consume classification
without overriding safety boundaries.

**Implementation note:** Initial Classification v1 is in place as a conservative
evidence layer over verified DBPF resource types, `.ts4script` extension
evidence, and weak path/name hints. Doctor payloads include
`classification_summary`, Patch Day can include the same summary when a Mods
path is supplied, and Update Desk staged items/actions include per-file
classification. Unknown remains unknown, classification does not mark anything
safe after a patch, and script files are never executed.

### Slice 9: Conflict Engine v2

**Goal:** Improve conflict explanation from raw overlap to user-actionable risk.

**Deliverable:** Conflict grouping distinguishes exact duplicate, likely
override, default replacement ambiguity, UI conflict, tuning conflict, and
script-family mismatch.

**Affected surfaces:** Conflict detectors/analyzers, JSON report output,
desktop Conflicts route, Doctor recommendations, tests, docs.

**Safety requirements:**

- Intentional overrides should not be labeled as errors without evidence.
- Recommendations should account for profile and classification when available.
- Existing export consumers must retain stable enough fields or receive a
  documented additive payload.

**Test requirements:** Detector tests for each conflict kind, report JSON tests,
desktop model tests, and regression tests for existing conflict fixtures.

**PR/merge gate:** Full backend/web gate and CI green.

**Done when:** Users can tell whether an overlap is duplicate, likely
intentional, ambiguous, or risky.

**Implementation note:** Initial Conflict Engine v2 metadata is in place for
existing resource, hash-duplicate, and tuning conflict detectors. Conflict
details now include `conflict_kind`, `review_status`, and profile-aware
`recommendation` guidance for exact duplicates, likely overrides, default
replacement ambiguity, UI conflicts, and tuning conflicts without changing
legacy conflict type/severity fields. Script-family mismatch now has a
read-only detector for shared `.ts4script` namespace families; it skips
identical-hash duplicates, sets `executes_code: false`, and recommends
profile-aware compatibility review without making malware claims.

### Slice 10: Script Security Analyzer v1

**Goal:** Add static script-risk signals for `.ts4script` files without running
mod code.

**Deliverable:** Analyzer inspects script archives for imports, namespaces,
basic metadata, obfuscation hints, unexpected binaries, and elevated-risk API
usage.

**Affected surfaces:** Script parser/analyzer, Doctor, Update Desk, CLI/JSON
payloads, desktop risk panels, tests, docs.

**Safety requirements:**

- Never execute `.py`, `.pyc`, or package code.
- Use "elevated risk" language, not malware verdicts.
- Reject archive path traversal.

**Test requirements:** Fixture archives for safe script, network/subprocess
signals, eval/exec, unexpected binaries, obfuscation hints, corrupt archives,
and traversal entries.

**PR/merge gate:** Full backend gate and affected UI gates. CI green.

**Done when:** Doctor and Update Desk can show script risk signals without
making unsupported security claims.

**Implementation note:** Static Script Security Analyzer v1 is in place through
`src/simanalysis/script_security.py`. It inspects `.ts4script` ZIP metadata and
Python source text for network imports, subprocess imports/calls, dynamic
execution APIs, obfuscation hints, unexpected native/binary files, corrupt
archives, and archive path traversal. Doctor exposes `script_security_summary`,
Update Desk staged items/actions expose `script_security`, and all payloads
state that no script code is executed. These are elevated-risk review signals,
not malware verdicts.

## P3 Later Tracks

### Slice 11: Packaging And Install Smoke

**Goal:** Prove Public v3 can be built and started from a clean checkout.

**Deliverable:** Release build runbook plus smoke-test harness/checklist for
desktop startup, sidecar execution, scan, Doctor, and Update Desk preview.

**Affected surfaces:** Build scripts, release docs, CI/release notes if needed.

**Safety requirements:** Smoke tests must use temp or explicitly chosen Sims
fixtures, not uncontrolled live mutation.

**Test requirements:** Clean-checkout build, desktop launch, sidecar command
smoke, and first-run profile smoke.

**PR/merge gate:** Release candidate build artifacts verified and CI green.

**Done when:** A fresh checkout can build an app that starts and runs core
read-only workflows.

**Implementation note:** The Public v3 packaging path now has a Tauri-first
release smoke harness (`python scripts/release_smoke.py --mode audit|source|full`)
and [`release-smoke.md`](release-smoke.md). The old standalone PyInstaller
build guide has been replaced with the Tauri + sidecar flow; final release still
requires the full smoke on a clean checkout plus Slice 12 signing/SBOM.

### Slice 12: Security, SBOM, Signing

**Goal:** Prepare release artifacts for responsible distribution.

**Deliverable:** SBOM, dependency security checks, signing/notarization notes,
and release security checklist.

**Affected surfaces:** Release docs, dependency audit tooling, build pipeline,
packaging scripts as needed.

**Safety requirements:** Do not claim signed/notarized distribution until the
actual artifact is signed/notarized.

**Test requirements:** Python, Rust, and web dependency checks; generated SBOM
inspection; signed artifact verification where applicable.

**PR/merge gate:** Security checks documented and green or explicitly blocked.

**Done when:** Release artifacts can be distributed without normal users needing
developer bypass steps.

**Implementation note:** The release security surface now has
[`release-security.md`](release-security.md) and
`python scripts/release_security.py --mode sbom|check|full`. The gate generates
CycloneDX SBOM files, runs Bandit, `pip-audit`, root/web npm production audits,
and Cargo lock metadata resolution. It can now also inspect built release
artifacts with `--artifact` and strict signing/notarization verification, writing
`release-artifact-status.json`. It verifies macOS `.app` bundles with
`codesign`/`stapler` and Windows `.exe`/`.msi` artifacts with Authenticode.
Signing/notarization statuses remain explicitly pending until real platform
evidence exists and strict artifact verification passes.

### Slice 13: Honest Docs Release Pass

**Goal:** Make public docs match the product that actually shipped.

**Deliverable:** Updated README, changelog, implementation status, presentation,
and release notes.

**Affected surfaces:** README, CHANGELOG, implementation/status docs, release
docs, presentation.

**Safety requirements:**

- Do not describe Simanalysis as generally production-ready unless all Public
  v3 gates are actually done.
- Public branding must not imply EA, Maxis, or official Sims affiliation.
- Claims about install/apply/restore must match desktop and CLI behavior.

**Test requirements:** Link checks where practical, `git diff --check`, docs
review against current implementation, and smoke verification of commands
mentioned in README/release notes.

**PR/merge gate:** Docs reviewed after final release candidate behavior is
known.

**Done when:** Public docs, changelog, status docs, and presentation describe
the same shipped surface.

**Implementation note:** The public docs pass now replaces the old README
product claims with a source-install, Public v3 development status, shipped
surface, limitation, release-gate, and not-EA/Maxis-affiliated summary. Status
docs and the presentation are aligned with the completed Update Desk, trust,
intelligence, smoke, and SBOM/security slices while keeping signing,
notarization, safe archive installation, and profile-aware re-enable workflows
explicitly pending.

## Standard Verification Gates

### Backend gate

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src
COVERAGE_FILE=/tmp/simanalysis-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-full.coverage .venv/bin/python -m pytest -q
```

### Tauri gate

```bash
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --lib
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
```

### Web gate

```bash
cd web
node --test src/*.test.js src/views/*.test.js
npm run lint
npm run build
```

### Desktop QA gate

- Open the affected desktop route.
- Verify the route at desktop width.
- Verify a narrow/mobile-width viewport.
- Confirm no horizontal overflow.
- Confirm loading, empty, warning/refusal, success, and undo/restore states
  where applicable.

### Mutating workflow gate

- Use temp-tree fixtures by default.
- Cover apply, undo, restore, interrupted operation, stale evidence, collision,
  symlink, path escape, process guard, no overwrite, and no permanent delete.
- Run a real-folder validation only when it is explicitly read-only or the user
  has chosen the exact live probe.

## Active Assumptions

- Public v3 remains local-first. Cloud, AI, and community compatibility are
  later optional layers.
- ZIP is the only archive format eligible for near-term safe install planning.
  `.rar` and `.7z` stay unsupported/review-only unless a later slice chooses
  and tests a safe extraction engine.
- Profile-aware operations use physical move/copy/quarantine strategies first.
  Symlink or hardlink activation is later/advanced.
- The HTML presentation stays as the executive report companion to this
  workplan.
- Release is blocked until docs, app behavior, changelog, and status files tell
  the same truth.
