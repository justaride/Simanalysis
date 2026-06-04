"""Local intelligence foundation for Sims 4 mod stewardship."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from simanalysis.treatment import timestamp_for, utc_now
from simanalysis.world import scan_world

MASTER_ROOT_NAME = "_Simanalysis_MasterPlan"
LATEST_BASELINE_NAME = "latest-catalog-baseline.json"
HEAVY_UNIT_BYTES = 2 * 1024 * 1024
SCRIPT_PRESSURE_COUNT = 100
PACKAGE_PRESSURE_COUNT = 10_000
UNIT_PRESSURE_COUNT = 300
GENERIC_CREATOR_TOKENS = {
    "cas",
    "cc",
    "custom",
    "merged",
    "mod",
    "mods",
    "package",
    "script",
    "set",
    "the",
    "ts4",
    "unknown",
}
VERSION_RE = re.compile(r"(?:^|[\s_.-])v?(\d+(?:[\s_.-]\d+){0,3})(?=$|[\s_.-])", re.IGNORECASE)


def create_master_plan(sims4_dir: str | Path) -> dict[str, Any]:
    """Create a read-only intelligence plan across update, performance, and creator lanes."""
    world = scan_world(sims4_dir)
    active_units = [unit for unit in world["units"] if unit["status"] == "active"]
    catalog_entries = [_catalog_entry(unit) for unit in active_units]
    update_candidates = _update_candidates(catalog_entries)
    performance = _performance_lane(world, active_units)
    creators = _creator_lane(catalog_entries)

    return {
        "schema_version": 1,
        "sims4_dir": world["sims4_dir"],
        "summary": {
            "active_units": len(active_units),
            "catalog_entries": len(catalog_entries),
            "creator_profiles": len(creators["profiles"]),
            "performance_actions": len(performance["actions"]),
            "update_candidates": len(update_candidates),
            "warnings": len(world["warnings"]),
        },
        "updates": {
            "candidates": update_candidates,
            "status_counts": _status_counts(catalog_entries),
        },
        "catalog": {
            "entries": catalog_entries,
        },
        "performance": performance,
        "creators": creators,
        "warnings": world["warnings"],
        "blockers": [],
    }


def master_status(sims4_dir: str | Path) -> dict[str, Any]:
    """Return a compact read-only status summary for the master plan."""
    plan = create_master_plan(sims4_dir)
    return {
        "schema_version": plan["schema_version"],
        "sims4_dir": plan["sims4_dir"],
        "summary": plan["summary"],
        "warnings": plan["warnings"],
        "blockers": plan["blockers"],
    }


def save_master_baseline(sims4_dir: str | Path, label: str | None = None) -> dict[str, Any]:
    """Persist the current catalog as a Simanalysis-owned baseline manifest."""
    base = _require_sims_dir(sims4_dir)
    plan = create_master_plan(base)
    now = utc_now()
    ts = timestamp_for(now)
    root = base / MASTER_ROOT_NAME
    baseline_path = root / f"catalog-baseline-{ts}.json"
    latest_path = root / LATEST_BASELINE_NAME
    baseline = {
        "schema_version": 1,
        "kind": "master_catalog_baseline",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "label": label,
        "sims4_dir": str(base),
        "baseline_path": str(baseline_path),
        "latest_baseline_path": str(latest_path),
        "summary": plan["summary"],
        "catalog": plan["catalog"],
        "warnings": plan["warnings"],
        "blockers": plan["blockers"],
    }
    _write_json_atomic(baseline_path, baseline)
    _write_json_atomic(latest_path, baseline)
    return baseline


def diff_master_baseline(
    sims4_dir: str | Path,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare the current catalog against a saved baseline."""
    base = _require_sims_dir(sims4_dir)
    baseline = load_master_baseline(base, baseline_path)
    plan = create_master_plan(base)
    current_entries = plan["catalog"]["entries"]
    baseline_entries = baseline["catalog"]["entries"]
    current_by_path = {str(entry["relative_path"]): entry for entry in current_entries}
    baseline_by_path = {str(entry["relative_path"]): entry for entry in baseline_entries}

    added = [
        current_by_path[key]
        for key in sorted(current_by_path.keys() - baseline_by_path.keys(), key=str.casefold)
    ]
    removed = [
        baseline_by_path[key]
        for key in sorted(baseline_by_path.keys() - current_by_path.keys(), key=str.casefold)
    ]
    changed = [
        {
            "relative_path": key,
            "baseline": baseline_by_path[key],
            "current": current_by_path[key],
            "reasons": _change_reasons(baseline_by_path[key], current_by_path[key]),
        }
        for key in sorted(current_by_path.keys() & baseline_by_path.keys(), key=str.casefold)
        if baseline_by_path[key]["unit_id"] != current_by_path[key]["unit_id"]
    ]
    unchanged = [
        key
        for key in sorted(current_by_path.keys() & baseline_by_path.keys(), key=str.casefold)
        if baseline_by_path[key]["unit_id"] == current_by_path[key]["unit_id"]
    ]

    return {
        "schema_version": 1,
        "sims4_dir": str(base),
        "baseline_path": baseline["baseline_path"],
        "baseline_created_at": baseline["created_at"],
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "warnings": len(plan["warnings"]) + len(baseline.get("warnings", [])),
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "warnings": [*baseline.get("warnings", []), *plan["warnings"]],
        "blockers": [],
    }


