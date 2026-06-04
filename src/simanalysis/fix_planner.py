"""Read-only fix planning built on the Sims 4 world inventory."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from simanalysis.world import scan_world

Severity = str

SEVERITY_ORDER: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}


def create_fix_plan(sims4_dir: str | Path) -> dict[str, Any]:
    """Create a read-only plan of reviewable fix candidates."""
    world = scan_world(sims4_dir)
    actions = [
        *_script_depth_actions(world),
        *_active_duplicate_actions(world),
        *_disabled_shadow_actions(world),
        *_cache_actions(world),
    ]
    actions = sorted(
        _dedupe_actions(actions),
        key=lambda action: (
            SEVERITY_ORDER.get(str(action["severity"]), 9),
            str(action["kind"]),
            str(action["title"]).casefold(),
        ),
    )

    return {
        "schema_version": 1,
        "sims4_dir": world["sims4_dir"],
        "dry_run": True,
        "summary": {
            "actions": len(actions),
            "high": _count_severity(actions, "high"),
            "medium": _count_severity(actions, "medium"),
            "low": _count_severity(actions, "low"),
            "warnings": len(world["warnings"]),
            "blockers": 0,
        },
        "actions": actions,
        "warnings": world["warnings"],
        "blockers": [],
    }


def fix_status(sims4_dir: str | Path) -> dict[str, Any]:
    """Return a compact status view for the fix plan."""
    plan = create_fix_plan(sims4_dir)
    return {
        "schema_version": plan["schema_version"],
        "sims4_dir": plan["sims4_dir"],
        "dry_run": plan["dry_run"],
        "summary": plan["summary"],
        "warnings": plan["warnings"],
        "blockers": plan["blockers"],
    }


def _count_severity(actions: list[dict[str, Any]], severity: Severity) -> int:
    return sum(1 for action in actions if action["severity"] == severity)


def _script_depth_actions(world: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for unit in world["units"]:
        if unit["status"] != "active":
            continue
        for file_record in unit["files"]:
            if file_record["suffix"] != ".ts4script":
                continue
            relative = Path(str(file_record["relative_path"]))
            parts = relative.parts
            if len(parts) <= 3 or parts[0] != "Mods":
                continue
            actions.append(
                _action(
                    kind="script_too_deep",
                    severity="high",
                    title=f"Script mod may be too deep: {file_record['name']}",
                    body=(
                        "The Sims 4 may not load script mods reliably when the .ts4script "
                        "file is nested more than one folder below Mods."
                    ),
                    target_paths=[str(file_record["path"])],
                    evidence=[
                        {
                            "reason": "script depth",
                            "relative_path": str(file_record["relative_path"]),
                            "depth": len(parts) - 1,
                        }
                    ],
                )
            )
    return actions


def _active_duplicate_actions(world: dict[str, Any]) -> list[dict[str, Any]]:
    by_signature: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for unit in world["units"]:
        if unit["status"] != "active":
            continue
        for file_record in unit["files"]:
            signature = (
                str(file_record["name"]).casefold(),
                str(file_record["suffix"]),
                int(file_record["size_bytes"]),
            )
            by_signature[signature].append(file_record)

    actions: list[dict[str, Any]] = []
    for (_name, suffix, _size), records in by_signature.items():
        if len(records) < 2:
            continue
        display_name = str(records[0]["name"])
        actions.append(
            _action(
                kind="active_duplicate_file",
                severity="medium",
                title=f"Active duplicate {suffix} file: {display_name}",
                body=(
                    "Multiple active mod files have the same name and size. This is a "
                    "review candidate, not proof that either file should be removed."
                ),
                target_paths=[str(record["path"]) for record in records],
                evidence=[
                    {
                        "reason": "same active filename and size",
                        "name": display_name,
                        "size_bytes": records[0]["size_bytes"],
                        "count": len(records),
                    }
                ],
            )
        )
    return actions


def _disabled_shadow_actions(world: dict[str, Any]) -> list[dict[str, Any]]:
    active_by_signature: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    inactive_by_signature: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for unit in world["units"]:
        for file_record in unit["files"]:
            signature = (
                str(file_record["name"]).casefold(),
                str(file_record["suffix"]),
                int(file_record["size_bytes"]),
            )
            if unit["status"] == "active":
                active_by_signature[signature].append(file_record)
            elif unit["status"] in {"disabled", "quarantined", "archived"}:
                inactive_by_signature[signature].append(file_record)

    actions: list[dict[str, Any]] = []
    for signature, active_records in active_by_signature.items():
        inactive_records = inactive_by_signature.get(signature, [])
        if not inactive_records:
            continue
        display_name = str(active_records[0]["name"])
        actions.append(
            _action(
                kind="disabled_shadow_copy",
                severity="medium",
                title=f"Active file also exists outside Mods: {display_name}",
                body=(
                    "A same-named same-size copy exists in disabled, quarantine, or archive "
                    "storage. Keep it for rollback unless you intentionally consolidate later."
                ),
                target_paths=[
                    *[str(record["path"]) for record in active_records],
                    *[str(record["path"]) for record in inactive_records],
                ],
                evidence=[
                    {
                        "reason": "active and inactive same filename and size",
                        "active_count": len(active_records),
                        "inactive_count": len(inactive_records),
                    }
                ],
            )
        )
    return actions


def _cache_actions(world: dict[str, Any]) -> list[dict[str, Any]]:
    caches = world.get("game_state", {}).get("caches", [])
    if not caches:
        return []
    return [
        _action(
            kind="cache_cleanup_candidate",
            severity="low",
            title="Cache files are present",
            body=(
                "Cache cleanup can be useful after mod changes, but this plan does not "
                "delete anything. Review cache cleanup only when the game is closed."
            ),
            target_paths=[str(cache["path"]) for cache in caches],
            evidence=[{"reason": "cache artifact", "count": len(caches)}],
            proposed_operation="move_to_simanalysis_cache_backup",
            can_apply=True,
        )
    ]


def _dedupe_actions(actions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for action in actions:
        key = str(action["action_id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return unique


def _action(
    *,
    kind: str,
    severity: Severity,
    title: str,
    body: str,
    target_paths: list[str],
    evidence: list[dict[str, Any]],
    proposed_operation: str = "review",
    can_apply: bool = False,
) -> dict[str, Any]:
    normalized_paths = sorted(target_paths, key=str.casefold)
    action_id = _action_id(kind, normalized_paths)
    return {
        "action_id": action_id,
        "kind": kind,
        "severity": severity,
        "title": title,
        "body": body,
        "target_paths": normalized_paths,
        "proposed_operation": proposed_operation,
        "can_apply": can_apply,
        "safety": "read_only_plan",
        "evidence": evidence,
    }


def _action_id(kind: str, target_paths: list[str]) -> str:
    digest = hashlib.sha256()
    digest.update(kind.encode("utf-8"))
    for path in target_paths:
        digest.update(b"\0")
        digest.update(path.encode("utf-8"))
    return f"fix-{kind}-{digest.hexdigest()[:12]}"
