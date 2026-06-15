"""Read-only Cache Doctor status for Sims 4 user folders."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, cast

from simanalysis.treatment import assert_sims_not_running as assert_sims_not_running

CACHE_TARGETS: tuple[dict[str, str], ...] = (
    {
        "id": "localthumbcache",
        "relative_path": "localthumbcache.package",
        "kind": "file",
        "label": "Local thumbnail cache",
        "risk": "medium",
        "reason": "Can retain stale thumbnails and CAS/build-buy previews after mod or patch changes.",
    },
    {
        "id": "avatarcache",
        "relative_path": "avatarcache.package",
        "kind": "file",
        "label": "Avatar cache",
        "risk": "low",
        "reason": "Can retain stale Sim portrait data; usually safe to review after UI or CAS issues.",
    },
    {
        "id": "cache_dir",
        "relative_path": "cache",
        "kind": "directory",
        "label": "Cache directory",
        "risk": "medium",
        "reason": "General game cache directory that can contain stale generated data.",
    },
    {
        "id": "cachestr_dir",
        "relative_path": "cachestr",
        "kind": "directory",
        "label": "String cache directory",
        "risk": "medium",
        "reason": "Can retain cached strings after tuning, STBL, or language-content changes.",
    },
    {
        "id": "onlinethumbnailcache_dir",
        "relative_path": "onlinethumbnailcache",
        "kind": "directory",
        "label": "Online thumbnail cache",
        "risk": "low",
        "reason": "Thumbnail cache directory; usually cosmetic but useful during visual cache review.",
    },
    {
        "id": "cachewebkit_dir",
        "relative_path": "cachewebkit",
        "kind": "directory",
        "label": "WebKit cache directory",
        "risk": "low",
        "reason": "Embedded web/UI cache directory; review only when UI/cache symptoms support it.",
    },
)
CACHE_OPERATION_ROOT_NAME = "_Simanalysis_CacheDoctor"
CACHE_QUARANTINE_DIR_NAME = "quarantine"
CACHE_MANIFEST_DIR_NAME = "manifests"
CACHE_MANIFEST_VERSION = 1
CACHE_PLAN_VERSION = 1
CACHE_MANIFEST_STATUSES = {"planned", "applying", "applied", "partial", "restoring", "restored"}
CACHE_ACTION_STATUSES = {
    "pending",
    "quarantining",
    "quarantined",
    "blocked",
    "restoring",
    "restored",
}


def _modified_at(path: Path) -> str | None:
    try:
        timestamp = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _logical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(path.expanduser()))


def _sha256_hex(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlinked_path(path: Path, message: str) -> None:
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise ValueError(f"Refusing {message}: {path}")


def _safe_relative_path(value: str) -> Path:
    relative = Path(value)
    if not value or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Cache target path must be relative to the Sims 4 folder")
    return relative


def _directory_stats(path: Path, warnings: list[str]) -> tuple[int, int]:
    size_bytes = 0
    item_count = 0
    for child in path.rglob("*"):
        if child.is_symlink():
            warnings.append(f"Skipped symlinked cache entry: {child}")
            continue
        item_count += 1
        if child.is_file():
            try:
                size_bytes += child.stat().st_size
            except OSError as exc:
                warnings.append(f"Could not stat cache entry {child}: {exc}")
    return size_bytes, item_count


def _target_evidence(path: Path, kind: str) -> dict[str, Any]:
    if kind == "file":
        return {
            "kind": kind,
            "size": path.stat().st_size,
            "sha256": _sha256_hex(path),
            "item_count": 1,
        }
    warnings: list[str] = []
    size_bytes, item_count = _directory_stats(path, warnings)
    if warnings:
        raise ValueError("; ".join(warnings))
    return {
        "kind": kind,
        "size": size_bytes,
        "sha256": None,
        "item_count": item_count,
    }


def _validate_target_identity(path: Path, expected: dict[str, Any]) -> None:
    kind = str(expected.get("kind", ""))
    current = _target_evidence(path, kind)
    if int(current["size"]) != int(expected["size"]):
        raise ValueError(f"Cache target no longer matches plan evidence: {path}")
    if int(current["item_count"]) != int(expected["item_count"]):
        raise ValueError(f"Cache target no longer matches plan evidence: {path}")
    if kind == "file" and current["sha256"] != expected.get("sha256"):
        raise ValueError(f"Cache target no longer matches plan evidence: {path}")


def _cache_target_by_id(target_id: str) -> dict[str, str]:
    for target in CACHE_TARGETS:
        if target["id"] == target_id:
            return target
    raise ValueError(f"Unknown cache target: {target_id}")


def _absent_target(root: Path, target: dict[str, str]) -> dict[str, Any]:
    absolute_path = root / target["relative_path"]
    return {
        **target,
        "path": str(absolute_path),
        "present": False,
        "status": "absent",
        "size_bytes": 0,
        "item_count": 0,
        "modified_at": None,
    }


def build_cache_status(sims4_dir: Path | str) -> dict[str, Any]:
    """Inspect known Sims 4 cache targets without mutating the selected folder."""
    root = Path(sims4_dir).expanduser().resolve()
    warnings: list[str] = []
    targets: list[dict[str, Any]] = []

    for target in CACHE_TARGETS:
        absolute_path = root / target["relative_path"]
        if not absolute_path.exists():
            targets.append(_absent_target(root, target))
            continue

        if absolute_path.is_symlink():
            warnings.append(f"Skipped symlinked cache target: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "skipped_symlink"
            targets.append(skipped)
            continue

        expected_kind = target["kind"]
        if expected_kind == "file" and not absolute_path.is_file():
            warnings.append(f"Cache target had unexpected type: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "unexpected_type"
            targets.append(skipped)
            continue
        if expected_kind == "directory" and not absolute_path.is_dir():
            warnings.append(f"Cache target had unexpected type: {absolute_path}")
            skipped = _absent_target(root, target)
            skipped["status"] = "unexpected_type"
            targets.append(skipped)
            continue

        if expected_kind == "directory":
            size_bytes, item_count = _directory_stats(absolute_path, warnings)
        else:
            size_bytes = absolute_path.stat().st_size
            item_count = 1

        targets.append(
            {
                **target,
                "path": str(absolute_path),
                "present": True,
                "status": "present",
                "size_bytes": size_bytes,
                "item_count": item_count,
                "modified_at": _modified_at(absolute_path),
            }
        )

    present = [target for target in targets if target["present"]]
    if present:
        recommendations = [
            "Review listed cache targets before planning cleanup.",
            "Use cache cleanup plan/apply only with explicit action approval.",
            "Close The Sims 4 before applying or restoring a cache cleanup plan.",
        ]
        status = "review_recommended"
    else:
        recommendations = ["No known Sims 4 cache targets were found in the selected folder."]
        status = "no_cache_targets_found"

    return {
        "status": status,
        "root_path": str(root),
        "targets": targets,
        "present_count": len(present),
        "total_size_bytes": sum(target["size_bytes"] for target in present),
        "warnings": warnings,
        "recommendations": recommendations,
        "mutates_files": False,
    }


def _cache_action(index: int, root: Path, target: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(target["relative_path"])
    source_path = root / _safe_relative_path(relative_path)
    blockers: list[str] = []
    expected: dict[str, Any] | None = None
    if target.get("status") == "skipped_symlink" or source_path.is_symlink():
        blockers.append("cache_target_symlink")
    elif target.get("present") is True:
        try:
            _reject_symlinked_path(source_path, "symlinked cache target")
            expected = _target_evidence(source_path, str(target["kind"]))
        except ValueError as exc:
            blockers.append(str(exc))
    else:
        blockers.append("cache_target_absent")

    stem = relative_path.replace("/", "__").replace("\\", "__")
    quarantine_relative = (
        Path(CACHE_OPERATION_ROOT_NAME) / CACHE_QUARANTINE_DIR_NAME / "pending" / stem
    )
    return {
        "action_id": f"cache-clear-{index:03d}",
        "action_type": "quarantine_cache_target",
        "target_id": target["id"],
        "status": "blocked" if blockers else "planned",
        "source_relative_path": relative_path,
        "source_path": str(source_path),
        "quarantine_relative_path": quarantine_relative.as_posix(),
        "quarantine_path": str(root / quarantine_relative),
        "expected": expected
        or {
            "kind": target.get("kind"),
            "size": 0,
            "sha256": None,
            "item_count": 0,
        },
        "blockers": blockers,
        "label": target.get("label"),
        "risk": target.get("risk"),
    }


def _plan_status(actions: list[dict[str, Any]]) -> str:
    if any(action["status"] == "blocked" for action in actions):
        return "blocked"
    if not actions:
        return "empty"
    return "ready_for_review"


def build_cache_cleanup_plan(sims4_dir: Path | str) -> dict[str, Any]:
    """Build a reversible cache cleanup plan without moving or deleting files."""
    status = build_cache_status(sims4_dir)
    root = Path(str(status["root_path"])).expanduser().resolve()
    actions: list[dict[str, Any]] = []
    for target in status["targets"]:
        if target.get("present") is True or target.get("status") == "skipped_symlink":
            actions.append(_cache_action(len(actions) + 1, root, target))
    generated_at = _utc_now()
    blocked_count = sum(1 for action in actions if action["status"] == "blocked")
    return {
        "version": CACHE_PLAN_VERSION,
        "plan_id": "cache-plan-" + generated_at.replace("-", "").replace(":", "")[:15],
        "generated_at": generated_at,
        "status": _plan_status(actions),
        "root_path": str(root),
        "manifest_path": None,
        "action_count": len(actions),
        "blocked_count": blocked_count,
        "requires_snapshot": True,
        "mutates_files": False,
        "actions": actions,
        "warnings": status.get("warnings", []),
        "recommendations": [
            "Review this plan before any manifest-backed cache cleanup.",
            "Cache cleanup quarantines targets instead of deleting them.",
            "Close The Sims 4 before applying or restoring this plan.",
        ],
    }


def write_cache_cleanup_plan(plan: dict[str, Any], output_path: Path | str) -> dict[str, Any]:
    """Write a cache cleanup plan manifest explicitly requested by the caller."""
    _validate_cache_plan_shape(plan)
    path = Path(output_path).expanduser().resolve()
    if path.exists() and path.is_symlink():
        raise ValueError(f"Refusing to replace symlinked cache cleanup plan: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = dict(plan)
    saved["manifest_path"] = str(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(saved, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return saved


def load_cache_cleanup_plan(plan_path: Path | str) -> dict[str, Any]:
    path = Path(plan_path).expanduser()
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked cache cleanup plan: {plan_path}")
    path = _logical_absolute(path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Cache cleanup plan not found: {plan_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cache cleanup plan is not valid JSON: {plan_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Cache cleanup plan must be a JSON object")
    plan = cast(dict[str, Any], parsed)
    _validate_cache_plan(plan)
    return plan


def load_cache_manifest(manifest_path: Path | str) -> dict[str, Any]:
    path = Path(manifest_path).expanduser()
    if path.is_symlink():
        raise ValueError(f"Refusing symlinked cache manifest: {manifest_path}")
    path = _logical_absolute(path)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Cache manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cache manifest is not valid JSON: {manifest_path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Cache manifest must be a JSON object")
    manifest = cast(dict[str, Any], parsed)
    _validate_cache_manifest(manifest, path)
    return manifest


def _validate_cache_plan(plan: dict[str, Any]) -> None:
    _validate_cache_plan_shape(plan)
    if plan.get("status") == "blocked":
        raise ValueError("Blocked cache cleanup plans cannot be applied")


def _validate_cache_plan_shape(plan: dict[str, Any]) -> None:
    if plan.get("version") != CACHE_PLAN_VERSION:
        raise ValueError("Unsupported cache cleanup plan version")
    for key in ("plan_id", "generated_at", "root_path", "actions"):
        if key not in plan:
            raise ValueError(f"Cache cleanup plan is missing required key: {key}")
    if plan.get("requires_snapshot") is not True:
        raise ValueError("Cache cleanup plan must require snapshot approval")
    if plan.get("mutates_files") is not False:
        raise ValueError("Cache cleanup plan must be read-only")
    if not isinstance(plan["actions"], list):
        raise ValueError("Cache cleanup plan actions must be a list")


def _selected_action_ids(
    plan: dict[str, Any],
    selected_action_ids: list[str] | None,
    all_actions: bool,
) -> list[str]:
    selected = list(selected_action_ids or [])
    if selected and all_actions:
        raise ValueError("Choose explicit cache actions or --all-actions, not both")
    available = [
        str(action["action_id"])
        for action in plan["actions"]
        if isinstance(action, dict)
        and action.get("action_type") == "quarantine_cache_target"
        and action.get("status") == "planned"
    ]
    if all_actions:
        selected = available
    if not selected:
        raise ValueError("Choose at least one cache action")
    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate cache action selected")
    missing = sorted(set(selected) - set(available))
    if missing:
        raise ValueError(f"Unknown or blocked cache action: {', '.join(missing)}")
    return selected


def _operation_id(created_at: str) -> str:
    digits = "".join(character for character in created_at if character.isdigit())
    return f"cache-op-{digits[:8]}-{digits[8:14]}"


def _unique_manifest_path(root: Path, base_operation_id: str) -> tuple[str, Path]:
    manifest_dir = root / CACHE_OPERATION_ROOT_NAME / CACHE_MANIFEST_DIR_NAME
    _reject_symlinked_path(manifest_dir, "symlinked cache manifest root")
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


def _save_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest["updated_at"] = _utc_now()
    return _write_manifest(manifest)


def _validate_cache_manifest(manifest: dict[str, Any], path: Path) -> None:
    if manifest.get("version") != CACHE_MANIFEST_VERSION:
        raise ValueError("Unsupported cache manifest version")
    required = {
        "operation_id",
        "created_at",
        "updated_at",
        "root_path",
        "manifest_path",
        "source_plan",
        "status",
        "mutates_files",
        "actions",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(f"Cache manifest is missing required keys: {', '.join(sorted(missing))}")
    if manifest["status"] not in CACHE_MANIFEST_STATUSES:
        raise ValueError(f"Unknown cache manifest status: {manifest['status']}")
    if _logical_absolute(Path(str(manifest["manifest_path"]))) != path:
        raise ValueError("Cache manifest path does not match loaded path")
    if manifest.get("mutates_files") is not True:
        raise ValueError("Cache manifest must declare file mutation")
    if not isinstance(manifest["actions"], list):
        raise ValueError("Cache manifest actions must be a list")


def _root_from_manifest(manifest: dict[str, Any]) -> Path:
    root = _logical_absolute(Path(str(manifest["root_path"])))
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Cache manifest root path is not a directory: {root}")
    return root


class CacheCleaner:
    """Apply and restore manifest-backed Cache Doctor quarantine operations."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now

    def stage_plan(
        self,
        plan: dict[str, Any],
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        _validate_cache_plan(plan)
        selected = _selected_action_ids(plan, selected_action_ids, all_actions)
        created_at = self._clock()
        root = _logical_absolute(Path(str(plan["root_path"])))
        operation_id, manifest_path = _unique_manifest_path(root, _operation_id(created_at))
        action_by_id = {str(action["action_id"]): action for action in plan["actions"]}
        actions: list[dict[str, Any]] = []
        for action_id in selected:
            planned = action_by_id[action_id]
            relative = _safe_relative_path(str(planned["source_relative_path"]))
            source_path = _logical_absolute(root / relative)
            quarantine_relative = (
                Path(CACHE_OPERATION_ROOT_NAME)
                / CACHE_QUARANTINE_DIR_NAME
                / operation_id
                / relative
            )
            quarantine_path = _logical_absolute(root / quarantine_relative)
            _reject_symlinked_path(source_path, "symlinked cache target")
            actions.append(
                {
                    "action_id": action_id,
                    "action_type": "quarantine_cache_target",
                    "target_id": planned["target_id"],
                    "source_relative_path": relative.as_posix(),
                    "source_path": str(source_path),
                    "quarantine_relative_path": quarantine_relative.as_posix(),
                    "quarantine_path": str(quarantine_path),
                    "expected": planned["expected"],
                    "status": "pending",
                    "error": None,
                }
            )
        manifest = {
            "version": CACHE_MANIFEST_VERSION,
            "operation_id": operation_id,
            "created_at": created_at,
            "updated_at": created_at,
            "root_path": str(root),
            "manifest_path": str(manifest_path),
            "source_plan": {
                "version": int(plan["version"]),
                "plan_id": str(plan["plan_id"]),
                "generated_at": str(plan["generated_at"]),
            },
            "status": "planned",
            "mutates_files": True,
            "actions": actions,
        }
        return _write_manifest(manifest)

    def apply(
        self,
        plan_path: Path | str,
        *,
        selected_action_ids: list[str] | None = None,
        all_actions: bool = False,
    ) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = self.stage_plan(
            load_cache_cleanup_plan(plan_path),
            selected_action_ids=selected_action_ids,
            all_actions=all_actions,
        )
        manifest["status"] = "applying"
        _save_manifest(manifest)
        for action in manifest["actions"]:
            try:
                source = Path(str(action["source_path"]))
                quarantine = Path(str(action["quarantine_path"]))
                if not source.exists():
                    raise ValueError(f"Cache target is missing: {source}")
                _reject_symlinked_path(source, "symlinked cache target")
                _validate_target_identity(source, cast(dict[str, Any], action["expected"]))
                if quarantine.exists():
                    raise ValueError(f"Cache quarantine destination already exists: {quarantine}")
                quarantine.parent.mkdir(parents=True, exist_ok=True)
                action["status"] = "quarantining"
                action["error"] = None
                _save_manifest(manifest)
                shutil.move(str(source), str(quarantine))
                action["status"] = "quarantined"
                action["error"] = None
                _save_manifest(manifest)
            except Exception as exc:
                action["status"] = "blocked"
                action["error"] = str(exc)
                manifest["status"] = "partial"
                _save_manifest(manifest)
                raise
        manifest["status"] = "applied"
        return _save_manifest(manifest)

    def restore(self, manifest_path: Path | str) -> dict[str, Any]:
        assert_sims_not_running()
        manifest = load_cache_manifest(manifest_path)
        if manifest["status"] not in {"applied", "partial", "restoring"}:
            raise ValueError(
                f"Cache operation cannot be restored from status: {manifest['status']}"
            )
        _root_from_manifest(manifest)
        restore_actions = [
            action
            for action in reversed(manifest["actions"])
            if action.get("status") == "quarantined"
        ]
        for action in restore_actions:
            source = Path(str(action["source_path"]))
            quarantine = Path(str(action["quarantine_path"]))
            if source.exists():
                raise ValueError(f"Cache restore destination already exists: {source}")
            if not quarantine.exists():
                raise ValueError(f"Cache quarantine target is missing: {quarantine}")
            _reject_symlinked_path(quarantine, "symlinked cache quarantine")
        manifest["status"] = "restoring"
        _save_manifest(manifest)
        for action in restore_actions:
            try:
                source = Path(str(action["source_path"]))
                quarantine = Path(str(action["quarantine_path"]))
                source.parent.mkdir(parents=True, exist_ok=True)
                action["status"] = "restoring"
                action["error"] = None
                _save_manifest(manifest)
                shutil.move(str(quarantine), str(source))
                action["status"] = "restored"
                action["error"] = None
                _save_manifest(manifest)
            except Exception as exc:
                action["error"] = str(exc)
                manifest["status"] = "partial"
                _save_manifest(manifest)
                raise
        manifest["status"] = "restored"
        return _save_manifest(manifest)


def format_cache_status_text(status: dict[str, Any]) -> str:
    """Format Cache Doctor status for terminal review."""
    lines = [
        "Cache Doctor",
        f"Status: {status.get('status', 'unknown')}",
        f"Root: {status.get('root_path', 'unknown')}",
        "Read-only: yes",
        f"Present targets: {status.get('present_count', 0)}",
        f"Total size: {status.get('total_size_bytes', 0)} bytes",
    ]

    targets = status.get("targets") or []
    present_targets = [target for target in targets if target.get("present")]
    if present_targets:
        lines.append("")
        lines.append("Cache targets:")
        for target in present_targets:
            lines.append(
                f"- {target.get('relative_path')}: {target.get('size_bytes', 0)} bytes, "
                f"{target.get('item_count', 0)} item(s), risk {target.get('risk', 'unknown')}"
            )

    warnings = status.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)

    recommendations = status.get("recommendations") or []
    if recommendations:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in recommendations)

    return "\n".join(lines)
