# Cleanup Planner v1 - design

**Status:** Design approved; awaiting written-spec review before implementation planning
**Date:** 2026-06-11
**Roadmap:** Track B, Milestone 1. Builds on the read-only inventory ledger by turning known Mods-folder file facts into a cleanup plan without moving files.

## Goal

Add a read-only Cleanup Planner that consumes the latest inventory snapshot for a Sims 4 folder and emits a JSON-serializable plan for low-risk cleanup candidates inside `Mods`.

The planner should help the user see clutter and obvious hazards before any reversible action engine exists. It should identify what looks safe to review, explain why, and name the reversible destination that a future action engine would use. It must not move, delete, rename, quarantine, or create Sims-folder files in v1.

## Why Now

The inventory ledger can now record file identity, package parse status, DBPF resource keys, scan history, and per-file change events. That gives Simanalysis enough local truth to reason about common Mods-folder cleanup problems without touching the live folder.

This is the bridge from "what exists" to "what should be reviewed." It also gives the later quarantine/restore engine a concrete plan format to consume once mutating actions are explicitly designed.

## Scope

**In:**

- Use the latest inventory snapshot for a selected Sims 4 folder.
- Restrict v1 findings to files under `<sims4_dir>/Mods`.
- Group exact duplicate files by `sha256` and size.
- Identify inactive archives inside `Mods`: `.zip`, `.rar`, `.7z`.
- Identify duplicate `Resource.cfg` files under `Mods`.
- Identify preview, note, shortcut, and metadata files inside `Mods` that are not active Sims 4 mod payloads.
- Identify likely misplaced Tray files inside `Mods`.
- Produce a stable plan object with summary counts, findings, proposed actions, warnings, and exportable JSON.
- Expose the planner through a bridge command so Tauri and the web API can call it later.
- Keep all suggestions explainable and tied to evidence from the inventory ledger.

**Out:**

- Moving, deleting, renaming, quarantining, or restoring files.
- Creating cleanup manifests or quarantine folders.
- Deciding whether a mod is broken, outdated, malicious, or safe.
- Unpacking archives.
- Detecting non-exact duplicates by name similarity or fuzzy package contents.
- Scanning the whole Sims 4 folder outside `Mods`.
- UI route work.
- Network lookups, creator identity resolution, or update checks.

## Architecture

V1 should be a pure Python service plus bridge command:

```text
simanalysis.bridge
  cleanup-plan command
        |
        v
simanalysis.cleanup
  load latest inventory snapshot
  filter to Mods files
  run read-only rule checks
  emit cleanup plan
```

Suggested core units:

- `CleanupPlanner`: orchestrates the plan from an inventory DB path and Sims 4 root.
- `CleanupPlan`: serializable result with version, root, scan id, summary, findings, warnings, and generated timestamp.
- `CleanupFinding`: one explainable issue group, such as an exact duplicate group or one archive file.
- `CleanupAction`: one proposed future action, always read-only in v1, with source path, proposed destination, action kind, and reason.
- Rule helpers for duplicates, archives, duplicate `Resource.cfg`, support files, and misplaced Tray files.

The planner should depend on the inventory database, not on a fresh filesystem walk. If there is no inventory snapshot for the selected root, it should return a clear error telling the caller to run `inventory-scan` first.

## Mods Folder Boundary

V1 only analyzes paths whose latest snapshot `relative_path` is under `Mods/`.

The planner ignores:

- files outside `Mods`
- missing or moved-source rows from historical scans
- symlinked paths, because inventory already skips them
- Simanalysis-owned future folders such as `_Simanalysis_Cleanup` if they ever appear in later phases

The inventory snapshot remains the source of truth for file size, hash, extension, parse status, and resource count. The planner may derive path names and folder depth from `relative_path`, but it should not read live file contents.

## Finding Rules

### Exact duplicates

Group files by `(sha256, size)` within `Mods`. A group is a finding when it contains at least two files and the size is greater than zero.

The planner should choose one `keep` candidate deterministically so the plan is stable. V1 preference:

1. keep the path with the shortest folder depth
2. then the shortest path string
3. then lexicographic order

Every other file in the group gets a proposed `review_duplicate` action. The suggested future destination should be under:

```text
<sims4_dir>/_Simanalysis_Cleanup/<plan_id>/duplicates/<relative_path>
```

No duplicate action is applied in v1.

### Inactive archives

Flag files in `Mods` with extensions:

- `.zip`
- `.rar`
- `.7z`

The finding should explain that The Sims 4 does not load these archives directly from `Mods`; the user may need to unpack them or archive them outside Mods through a future reversible action.

The proposed action kind is `review_archive`.

### Duplicate Resource.cfg

`Mods/Resource.cfg` is expected. Additional `Resource.cfg` files under nested folders are findings because they can confuse folder organization and duplicate setup instructions.

The proposed action kind is `review_resource_cfg`. The root `Mods/Resource.cfg` is not a finding by itself.

### Support files

Flag common non-mod support files inside `Mods`:

