# Operating Table v1 - design

**Status:** Implemented backend/API slice; visual cleanup route pending separate design
**Date:** 2026-06-12
**Roadmap:** Track B, General Quarantine + Restore v1. Builds on Cleanup Planner v1 by turning review-only cleanup actions into a manifest-first, undoable quarantine workflow.

## Goal

Add the first general reversible action engine for Simanalysis. The engine should consume a Cleanup Planner v1 JSON plan, let a caller explicitly choose which proposed actions to stage, write a durable operation manifest, then apply or restore those staged moves through strict safety guards.

The feature is named "Operating Table" because every mutation should feel like careful, journaled surgery: no silent changes, no deletion, no touching the live folder while the game is running, and no restore based on a fresh scan when a manifest already records the truth.

## Why Now

Cleanup Planner v1 can already identify low-risk Mods-folder clutter and emit proposed destinations, but it cannot act. Treatment + Auto-Bisect already proves the core safety pattern for a specific workflow: process guard, manifest-first writes, path guards, status transitions, partial-progress recovery, and restore from manifest.

Operating Table v1 generalizes those safety principles without widening the product into one-click fixing. It is the bridge from "review this action" to "stage, apply, and undo this exact action."

## Scope

**In:**

- Consume an exported or in-memory Cleanup Planner v1 plan.
- Stage only explicitly selected cleanup actions, or all actions only when the caller uses an explicit "all actions" option.
- Write an operation manifest before any file move.
- Move files from `Mods` into the plan's Simanalysis-owned `_Simanalysis_Cleanup/...` destinations.
- Restore moved files back to their original `Mods` paths from the manifest.
- Block every mutating command while The Sims 4 is running.
- Reject path escape, symlinked sources, missing sources, destination collisions, restore collisions, malformed manifests, unsupported plan versions, and source files that no longer match plan evidence.
- Preserve enough manifest state to resume or restore after a partial failure.
- Expose bridge commands first so the desktop app can call the workflow later.

**Out:**

- Deleting files.
- Permanent quarantine or "fix all" language.
- Acting on Doctor/Treatment candidates.
- Moving folders or arbitrary paths outside Cleanup Planner v1 action sources.
- Cache Doctor, profile activation, patch-day workflows, or update staging.
- Desktop visual route work.
- Network lookups or creator/update metadata.
- Automatically rescanning inventory before mutation.

## User Flow

1. Run `inventory-scan`.
2. Run `cleanup-plan` and review the returned findings.
3. Stage a subset of action IDs into an Operating Table manifest.
4. Apply the manifest after explicit confirmation.
5. Review the result or restore the manifest later.

Planning remains read-only. Staging writes only a Simanalysis manifest. Applying and restoring are the only mutating operations.

## Architecture

Add a new Python service module at `src/simanalysis/operating_table.py`.

Core units:

- `OperatingTable`: orchestrates stage, apply, restore, and status operations.
- `OperationManifest`: JSON-serializable session state with version, operation id, source plan metadata, selected actions, status, warnings, blockers, and timestamps.
- `OperationAction`: one staged move with original relative path, absolute source path, relative destination, absolute destination path, action kind, evidence, and status.
- Path guard helpers shared with or adapted from `treatment.py`.
- Process guard shared with `treatment.assert_sims_not_running()` unless it is extracted into a common safety module.

The first implementation should not require the inventory database at apply time. The cleanup plan is the evidence contract; the live filesystem is checked only to verify that each selected source still exists and still matches the evidence recorded in the plan.

## Cleanup Plan Mapping

Cleanup Planner v1 stores action rows under each finding. Operating Table staging should flatten those findings into manifest actions while preserving the parent finding context:

- `action_id`, `kind`, `source_relative_path`, `proposed_destination`, and `reason` come from the selected action.
- `finding_id` comes from the parent finding.
- `expected.sha256` and `expected.size` come from the parent finding evidence.
- For exact duplicates, the parent finding evidence applies to every action in that duplicate group; the staged action should also preserve `keep_candidate` when present.
- For single-file review findings, parent evidence must name the same path as the action's `source_relative_path`.

If a selected action cannot be tied back to exactly one parent finding, staging fails before writing a manifest.

## Manifest Location

Manifests live inside the selected Sims 4 folder under a Simanalysis-owned directory:

```text
<sims4_dir>/_Simanalysis_Cleanup/manifests/<operation_id>.json
```

