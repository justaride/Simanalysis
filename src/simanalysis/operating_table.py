"""Manifest-first cleanup operation staging, apply, and restore."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, cast

from simanalysis.treatment import assert_sims_not_running as assert_sims_not_running

MANIFEST_VERSION = 1
SESSION_ROOT_NAME = "_Simanalysis_Cleanup"
MANIFEST_DIR_NAME = "manifests"
VALID_ACTION_KINDS = {
    "review_duplicate",
    "review_archive",
    "review_resource_cfg",
    "review_support_file",
    "review_misplaced_tray",
}
VALID_MANIFEST_STATUSES = {
    "planned",
    "applying",
    "applied",
    "partial",
    "blocked",
    "restoring",
    "restored",
}
RESTORABLE_ACTION_STATUSES = {"moving", "moved", "restore_pending", "restoring"}


class OperatingTable:
    """Stage and execute cleanup operations from review-only cleanup plans."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now

    def stage_cleanup_plan(
        self,
        root_path: Path | str,
        plan: dict[str, Any],
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Invalid Sims 4 directory path: {root_path}")
        _validate_plan_for_root(plan, root)

        selected_ids = _selected_action_ids(plan, selected_action_ids, all_actions)
        created_at = self._clock()
        operation_id = _operation_id(created_at)
        manifest_path = root / SESSION_ROOT_NAME / MANIFEST_DIR_NAME / f"{operation_id}.json"
        actions = [_manifest_action(root, plan, action_id) for action_id in selected_ids]
        manifest: dict[str, Any] = {
            "version": MANIFEST_VERSION,
            "operation_id": operation_id,
            "created_at": created_at,
            "updated_at": created_at,
            "root_path": str(root),
            "mods_path": str(root / "Mods"),
            "source_plan": {
                "version": int(plan["version"]),
                "plan_id": str(plan["plan_id"]),
                "scan_id": int(plan["scan_id"]),
                "created_at": str(plan["created_at"]),
            },
            "manifest_path": str(manifest_path),
            "status": "planned",
            "actions": actions,
            "warnings": [],
            "blockers": [],
        }
        return _write_manifest(manifest)

    def stage_cleanup_plan_file(
        self,
        root_path: Path | str,
        plan_path: Path | str,
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        plan = _load_plan_file(plan_path)
        return self.stage_cleanup_plan(
            root_path,
            plan,
            selected_action_ids=selected_action_ids,
            all_actions=all_actions,
        )

    def load_status(self, manifest_path: Path | str) -> dict[str, Any]:
        return load_manifest(manifest_path)

    def apply(self, manifest_path: Path | str) -> dict[str, Any]:
        raise NotImplementedError("apply is implemented in Task 2")

    def restore(self, manifest_path: Path | str) -> dict[str, Any]:
        raise NotImplementedError("restore is implemented in Task 3")


def load_manifest(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Manifest must be a JSON object")
    manifest = cast(dict[str, Any], parsed)
    _validate_manifest(manifest, path)
    return manifest


def _validate_manifest(manifest: dict[str, Any], path: Path) -> None:
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("Unsupported cleanup operation manifest version")
    required = {
        "operation_id",
        "created_at",
        "updated_at",
        "root_path",
        "mods_path",
        "source_plan",
        "manifest_path",
        "status",
        "actions",
        "warnings",
        "blockers",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"Manifest is missing required keys: {', '.join(sorted(missing))}")
    if manifest["status"] not in VALID_MANIFEST_STATUSES:
        raise ValueError(f"Unknown cleanup operation status: {manifest['status']}")
    if Path(str(manifest["manifest_path"])).expanduser().resolve() != path:
        raise ValueError("Manifest path does not match loaded path")
    if not isinstance(manifest["actions"], list):
        raise ValueError("Manifest actions must be a list")


def _load_plan_file(plan_path: Path | str) -> dict[str, Any]:
    path = Path(plan_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Cleanup plan not found: {plan_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cleanup plan is not valid JSON: {plan_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Cleanup plan must be a JSON object")
    return cast(dict[str, Any], parsed)


def _validate_plan_for_root(plan: dict[str, Any], root: Path) -> None:
    if plan.get("version") != 1:
        raise ValueError("Unsupported cleanup plan version")
    if Path(str(plan.get("root_path", ""))).expanduser().resolve() != root:
        raise ValueError("Cleanup plan root does not match selected Sims 4 folder")
    for key in ("plan_id", "created_at", "scan_id", "findings"):
        if key not in plan:
            raise ValueError(f"Cleanup plan is missing required key: {key}")
    if not isinstance(plan["findings"], list):
        raise ValueError("Cleanup plan findings must be a list")


def _selected_action_ids(
    plan: dict[str, Any],
    selected_action_ids: list[str] | None,
    all_actions: bool,
) -> list[str]:
    selected = list(selected_action_ids or [])
    if selected and all_actions:
        raise ValueError("Choose explicit actions or --all-actions, not both")
    available = [action["action_id"] for _, action in _iter_plan_actions(plan)]
    if all_actions:
        selected = [str(action_id) for action_id in available]
    if not selected:
        raise ValueError("Choose at least one cleanup action")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate cleanup action selected")
    missing = sorted(set(selected) - {str(action_id) for action_id in available})
    if missing:
        raise ValueError(f"Unknown cleanup action: {', '.join(missing)}")
    return selected


def _iter_plan_actions(plan: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for finding in plan["findings"]:
        if not isinstance(finding, dict):
            continue
        actions = finding.get("actions", [])
        if not isinstance(actions, list):
            continue
        for action in actions:
            if isinstance(action, dict):
                pairs.append((finding, action))
    return pairs


def _find_plan_action(
    plan: dict[str, Any],
    action_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (finding, action)
        for finding, action in _iter_plan_actions(plan)
        if str(action.get("action_id")) == action_id
    ]
    if len(matches) != 1:
        raise ValueError(f"Cleanup action must map to exactly one finding: {action_id}")
    return matches[0]


def _manifest_action(root: Path, plan: dict[str, Any], action_id: str) -> dict[str, Any]:
    finding, action = _find_plan_action(plan, action_id)
    kind = str(action.get("kind", ""))
    if kind not in VALID_ACTION_KINDS:
        raise ValueError(f"Unsupported cleanup action kind: {kind}")

    source_relative = str(action.get("source_relative_path", ""))
    destination_relative = str(action.get("proposed_destination", ""))
    source_path = _resolve_source(root, source_relative)
    destination_path = _resolve_destination(root, destination_relative)
    evidence = finding.get("evidence", {})
    if not isinstance(evidence, dict):
        raise ValueError(f"Cleanup finding has invalid evidence: {finding.get('finding_id')}")
    expected = _expected_for_action(evidence, source_relative)
    _reject_symlinked_path(source_path, "symlinked source")
    _reject_symlinked_existing_ancestors(destination_path, "symlinked destination")
    return {
        "action_id": action_id,
        "finding_id": str(finding.get("finding_id", "")),
        "kind": kind,
        "source_relative_path": source_relative,
        "destination_relative_path": destination_relative,
        "source_path": str(source_path),
        "destination_path": str(destination_path),
        "reason": str(action.get("reason", "")),
        "expected": expected,
        "status": "pending",
        "error": None,
    }


def _expected_for_action(evidence: dict[str, Any], source_relative: str) -> dict[str, Any]:
    if "path" in evidence and str(evidence["path"]) != source_relative:
        raise ValueError("Cleanup finding evidence path does not match selected action")
    expected: dict[str, Any] = {}
    if "sha256" in evidence:
        expected["sha256"] = str(evidence["sha256"])
    if "size" in evidence:
        expected["size"] = int(evidence["size"])
    if "keep_candidate" in evidence:
        expected["keep_candidate"] = str(evidence["keep_candidate"])
    return expected


def _resolve_source(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Cleanup source must be a relative Mods path")
    source = _logical_absolute(root / relative_path)
    mods = _logical_absolute(root / "Mods")
    try:
        source.relative_to(mods)
    except ValueError as exc:
        raise ValueError("Cleanup source must be under Mods") from exc
    return source


def _resolve_destination(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ValueError("Cleanup destination must be relative")
    destination = _logical_absolute(root / relative_path)
    cleanup_root = _logical_absolute(root / SESSION_ROOT_NAME)
    try:
        destination.relative_to(cleanup_root)
    except ValueError as exc:
        raise ValueError("Cleanup destination must be under _Simanalysis_Cleanup") from exc
    if destination == cleanup_root:
        raise ValueError("Cleanup destination must be a file path")
    return destination


def _logical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _reject_symlinked_path(path: Path, message: str) -> None:
    for part in [path, *path.parents]:
        if part.exists() and part.is_symlink():
            raise ValueError(f"Refusing {message}: {path}")


def _reject_symlinked_existing_ancestors(path: Path, message: str) -> None:
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    _reject_symlinked_path(current, message)


def _write_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(manifest["manifest_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=path.parent,
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(json.dumps(manifest, indent=2, sort_keys=True))
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return manifest


def _operation_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cleanup-op-{digits[:8]}-{digits[8:14]}"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