def master_baseline_status(sims4_dir: str | Path) -> dict[str, Any]:
    """Return compact diff status for the latest baseline if present."""
    base = _require_sims_dir(sims4_dir)
    latest_path = base / MASTER_ROOT_NAME / LATEST_BASELINE_NAME
    if not latest_path.exists():
        return {
            "schema_version": 1,
            "sims4_dir": str(base),
            "baseline_exists": False,
            "baseline_path": None,
            "summary": {
                "added": 0,
                "removed": 0,
                "changed": 0,
                "unchanged": 0,
                "warnings": 0,
            },
            "warnings": [],
            "blockers": ["No master baseline found"],
        }
    diff = diff_master_baseline(base, latest_path)
    return {
        "schema_version": 1,
        "sims4_dir": str(base),
        "baseline_exists": True,
        "baseline_path": diff["baseline_path"],
        "baseline_created_at": diff["baseline_created_at"],
        "summary": diff["summary"],
        "warnings": diff["warnings"],
        "blockers": diff["blockers"],
    }


def load_master_baseline(
    sims4_dir: str | Path,
    baseline_path: str | Path | None = None,
) -> dict[str, Any]:
    base = _require_sims_dir(sims4_dir)
    path = Path(baseline_path).expanduser() if baseline_path else base / MASTER_ROOT_NAME / LATEST_BASELINE_NAME
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Master baseline not found: {path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Master baseline is not valid JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Master baseline must be a JSON object")
    data = parsed
    _validate_baseline(data)
    data["baseline_path"] = str(path)
    return data


def _catalog_entry(unit: dict[str, Any]) -> dict[str, Any]:
    version = _version_signal(unit)
    creator = _infer_creator(unit)
    update_status = "tracked"
    if not version and int(unit["script_count"]) > 0:
        update_status = "needs_version_tracking"
    elif not version:
        update_status = "local_only"

    return {
        "unit_id": unit["unit_id"],
        "unit_name": unit["name"],
        "creator": creator,
        "version_signal": version,
        "update_status": update_status,
        "package_count": unit["package_count"],
        "script_count": unit["script_count"],
        "file_count": unit["file_count"],
        "total_size_bytes": unit["total_size_bytes"],
        "path": unit["path"],
        "relative_path": unit["relative_path"],
    }


def _update_candidates(catalog_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entry in catalog_entries:
        if entry["update_status"] != "needs_version_tracking":
            continue
        candidates.append(
            {
                "unit_id": entry["unit_id"],
                "unit_name": entry["unit_name"],
                "reason": "script_mod_without_version_signal",
                "severity": "medium",
                "suggested_action": "Add this script mod to the update catalog before changing more mods.",
            }
        )
    return candidates


def _performance_lane(world: dict[str, Any], active_units: list[dict[str, Any]]) -> dict[str, Any]:
    total_size_bytes = sum(int(unit["total_size_bytes"]) for unit in active_units)
    heavy_units = [
        {
            "unit_id": unit["unit_id"],
            "unit_name": unit["name"],
            "total_size_bytes": unit["total_size_bytes"],
            "package_count": unit["package_count"],
            "script_count": unit["script_count"],
            "path": unit["path"],
        }
        for unit in active_units
        if int(unit["total_size_bytes"]) >= HEAVY_UNIT_BYTES
    ]
    heavy_units.sort(key=lambda item: (-int(item["total_size_bytes"]), str(item["unit_name"]).casefold()))

    summary = world["summary"]
    actions: list[dict[str, Any]] = []
    if heavy_units:
        actions.append(
            {
                "kind": "large_unit_review",
                "severity": "medium",
                "title": "Review large active mod units",
                "count": len(heavy_units),
            }
        )
    if int(summary["script_files"]) >= SCRIPT_PRESSURE_COUNT:
        actions.append(
            {
                "kind": "script_pressure_review",
                "severity": "high",
                "title": "Review script-mod load pressure",
                "count": summary["script_files"],
            }
        )
    if int(summary["package_files"]) >= PACKAGE_PRESSURE_COUNT:
        actions.append(
            {
                "kind": "package_pressure_review",
                "severity": "medium",
                "title": "Review package-file count pressure",
                "count": summary["package_files"],
            }
        )
    if len(active_units) >= UNIT_PRESSURE_COUNT:
        actions.append(
            {
                "kind": "active_unit_pressure_review",
                "severity": "medium",
                "title": "Review active folder/unit count",
                "count": len(active_units),
            }
        )

    return {
        "summary": {
            "active_units": len(active_units),
            "total_size_bytes": total_size_bytes,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "package_files": summary["package_files"],
            "script_files": summary["script_files"],
        },
        "heavy_units": heavy_units[:25],
        "actions": actions,
    }


def _creator_lane(catalog_entries: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in catalog_entries:
        grouped[str(entry["creator"])].append(entry)

    profiles: list[dict[str, Any]] = [
        {
            "creator": creator,
            "unit_count": len(entries),
            "package_count": sum(int(entry["package_count"]) for entry in entries),
            "script_count": sum(int(entry["script_count"]) for entry in entries),
            "total_size_bytes": sum(int(entry["total_size_bytes"]) for entry in entries),
            "units": [entry["unit_name"] for entry in entries[:20]],
        }
        for creator, entries in grouped.items()
    ]
    profiles.sort(
        key=lambda profile: (
            -int(profile["script_count"]),
            -int(profile["unit_count"]),
            str(profile["creator"]).casefold(),
        )
    )
    return {
        "profiles": profiles,
        "unknown_units": [entry for entry in catalog_entries if entry["creator"] == "Unknown"],
    }


def _status_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "tracked": 0,
        "needs_version_tracking": 0,
        "local_only": 0,
    }
    for entry in entries:
        status = str(entry["update_status"])
        if status in counts:
            counts[status] += 1
    return counts


def _version_signal(unit: dict[str, Any]) -> str | None:
    names = [_unit_source_name(str(unit["name"]))]
    names.extend(_unit_source_name(str(file_record["name"])) for file_record in unit["files"])
    for name in names:
        match = VERSION_RE.search(name)
        if match:
            return re.sub(r"[\s_-]+", ".", match.group(1))
    return None


def _infer_creator(unit: dict[str, Any]) -> str:
    source = _strip_version(_unit_source_name(str(unit["name"]))).strip(" _-.")
    bracket_match = re.match(r"^\[([^\]]+)]", source)
    if bracket_match:
        token = bracket_match.group(1).strip()
    else:
        token = re.split(r"\s+-\s+|[_\s]+", source, maxsplit=1)[0].strip()
    if len(token) < 3 or token.casefold() in GENERIC_CREATOR_TOKENS:
        return "Unknown"
    return token


def _strip_version(name: str) -> str:
    return VERSION_RE.sub(" ", name)


def _unit_source_name(name: str) -> str:
    path = Path(name)
    return path.stem if path.suffix.lower() in {".package", ".ts4script"} else name


def _change_reasons(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in ("version_signal", "package_count", "script_count", "file_count", "total_size_bytes"):
        if baseline.get(key) != current.get(key):
            reasons.append(key)
    if not reasons:
        reasons.append("identity")
    return reasons


def _validate_baseline(data: dict[str, Any]) -> None:
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported master baseline schema version")
    if data.get("kind") != "master_catalog_baseline":
        raise ValueError("Unsupported master baseline kind")
    for key in ("created_at", "sims4_dir", "baseline_path", "latest_baseline_path"):
        if not isinstance(data.get(key), str):
            raise ValueError(f"Master baseline field {key} must be a string")
    catalog = data.get("catalog")
    if not isinstance(catalog, dict) or not isinstance(catalog.get("entries"), list):
        raise ValueError("Master baseline catalog entries must be a list")
    for key in ("warnings", "blockers"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"Master baseline field {key} must be a list")


def _require_sims_dir(path: str | Path) -> Path:
    base = Path(path).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Invalid Sims 4 directory path: {path}")
    return base


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
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
            tmp.write(json.dumps(data, indent=2))
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