Moved files use the destinations from the cleanup plan, resolved under the same Sims 4 root:

```text
<sims4_dir>/_Simanalysis_Cleanup/<plan_id>/<bucket>/<relative_path>
```

If a selected action's proposed destination is missing, absolute, outside the Sims 4 root, outside `_Simanalysis_Cleanup`, or collides with an existing file, staging or apply must fail before moving anything.

## Manifest Shape

```json
{
  "version": 1,
  "operation_id": "cleanup-op-20260612-101530",
  "created_at": "2026-06-12T10:15:30Z",
  "updated_at": "2026-06-12T10:15:30Z",
  "root_path": "/Users/example/Documents/Electronic Arts/The Sims 4",
  "mods_path": "/Users/example/Documents/Electronic Arts/The Sims 4/Mods",
  "source_plan": {
    "version": 1,
    "plan_id": "cleanup-20260612-101400",
    "scan_id": 42,
    "created_at": "2026-06-12T10:14:00Z"
  },
  "manifest_path": "/.../_Simanalysis_Cleanup/manifests/cleanup-op-20260612-101530.json",
  "status": "planned",
  "actions": [
    {
      "action_id": "duplicate:1",
      "finding_id": "duplicate:sha256:abc123",
      "kind": "review_duplicate",
      "source_relative_path": "Mods/B/item.package",
      "destination_relative_path": "_Simanalysis_Cleanup/cleanup-20260612-101400/duplicates/Mods/B/item.package",
      "source_path": "/.../Mods/B/item.package",
      "destination_path": "/.../_Simanalysis_Cleanup/cleanup-20260612-101400/duplicates/Mods/B/item.package",
      "reason": "Exact duplicate of Mods/A/item.package",
      "expected": {
        "sha256": "abc123",
        "size": 12345
      },
      "status": "pending",
      "error": null
    }
  ],
  "warnings": [],
  "blockers": []
}
```

Valid manifest statuses:

- `planned`: manifest written, no moves applied yet.
- `applying`: an apply operation is in progress.
- `applied`: every staged action moved successfully.
- `partial`: at least one action moved, but a later action blocked.
- `blocked`: no safe mutation can continue until the manifest or filesystem is reviewed.
- `restoring`: a restore operation is in progress.
- `restored`: every moved action was restored.

Valid action statuses:

- `pending`
- `moving`
- `moved`
- `restore_pending`
- `restoring`
- `restored`
- `blocked`

## Staging Rules

Staging takes a Cleanup Planner v1 plan plus selected action IDs.

It must:

- require `plan.version == 1`
- require the selected Sims 4 root to match `plan.root_path`
- reject implicit "all" behavior unless the caller uses an explicit all-actions flag
- reject unknown action IDs
- reject duplicate action IDs
- reject action kinds outside Cleanup Planner v1 review kinds
- resolve every source relative path under `<sims4_dir>/Mods`
- resolve every proposed destination under `<sims4_dir>/_Simanalysis_Cleanup`
- reject source paths containing symlinked path segments
- reject destination paths whose existing ancestor chain contains symlinked path segments
- record expected `sha256` and `size` when the plan evidence contains them
- write the manifest atomically before any apply command can run

Staging may create `_Simanalysis_Cleanup/manifests` to store the manifest. It must not create action destination directories or move source files.

## Apply Rules

Apply takes a manifest path, not a fresh plan.

Before moving, it must:

- load and validate the manifest
- run the Sims process guard
- refuse to apply a restored or already-applied manifest unless a future resume mode is explicitly designed
- verify each pending source exists
- verify source size and SHA-256 when expected evidence is present
- verify each destination does not exist
- verify every source remains under `Mods`
- verify every destination remains under `_Simanalysis_Cleanup`
- preflight every pending action before the first move, so predictable blockers do not create partial operations

During apply:

1. Mark the manifest `applying`.
2. Re-run the same preflight checks immediately before each individual move because the filesystem can change after the initial preflight.
3. For each action, write `moving` before calling `shutil.move`.
4. Move the source file to the destination, creating only the destination parent directories needed for selected actions.
5. Mark the action `moved` immediately after a successful move.
6. Save the manifest after every status transition.
7. Mark the manifest `applied` only when all actions are moved.

If initial preflight fails, no source file moves. If a later per-action check or move fails after earlier actions moved, the manifest status becomes `partial`, the blocked action records its error, and restore can use the manifest to undo moved actions.

