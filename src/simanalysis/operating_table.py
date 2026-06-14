"""Manifest-first cleanup operation staging, apply, and restore."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import suppress
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
RESTORABLE_MANIFEST_STATUSES = {"applied", "partial", "restoring"}
APPLICABLE_MANIFEST_STATUSES = {"planned", "partial"}
APPLICABLE_ACTION_STATUSES = {"pending", "blocked"}
VALID_ACTION_STATUSES = APPLICABLE_ACTION_STATUSES | {
    "moving",
    "moved",
    "restore_pending",
    "restoring",
    "restored",
}
REQUIRED_ACTION_KEYS = {
    "action_id",
    "finding_id",
    "kind",
    "source_relative_path",
    "destination_relative_path",
    "source_path",
    "destination_path",
    "reason",
    "expected",
    "status",
    "error",
}


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
        actions = [_manifest_action(root, plan, action_id) for action_id in selected_ids]
        source_plan = {
            "version": int(plan["version"]),
            "plan_id": str(plan["plan_id"]),
            "scan_id": int(plan["scan_id"]),
            "created_at": str(plan["created_at"]),
        }
        base_operation_id = _operation_id(created_at)
        operation_id, manifest_path = _unique_manifest_path(
            root / SESSION_ROOT_NAME / MANIFEST_DIR_NAME,
            base_operation_id,
        )
        manifest: dict[str, Any] = {
            "version": MANIFEST_VERSION,
            "operation_id": operation_id,
            "created_at": created_at,
            "updated_at": created_at,
            "root_path": str(root),
            "mods_path": str(root / "Mods"),
            "source_plan": source_plan,
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
        assert_sims_not_running()
        manifest = load_manifest(manifest_path)
        if manifest["status"] not in APPLICABLE_MANIFEST_STATUSES:
            raise ValueError(
                f"Cleanup operation cannot be applied from status: {manifest['status']}"
            )
        actions = _validated_apply_actions(manifest)
        pending = [
            action for action in actions if action.get("status") in APPLICABLE_ACTION_STATUSES
        ]
        _preflight_actions(manifest, pending)
        manifest["status"] = "applying"
        _save_manifest(manifest)

        for action in pending:
            move_completed = False
            try:
                _preflight_action(manifest, action)
                action["status"] = "moving"
                action["error"] = None
                _save_manifest(manifest)
                destination = Path(str(action["destination_path"]))
                _ensure_safe_destination_parent(manifest, destination)
                if destination.exists():
                    raise ValueError(f"Destination already exists: {destination}")
                shutil.move(str(action["source_path"]), str(destination))
                move_completed = True
                action["status"] = "moved"
                _save_manifest(manifest)
            except Exception as exc:
                if move_completed:
                    if action.get("status") not in RESTORABLE_ACTION_STATUSES:
                        action["status"] = "restore_pending"
                    action["error"] = str(exc)
                    manifest["status"] = "partial"
                    _save_manifest_best_effort(manifest)
                    raise
                action["status"] = "blocked"
                action["error"] = str(exc)
                manifest["status"] = "partial" if _has_moved_actions(manifest) else "blocked"
                _save_manifest(manifest)
                raise

        manifest["status"] = "applied"
        return _save_manifest(manifest)

    def restore(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_manifest(manifest_path)
        actions = _validated_apply_actions(manifest)
        restorable = [
            action
            for action in reversed(actions)
            if action.get("status") in RESTORABLE_ACTION_STATUSES
        ]
        if not _can_restore_manifest_status(manifest, restorable):
            raise ValueError(
                f"Cleanup operation cannot be restored from status: {manifest['status']}"
            )
        _preflight_restore_actions(manifest, restorable)

        manifest["status"] = "restoring"
        _save_manifest(manifest)

        for action in restorable:
            move_completed = False
            already_restored = False
            try:
                restore_paths = _prepare_restore_action(manifest, action)
                if restore_paths is None:
                    already_restored = True
                    action["status"] = "restored"
                    action["error"] = None
                    _save_manifest(manifest)
                    continue

                source, destination = restore_paths
                action["status"] = "restoring"
                action["error"] = None
                _save_manifest(manifest)
                shutil.move(str(source), str(destination))
                move_completed = True
                action["status"] = "restored"
                action["error"] = None
                _save_manifest(manifest)
            except Exception as exc:
                if move_completed:
                    action["status"] = "restored"
                    action["error"] = str(exc)
                    _save_manifest_best_effort(manifest)
                    raise
                if already_restored:
                    action["status"] = "restored"
                    action["error"] = str(exc)
                    _save_manifest_best_effort(manifest)
                    raise
                action["status"] = "restore_pending"
                action["error"] = str(exc)
                manifest["status"] = "blocked"
                _save_manifest(manifest)
                raise

        if _has_moved_or_moving_actions(manifest):
            manifest["status"] = "partial"
            _save_manifest(manifest)
            raise ValueError("Could not restore every moved cleanup action")
        manifest["status"] = "restored"
        return _save_manifest(manifest)


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
    status = manifest["status"]
    if not isinstance(status, str):
        raise ValueError("Cleanup operation status must be a string")
    if status not in VALID_MANIFEST_STATUSES:
        raise ValueError(f"Unknown cleanup operation status: {status}")
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
    available = [_plan_action_id(action) for _, action in _iter_plan_actions(plan)]
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


def _plan_action_id(action: dict[str, Any]) -> str:
    action_id = action.get("action_id")
    if not isinstance(action_id, str) or not action_id:
        raise ValueError("Cleanup action is missing action_id")
    return action_id


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
        if part.is_symlink():
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

        try:
            parent_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return manifest
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return manifest


def _save_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    _validate_manifest_write_target(manifest)
    manifest["updated_at"] = _utc_now()
    return _write_manifest(manifest)


def _save_manifest_best_effort(manifest: dict[str, Any]) -> None:
    with suppress(Exception):
        _save_manifest(manifest)


def _validated_apply_actions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_manifest_write_target(manifest)
    actions = manifest.get("actions")
    if not isinstance(actions, list):
        raise ValueError("Manifest actions must be a list")
    validated: list[dict[str, Any]] = []
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"Manifest action at index {index} must be an object")
        _validate_action_contract(manifest, action)
        validated.append(action)
    return validated


def _preflight_actions(manifest: dict[str, Any], actions: list[dict[str, Any]]) -> None:
    _reject_duplicate_action_paths(actions, "source_path", "source")
    _reject_duplicate_action_paths(actions, "destination_path", "destination")
    for action in actions:
        _preflight_action(manifest, action)


def _preflight_restore_actions(
    manifest: dict[str, Any],
    actions: list[dict[str, Any]],
) -> None:
    _reject_duplicate_action_paths(actions, "destination_path", "restore source")
    _reject_duplicate_action_paths(actions, "source_path", "restore destination")
    for action in actions:
        _prepare_restore_action(manifest, action, create_destination_parent=False)


def _reject_duplicate_action_paths(
    actions: list[dict[str, Any]],
    key: str,
    label: str,
) -> None:
    seen: dict[Path, str] = {}
    for action in actions:
        path = _logical_absolute(Path(str(action[key])))
        action_id = str(action["action_id"])
        previous_action_id = seen.get(path)
        if previous_action_id is not None:
            raise ValueError(
                f"Duplicate cleanup action {label} path: {path} ({previous_action_id}, {action_id})"
            )
        seen[path] = action_id


def _preflight_action(manifest: dict[str, Any], action: dict[str, Any]) -> None:
    _validate_action_contract(manifest, action)
    source = Path(str(action["source_path"]))
    destination = Path(str(action["destination_path"]))
    if not source.exists():
        raise ValueError(f"Source path is missing: {source}")
    _reject_symlinked_path(source, "symlinked source")
    _reject_symlinked_existing_ancestors(destination, "symlinked destination")
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    _validate_expected_file_identity(action)


def _ensure_safe_destination_parent(manifest: dict[str, Any], destination: Path) -> None:
    root = _manifest_root(manifest)
    cleanup_root = _logical_absolute(root / SESSION_ROOT_NAME)
    destination = _logical_absolute(destination)
    try:
        relative_parent = destination.parent.relative_to(cleanup_root)
    except ValueError as exc:
        raise ValueError("Destination path must be under cleanup root") from exc

    _ensure_safe_directory_component(cleanup_root, destination, "symlinked destination")
    current = cleanup_root
    for part in relative_parent.parts:
        current = current / part
        _ensure_safe_directory_component(current, destination, "symlinked destination")


def _ensure_safe_restore_destination_parent(
    manifest: dict[str, Any],
    destination: Path,
) -> None:
    _check_restore_destination_parent(manifest, destination, create=True)


def _check_restore_destination_parent(
    manifest: dict[str, Any],
    destination: Path,
    *,
    create: bool,
) -> None:
    root = _manifest_root(manifest)
    mods = _manifest_mods(manifest, root)
    destination = _logical_absolute(destination)
    try:
        relative_parent = destination.parent.relative_to(mods)
    except ValueError as exc:
        raise ValueError("Restore destination path must be under Mods") from exc

    if not _ensure_safe_directory_component(
        mods,
        destination,
        "symlinked restore destination",
        create=create,
    ):
        return
    current = mods
    for part in relative_parent.parts:
        current = current / part
        if not _ensure_safe_directory_component(
            current,
            destination,
            "symlinked restore destination",
            create=create,
        ):
            return


def _ensure_safe_directory_component(
    path: Path,
    destination: Path,
    symlink_message: str,
    *,
    create: bool = True,
) -> bool:
    if path.is_symlink():
        raise ValueError(f"Refusing {symlink_message}: {destination}")
    if path.exists() and not path.is_dir():
        raise ValueError(f"Destination parent is not a directory: {path}")
    if not path.exists():
        if not create:
            return False
        path.mkdir(exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing {symlink_message}: {destination}")
    if not path.is_dir():
        raise ValueError(f"Destination parent is not a directory: {path}")
    return True


def _validate_manifest_write_target(manifest: dict[str, Any]) -> None:
    root = _manifest_root(manifest)
    _manifest_mods(manifest, root)
    manifest_path = _absolute_manifest_path(manifest)
    cleanup_root = _logical_absolute(root / SESSION_ROOT_NAME)
    manifest_root = _logical_absolute(cleanup_root / MANIFEST_DIR_NAME)
    try:
        manifest_path.relative_to(manifest_root)
    except ValueError as exc:
        raise ValueError("Manifest path must be under cleanup manifest root") from exc
    _reject_symlinked_path(manifest_path, "symlinked cleanup manifest")


def _validate_action_contract(manifest: dict[str, Any], action: dict[str, Any]) -> None:
    missing = REQUIRED_ACTION_KEYS - set(action)
    if missing:
        raise ValueError(f"Manifest action is missing required keys: {', '.join(sorted(missing))}")

    for key in (
        "action_id",
        "finding_id",
        "kind",
        "source_relative_path",
        "destination_relative_path",
        "source_path",
        "destination_path",
        "reason",
    ):
        if not isinstance(action[key], str) or not action[key]:
            raise ValueError(f"Manifest action {key} must be a non-empty string")

    if action["kind"] not in VALID_ACTION_KINDS:
        raise ValueError(f"Unsupported cleanup action kind: {action['kind']}")

    status = action["status"]
    if not isinstance(status, str):
        raise ValueError("Cleanup action status must be a string")
    if status not in VALID_ACTION_STATUSES:
        raise ValueError(f"Unsupported cleanup action status: {status}")

    if action["error"] is not None and not isinstance(action["error"], str):
        raise ValueError("Manifest action error must be a string or null")

    expected = action["expected"]
    if not isinstance(expected, dict):
        raise ValueError("Action expected evidence must be an object")
    if "size" not in expected or "sha256" not in expected:
        raise ValueError("Action expected evidence must include size and sha256")

    _validate_expected_size(expected["size"])
    if not isinstance(expected["sha256"], str) or not expected["sha256"]:
        raise ValueError("Action expected sha256 must be a non-empty string")

    _validate_source_path_relation(manifest, action)
    _validate_destination_path_relation(manifest, action)


def _validate_source_path_relation(
    manifest: dict[str, Any],
    action: dict[str, Any],
) -> None:
    root = _manifest_root(manifest)
    source = _absolute_action_path(action, "source_path", "Source path")
    expected_source = _resolve_source(root, str(action["source_relative_path"]))
    if source != expected_source:
        raise ValueError("Source path does not match relative path")


def _validate_destination_path_relation(
    manifest: dict[str, Any],
    action: dict[str, Any],
) -> None:
    root = _manifest_root(manifest)
    destination = _absolute_action_path(action, "destination_path", "Destination path")
    expected_destination = _resolve_destination(root, str(action["destination_relative_path"]))
    if destination != expected_destination:
        raise ValueError("Destination path does not match relative path")


def _absolute_action_path(
    action: dict[str, Any],
    key: str,
    label: str,
) -> Path:
    path = Path(str(action[key])).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute")
    return _logical_absolute(path)


def _absolute_manifest_path(manifest: dict[str, Any]) -> Path:
    path = Path(str(manifest["manifest_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Manifest path must be absolute")
    return _logical_absolute(path)


def _manifest_root(manifest: dict[str, Any]) -> Path:
    path = Path(str(manifest["root_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Manifest root path must be absolute")
    root = _logical_absolute(path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Manifest root path is not a directory: {root}")
    return root


def _manifest_mods(manifest: dict[str, Any], root: Path) -> Path:
    path = Path(str(manifest["mods_path"])).expanduser()
    if not path.is_absolute():
        raise ValueError("Manifest Mods path must be absolute")
    mods = _logical_absolute(path)
    expected_mods = _logical_absolute(root / "Mods")
    if mods != expected_mods:
        raise ValueError("Manifest Mods path does not match root")
    return mods


def _validate_expected_file_identity(action: dict[str, Any]) -> None:
    source = Path(str(action["source_path"]))
    _validate_expected_path_identity(action, source, "Source path")


def _validate_expected_path_identity(
    action: dict[str, Any],
    path: Path,
    label: str,
) -> None:
    expected = cast(dict[str, Any], action["expected"])
    if path.stat().st_size != _validate_expected_size(expected["size"]):
        raise ValueError(f"{label} no longer matches cleanup plan evidence: {path}")
    if _sha256_file(path) != str(expected["sha256"]):
        raise ValueError(f"{label} no longer matches cleanup plan evidence: {path}")


def _validate_expected_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Action expected size must be an integer") from exc
    if size < 0:
        raise ValueError("Action expected size must be non-negative")
    return size


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_moved_actions(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(action, dict) and action.get("status") == "moved"
        for action in manifest.get("actions", [])
    )


def _has_moved_or_moving_actions(manifest: dict[str, Any]) -> bool:
    return any(
        isinstance(action, dict) and action.get("status") in RESTORABLE_ACTION_STATUSES
        for action in manifest.get("actions", [])
    )


def _can_restore_manifest_status(
    manifest: dict[str, Any],
    restorable_actions: list[dict[str, Any]],
) -> bool:
    status = manifest["status"]
    if status in RESTORABLE_MANIFEST_STATUSES:
        return True
    return status == "applying" and bool(restorable_actions)


def _prepare_restore_action(
    manifest: dict[str, Any],
    action: dict[str, Any],
    *,
    create_destination_parent: bool = True,
) -> tuple[Path, Path] | None:
    _validate_action_contract(manifest, action)
    source = Path(str(action["destination_path"]))
    destination = Path(str(action["source_path"]))

    if not source.exists():
        if destination.is_symlink():
            raise ValueError(f"Refusing symlinked restore destination: {destination}")
        if destination.exists():
            _reject_symlinked_path(destination, "symlinked restore destination")
            _validate_expected_path_identity(action, destination, "Restore destination")
            return None
        raise ValueError(f"Restore source is missing: {source}")

    _reject_symlinked_path(source, "symlinked restore source")
    _validate_expected_path_identity(action, source, "Restore source")
    if destination.is_symlink():
        raise ValueError(f"Refusing symlinked restore destination: {destination}")
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}")
    if create_destination_parent:
        _ensure_safe_restore_destination_parent(manifest, destination)
    else:
        _check_restore_destination_parent(manifest, destination, create=False)
    if destination.is_symlink():
        raise ValueError(f"Refusing symlinked restore destination: {destination}")
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}")
    return source, destination


def _unique_manifest_path(manifest_dir: Path, base_operation_id: str) -> tuple[str, Path]:
    _reject_symlinked_path(manifest_dir, "symlinked cleanup manifest root")
    manifest_dir.mkdir(parents=True, exist_ok=True)
    operation_id = base_operation_id
    suffix = 1
    while True:
        path = manifest_dir / f"{operation_id}.json"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            suffix += 1
            operation_id = f"{base_operation_id}-{suffix}"
        else:
            os.close(fd)
            return operation_id, path


def _operation_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cleanup-op-{digits[:8]}-{digits[8:14]}"


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