- previews: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`
- notes and docs: `.txt`, `.md`, `.pdf`, `.rtf`, `.doc`, `.docx`
- links and shortcuts: `.url`, `.webloc`, `.lnk`
- system metadata: `.ds_store`, `thumbs.db`

These are not automatically wrong, but they are not active package or script payloads. The proposed action kind is `review_support_file`.

### Misplaced Tray files

Flag likely Tray payloads found in `Mods`:

- `.trayitem`
- `.blueprint`
- `.bpi`
- `.hhi`
- `.householdbinary`
- `.sgi`

The finding should explain that Tray files normally belong in the Sims 4 `Tray` folder, not `Mods`. The proposed action kind is `review_misplaced_tray`.

## Plan Shape

The bridge result should be compact and stable:

```json
{
  "version": 1,
  "plan_id": "cleanup-20260611-123456",
  "created_at": "2026-06-11T12:34:56Z",
  "root_path": "/Users/example/Documents/Electronic Arts/The Sims 4",
  "mods_path": "/Users/example/Documents/Electronic Arts/The Sims 4/Mods",
  "db_path": "/Users/example/Library/Application Support/Simanalysis/inventory.sqlite3",
  "scan_id": 12,
  "summary": {
    "files_considered": 1280,
    "finding_count": 8,
    "action_count": 14,
    "duplicate_groups": 2,
    "archives": 3,
    "duplicate_resource_cfg": 1,
    "support_files": 6,
    "misplaced_tray": 2
  },
  "findings": [
    {
      "finding_id": "duplicate:sha256:abc123",
      "category": "exact_duplicate",
      "severity": "review",
      "title": "Exact duplicate files",
      "explanation": "These files have identical SHA-256 and size in Mods.",
      "evidence": {
        "sha256": "abc123",
        "size": 12345,
        "paths": [
          "Mods/A/item.package",
          "Mods/B/item.package"
        ],
        "keep_candidate": "Mods/A/item.package"
      },
      "actions": [
        {
          "action_id": "duplicate:abc123:1",
          "kind": "review_duplicate",
          "source_relative_path": "Mods/B/item.package",
          "proposed_destination": "_Simanalysis_Cleanup/cleanup-20260611-123456/duplicates/Mods/B/item.package",
          "reason": "Exact duplicate of Mods/A/item.package"
        }
      ]
    }
  ],
  "warnings": []
}
```

`proposed_destination` is a future-action hint only. It must not be created by v1.

## Bridge Command

Add one bridge command:

```text
simanalysis-bridge cleanup-plan <sims4_dir> [--db PATH] [--export PATH]
```

Behavior:

- `--db` defaults to the inventory database path.
- The command requires an existing latest inventory snapshot for `sims4_dir`.
- The command emits `start`, `result`, and `done` NDJSON events.
- `--export PATH` writes the plan JSON only when explicitly requested, and the export path must be outside the selected Sims 4 root.
- Without `--export`, the command writes nothing.

The first implementation may omit Tauri and web wrappers if the bridge command and service contract are complete. If wrappers are added in the same slice, they should be thin argument builders only, with no visual route.

## Safety Model

Cleanup Planner v1 is read-only by default and must not mutate Sims files.

It may read:

- the inventory SQLite database
- the latest snapshot rows for the selected Sims 4 root

It must not:

- walk live Sims files unless a future explicit rescan option is designed
- write under the Sims 4 folder
- create `_Simanalysis_Cleanup`
- move, delete, rename, quarantine, or restore files
- mark any action as applied
- treat a finding as user-approved cleanup

The plan should use language like `review` and `proposed_destination`, not `delete` or `remove`.

## Error Handling

- Invalid Sims 4 folder: bridge returns `INVALID_INPUT`.
- Missing inventory DB: return a clear error saying no inventory database exists and `inventory-scan` should run first.
- No latest snapshot for the root: return a clear error saying no inventory scan exists for that Sims folder.
- Missing `Mods` entries in the snapshot: return an empty plan with a warning instead of failing.
- Corrupt inventory DB: return a readable error and do not attempt a live scan.
- Export path inside the selected Sims 4 root: return a clear error and write nothing.
- Unsupported export path or write failure: fail the command without altering the plan data in the DB.

## Testing

- Unit-test duplicate grouping with deterministic keep candidates.
- Unit-test archives in `Mods` become `review_archive` findings.
- Unit-test nested `Resource.cfg` files are findings while root `Mods/Resource.cfg` is not.
- Unit-test preview, note, shortcut, and metadata support files.
- Unit-test misplaced Tray file extensions.
- Unit-test that files outside `Mods` are ignored.
- Unit-test that no plan is available before an inventory scan.
- Unit-test bridge parser and dispatch for `cleanup-plan`.
- Unit-test `--export` writes a JSON plan only when explicitly requested.
- Regression-test that planning does not create `_Simanalysis_Cleanup` or move any files.
- Run the existing inventory tests, bridge tests, ruff, format check, mypy, real-fixture tests, and full pytest.

## Validation Plan

Use a synthetic Sims 4 fixture under `/tmp`:

1. Create `Mods` files covering exact duplicates, archives, support files, nested `Resource.cfg`, and misplaced Tray files.
2. Run `inventory-scan` against the fixture.
3. Run `cleanup-plan` against the same fixture.
4. Verify the plan categories and action counts.
5. Verify no Sims-folder files or directories were created, moved, renamed, or deleted.

Real-folder validation may be read-only:

- run `inventory-scan` against the user's real Sims 4 folder only if explicitly approved for that session
- run `cleanup-plan` with no export path first
- report summary counts and warnings without publishing personal file names in commit messages or docs

## Acceptance Criteria

- A synthetic Mods folder with duplicate packages produces a stable exact-duplicate finding group.
- Archives, nested `Resource.cfg`, support files, and misplaced Tray files produce separate explainable findings.
- Files outside `Mods` do not appear in the plan.
- The plan is JSON-serializable and can be exported only when explicitly requested.
- Running the planner never creates `_Simanalysis_Cleanup` and never moves or deletes files.
- The bridge command emits valid NDJSON and returns a clear error when no inventory snapshot exists.