## Restore Rules

Restore takes a manifest path and restores all actions with `moved`, `moving`, or `restore_pending` status.

Before restoring, it must:

- run the Sims process guard
- reject restore destination collisions at original source paths
- reject missing quarantine sources unless the action status shows the original source already exists and the move never completed
- reject source paths and existing destination ancestors that contain symlinked path segments
- use only manifest paths, not a fresh scan or regenerated cleanup plan

During restore:

1. Mark the manifest `restoring`.
2. Process moved actions in reverse order.
3. Mark each action `restoring` before moving it back.
4. Move the file back to its original source path.
5. Mark the action `restored`.
6. Save the manifest after every status transition.
7. Mark the manifest `restored` only when no moved actions remain.

If restore blocks midway, keep already-restored actions marked `restored`, keep remaining moved actions visible, and mark the manifest `blocked`.

## Bridge Commands

Add bridge commands first:

```text
simanalysis-bridge cleanup-stage <sims4_dir> --plan PATH [--action ACTION_ID ... | --all-actions]
simanalysis-bridge cleanup-apply <manifest_path>
simanalysis-bridge cleanup-restore <manifest_path>
simanalysis-bridge cleanup-status <manifest_path>
```

Behavior:

- `cleanup-stage` emits the manifest and writes it atomically.
- `cleanup-apply` and `cleanup-restore` emit the updated manifest.
- `cleanup-status` is read-only.
- All commands emit the existing bridge `start`, `result`, and `done` NDJSON events.
- Errors must be readable and must not hide a partially written manifest path when one exists.

Tauri and web wrappers can be thin argument builders in the same implementation slice if backend behavior is complete first. The visual route remains a later design.

## Safety Model

Operating Table v1 may write only:

- the operation manifest
- parent directories required under `_Simanalysis_Cleanup` for selected moved files
- the moved files themselves

It must never:

- delete a file
- overwrite a destination
- mutate while The Sims 4 is running
- move a source outside `Mods`
- move into a destination outside `_Simanalysis_Cleanup`
- follow symlinks
- infer user approval from plan generation
- regenerate actions from a changed scan during restore

Language should stay conservative: `stage`, `apply`, `restore`, `review`, and `quarantine`. Avoid `delete`, `clean automatically`, `fix all`, or `safe to remove`.

## Error Handling

- Missing Sims folder: staging fails.
- Missing plan file: staging fails.
- Malformed plan JSON: staging fails with a readable message.
- Unsupported plan or manifest version: fail before mutation.
- Unknown or duplicate selected action IDs: staging fails.
- No selected actions: staging fails with a message asking the caller to choose at least one action.
- Sims process running: apply and restore fail before mutation.
- Process check unavailable: apply and restore fail before mutation.
- Source hash/size mismatch: apply fails and asks for a fresh inventory scan and cleanup plan.
- Destination collision: apply fails before moving that action.
- Restore collision: restore fails and keeps the manifest restorable.
- Partial move: record enough status and error detail for restore or manual repair.

## Testing

- Stage a manifest from a cleanup plan with one explicit action.
- Refuse staging when no action or all-actions flag is provided.
- Refuse unknown and duplicate action IDs.
- Refuse unsupported plan versions and malformed plan files.
- Refuse source paths outside `Mods`.
- Refuse destinations outside `_Simanalysis_Cleanup`.
- Refuse symlinked sources and destination paths whose existing ancestors are symlinks.
- Apply writes the manifest before moving and updates action status after move.
- Apply moves selected files only and never moves unselected cleanup-plan actions.
- Apply refuses while The Sims 4 process guard reports running.
- Apply refuses if live source hash or size no longer matches expected evidence.
- Apply records partial progress if a later action blocks after an earlier move.
- Restore moves files back using only manifest paths.
- Restore refuses collisions and preserves manifest state.
- Bridge parser and dispatch tests cover all four commands.
- A synthetic end-to-end test proves stage -> apply -> restore returns the Mods folder to its original file set.

## Later Work

- Visual cleanup route with checklist review and exact destination preview.
- Inventory event-log rows for staged, applied, and restored operations.
- Cache Doctor using the same operating-table engine.
- Profile activation using the same operating-table engine.
- General action bundles not sourced from Cleanup Planner v1.
- Resume mode for partially applied manifests after manual repair.
