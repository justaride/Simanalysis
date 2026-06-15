"""Safe Treatment + Auto-Bisect planning and session operations."""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

SESSION_ROOT_NAME = "_Simanalysis_Treatment"
DISABLED_PREFIX = "_Disabled_Simanalysis_Bisect_"
VALID_OUTCOMES = {"same_issue", "issue_gone", "different_issue"}
RESTORABLE_RECORD_STATUSES = {"moving", "moved", "kept_disabled"}
VALID_SESSION_STATUSES = {
    "planned",
    "awaiting_result",
    "confirmed_candidate",
    "inconclusive",
    "blocked",
    "manual_review",
}
SIMS_PROCESS_NAMES = {"the sims 4", "the sims 4.app", "ts4_x64.exe", "ts4_dx9_x64.exe"}
PS_COMMAND = "/bin/ps"


@dataclass(frozen=True)
class Evidence:
    source: str
    finding: str
    reason: str
    path: str


@dataclass(frozen=True)
class TreatmentCandidate:
    unit_path: str
    unit_name: str
    unit_kind: str
    evidence: list[Evidence] = field(default_factory=list)
    rank: int = 100


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_for(dt: datetime) -> str:
    return dt.strftime("%Y%m%d-%H%M%S")


def _is_disabled_segment(name: str) -> bool:
    lowered = name.casefold()
    return lowered.startswith(("_disabled", "_quarantine"))


def _logical_absolute(path: str | Path) -> Path:
    """Absolute path with ``..`` collapsed, but symlinks preserved."""
    return Path(os.path.abspath(Path(path).expanduser()))


def unit_for_path(path: str | Path, mods_dir: str | Path) -> TreatmentCandidate | None:
    mods = _logical_absolute(mods_dir)
    candidate_path = _logical_absolute(path)
    if not candidate_path.exists():
        return None

    try:
        rel = candidate_path.relative_to(mods)
    except ValueError:
        return None
    if not rel.parts:
        return None
    if any(_is_disabled_segment(part) for part in rel.parts):
        return None

    first = mods / rel.parts[0]
    if not first.exists():
        return None
    return TreatmentCandidate(
        unit_path=str(first),
        unit_name=first.name,
        unit_kind="folder" if first.is_dir() else "file",
    )


def _merge_candidate(
    by_path: dict[str, TreatmentCandidate],
    unit: TreatmentCandidate,
    evidence: Evidence,
    rank: int,
) -> None:
    current = by_path.get(unit.unit_path)
    if current is None:
        by_path[unit.unit_path] = TreatmentCandidate(
            unit_path=unit.unit_path,
            unit_name=unit.unit_name,
            unit_kind=unit.unit_kind,
            evidence=[evidence],
            rank=rank,
        )
        return
    by_path[unit.unit_path] = TreatmentCandidate(
        unit_path=current.unit_path,
        unit_name=current.unit_name,
        unit_kind=current.unit_kind,
        evidence=[*current.evidence, evidence],
        rank=min(current.rank, rank),
    )


def _confidence_rank(confidence: str | None) -> int:
    if confidence == "high":
        return 20
    if confidence == "medium":
        return 30
    return 40


def _script_confidence_by_mod(doctor_payload: dict[str, Any]) -> dict[str, str]:
    confidence_by_mod: dict[str, str] = {}
    rank_by_mod: dict[str, int] = {}
    for finding in doctor_payload.get("script_crashes", {}).get("findings", []):
        for suspect in finding.get("suspects", []):
            mod_name = suspect.get("mod")
            if not mod_name or suspect.get("status") != "active":
                continue
            confidence = suspect.get("confidence")
            rank = _confidence_rank(confidence)
            key = str(mod_name).casefold()
            if key not in rank_by_mod or rank < rank_by_mod[key]:
                rank_by_mod[key] = rank
                confidence_by_mod[key] = str(confidence) if confidence else "unknown"
    return confidence_by_mod


def _iter_ts4scripts(root: Path, seen_dirs: set[Path] | None = None) -> list[Path]:
    if seen_dirs is None:
        seen_dirs = set()
    try:
        real_root = root.resolve(strict=True)
    except FileNotFoundError:
        return []
    if real_root in seen_dirs:
        return []
    seen_dirs.add(real_root)

    scripts: list[Path] = []
    for child in root.iterdir():
        if child.is_dir():
            scripts.extend(_iter_ts4scripts(child, seen_dirs))
        elif child.suffix.casefold() == ".ts4script" and child.exists():
            scripts.append(child)
    return scripts


def _find_active_script(mods_dir: Path, mod_name: str) -> Path | None:
    target = mod_name.casefold()
    for path in _iter_ts4scripts(mods_dir):
        try:
            rel = _logical_absolute(path).relative_to(_logical_absolute(mods_dir))
        except ValueError:
            continue
        if any(_is_disabled_segment(part) for part in rel.parts):
            continue
        if path.name.casefold() == target:
            return path
    return None


def candidates_from_doctor(
    doctor_payload: dict[str, Any],
    mods_dir: str | Path,
) -> list[TreatmentCandidate]:
    mods = Path(mods_dir).expanduser().resolve()
    by_path: dict[str, TreatmentCandidate] = {}
    script_confidence = _script_confidence_by_mod(doctor_payload)

    for finding in doctor_payload.get("ui_crashes", {}).get("findings", []):
        if finding.get("status") != "active":
            continue
        report = finding.get("report") or {}
        for hit in finding.get("hits", []):
            if hit.get("status") != "active" or not hit.get("package_path"):
                continue
            unit = unit_for_path(hit["package_path"], mods)
            if unit is None:
                continue
            _merge_candidate(
                by_path,
                unit,
                Evidence(
                    source="ui",
                    finding=str(
                        report.get("source_file") or report.get("signature") or "ui finding"
                    ),
                    reason=str(finding.get("reason") or "active package hit"),
                    path=str(hit["package_path"]),
                ),
                10,
            )

    for ranked in doctor_payload.get("script_crashes", {}).get("ranked_mods", []):
        if ranked.get("status") != "active" or not ranked.get("mod"):
            continue
        script_path = _find_active_script(mods, str(ranked["mod"]))
        if script_path is None:
            continue
        unit = unit_for_path(script_path, mods)
        if unit is None:
            continue
        mod_name = str(ranked["mod"])
        confidence = ranked.get("confidence") or script_confidence.get(mod_name.casefold())
        _merge_candidate(
            by_path,
            unit,
            Evidence(
                source="script",
                finding=mod_name,
                reason=f"active script suspect ({confidence or 'unknown'} confidence)",
                path=str(script_path),
            ),
            _confidence_rank(confidence),
        )

    return sorted(by_path.values(), key=lambda c: (c.rank, c.unit_name.casefold()))


def _base_plan(
    sims4_dir: Path,
    mods_dir: Path,
    doctor_payload: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    candidates = candidates_from_doctor(doctor_payload, mods_dir) if mods_dir.exists() else []
    ts = timestamp_for(now)
    remaining = [candidate.unit_path for candidate in candidates]
    batch_size = (len(remaining) + 1) // 2 if len(remaining) > 1 else len(remaining)
    warnings: list[str] = []
    if not mods_dir.exists():
        warnings.append(f"Mods folder does not exist: {mods_dir}")
    if not candidates:
        warnings.append("No active Doctor candidates can be moved.")

    return {
        "version": 1,
        "session_id": f"bisect-{ts}",
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "sims4_dir": str(sims4_dir),
        "mods_dir": str(mods_dir),
        "disabled_dir": str(sims4_dir / f"{DISABLED_PREFIX}{ts}"),
        "manifest_path": None,
        "status": "planned",
        "active_candidates": [asdict(candidate) for candidate in candidates],
        "remaining_candidates": remaining,
        "current_removed": [],
        "next_batch": remaining[:batch_size],
        "steps": [],
        "warnings": warnings,
        "blockers": [],
    }


def manifest_path_for(sims4_dir: Path, session_id: str) -> Path:
    return sims4_dir / SESSION_ROOT_NAME / f"{session_id}.json"


def _write_session(session: dict[str, Any]) -> dict[str, Any]:
    path = Path(session["manifest_path"])
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
            tmp.write(json.dumps(session, indent=2))
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
        tmp_name = None

        try:
            parent_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return session
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return session


def _require_string(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), str):
        raise ValueError(f"Manifest field {key} must be a string")


def _require_list(data: dict[str, Any], key: str) -> None:
    if not isinstance(data.get(key), list):
        raise ValueError(f"Manifest field {key} must be a list")


def _validate_session_roots(data: dict[str, Any]) -> None:
    sims4 = _logical_absolute(data["sims4_dir"])
    mods = _logical_absolute(data["mods_dir"])
    disabled = _logical_absolute(data["disabled_dir"])
    if mods != sims4 / "Mods":
        raise ValueError("Manifest Mods folder must be the Sims 4 Mods folder")
    if disabled.parent != sims4 or not disabled.name.startswith(DISABLED_PREFIX):
        raise ValueError("Manifest disabled folder must be a Simanalysis bisect folder")


def load_session(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Manifest not found: {manifest_path}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Manifest is not valid JSON: {manifest_path}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Manifest must be a JSON object")
    data = cast(dict[str, Any], parsed)

    if data.get("version") != 1:
        raise ValueError("Unsupported treatment manifest version")
    required = {
        "session_id",
        "sims4_dir",
        "mods_dir",
        "disabled_dir",
        "status",
        "active_candidates",
        "remaining_candidates",
        "current_removed",
        "next_batch",
        "steps",
        "warnings",
        "blockers",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"Manifest is missing required keys: {', '.join(sorted(missing))}")
    for key in ("session_id", "sims4_dir", "mods_dir", "disabled_dir"):
        _require_string(data, key)
    if "manifest_path" in data and data["manifest_path"] is not None:
        _require_string(data, "manifest_path")
    for key in (
        "active_candidates",
        "remaining_candidates",
        "current_removed",
        "next_batch",
        "steps",
        "warnings",
        "blockers",
    ):
        if key in data:
            _require_list(data, key)
    if data["status"] not in VALID_SESSION_STATUSES:
        raise ValueError(f"Unknown treatment session status: {data['status']}")
    _validate_session_roots(data)

    data["manifest_path"] = str(path)
    return data


def assert_sims_not_running() -> None:
    try:
        result = subprocess.run(
            [PS_COMMAND, "-axo", "comm="],  # nosec B603
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            "Refusing to move files because running processes could not be checked"
        ) from exc

    for line in result.stdout.splitlines():
        name = Path(line.strip()).name.casefold()
        if name in SIMS_PROCESS_NAMES:
            raise ValueError("Refusing to move files while The Sims 4 is running")


def _save_loaded(session: dict[str, Any]) -> dict[str, Any]:
    session["updated_at"] = utc_now().isoformat().replace("+00:00", "Z")
    return _write_session(session)


def _candidate_by_path(session: dict[str, Any], unit_path: str) -> dict[str, Any]:
    for candidate in session.get("active_candidates", []):
        if isinstance(candidate, dict) and candidate.get("unit_path") == unit_path:
            return cast(dict[str, Any], candidate)
    raise ValueError(f"Candidate not found in treatment manifest: {unit_path}")


def _next_batch(session: dict[str, Any]) -> list[str]:
    remaining = session.get("remaining_candidates", [])
    if not isinstance(remaining, list):
        raise ValueError("Manifest field remaining_candidates must be a list")
    if len(remaining) <= 1:
        return []
    batch_size = (len(remaining) + 1) // 2
    return [str(path) for path in remaining[:batch_size]]


def _move_records_for(session: dict[str, Any], unit_paths: list[str]) -> list[dict[str, Any]]:
    disabled = Path(str(session["disabled_dir"]))
    records: list[dict[str, Any]] = []
    for unit_path in unit_paths:
        candidate = _candidate_by_path(session, unit_path)
        source = Path(unit_path)
        destination = disabled / source.name
        records.append(
            {
                "unit_path": unit_path,
                "source": unit_path,
                "destination": str(destination),
                "unit_kind": str(candidate.get("unit_kind", "unknown")),
                "status": "pending",
            }
        )
    return records


def apply_next_step(manifest_path: str | Path) -> dict[str, Any]:
    assert_sims_not_running()
    session = load_session(manifest_path)

    batch = _next_batch(session)
    if not batch:
        session["status"] = (
            "confirmed_candidate" if session["remaining_candidates"] else "inconclusive"
        )
        session["next_batch"] = []
        return _save_loaded(session)

    mods = Path(str(session["mods_dir"]))
    disabled = Path(str(session["disabled_dir"]))
    if session["current_removed"]:
        if session["status"] != "planned":
            raise ValueError(
                "Current removed batch must be restored or recorded before applying another step"
            )
        current_removed = {str(path) for path in session["current_removed"]}
        remaining = {str(path) for path in session["remaining_candidates"]}
        if not current_removed.issubset(remaining):
            raise ValueError("Current removed batch is inconsistent with remaining candidates")
        _restore_current_removed_for_next_step(session, mods, disabled)

    removed_units = _move_records_for(session, batch)
    step: dict[str, Any] = {
        "step_id": f"step-{len(session['steps']) + 1}",
        "created_at": utc_now().isoformat().replace("+00:00", "Z"),
        "status": "pending",
        "reason": "bisect first half",
        "removed_units": removed_units,
        "outcome": None,
    }
    session["steps"].append(step)
    _save_loaded(session)

    disabled.mkdir(parents=True, exist_ok=True)

    blocked_record: dict[str, Any] | None = None
    try:
        for record in removed_units:
            blocked_record = record
            source = Path(str(record["source"]))
            destination = Path(str(record["destination"]))
            assert_safe_unit_move(source, destination, mods, disabled)
            record["status"] = "moving"
            moved_unit = str(record["unit_path"])
            if moved_unit not in session["current_removed"]:
                session["current_removed"].append(moved_unit)
            session["status"] = "awaiting_result"
            _save_loaded(session)
            shutil.move(str(source), str(destination))
            record["status"] = "moved"
            _save_loaded(session)
    except Exception:
        if blocked_record is not None:
            destination = Path(str(blocked_record["destination"]))
            source = Path(str(blocked_record["source"]))
            if destination.exists() and not source.exists():
                blocked_record["status"] = "moved"
            else:
                blocked_record["status"] = "blocked"
                _remove_current_removed(
                    session,
                    str(blocked_record.get("unit_path") or blocked_record["source"]),
                )
        step["status"] = "blocked"
        session["status"] = "blocked"
        _save_loaded(session)
        raise

    step["status"] = "applied"
    session["next_batch"] = []
    return _save_loaded(session)


def _restore_record(record: dict[str, Any], mods_dir: Path, disabled_dir: Path) -> None:
    mods_root = Path(mods_dir).expanduser()
    if mods_root.is_symlink():
        raise ValueError(f"Mods folder must not be a symlink: {mods_dir}")
    mods = _logical_absolute(mods_root)
    disabled = _logical_absolute(disabled_dir)
    source = Path(str(record["destination"])).expanduser()
    destination = Path(str(record["source"])).expanduser()
    if not source.exists():
        if record.get("status") == "moving" and destination.exists():
            record["status"] = "restored"
            return
        raise ValueError(f"Restore source is missing: {source}")
    if contains_symlink(source):
        raise ValueError(f"Refusing to restore symlinked unit: {source}")
    if destination.exists():
        raise ValueError(f"Restore destination already exists: {destination}")
    logical_source = _logical_absolute(source)
    logical_destination = _logical_absolute(destination)
    try:
        logical_source.relative_to(disabled)
    except ValueError as exc:
        raise ValueError(f"Restore source is outside active disabled folder: {source}") from exc
    if _logical_absolute(source.parent) != disabled:
        raise ValueError(
            f"Restore source must be a direct child of active disabled folder: {source}"
        )
    try:
        rel_destination = logical_destination.relative_to(mods)
    except ValueError as exc:
        raise ValueError(f"Restore destination is outside Mods folder: {destination}") from exc
    if len(rel_destination.parts) != 1:
        raise ValueError(f"Restore destination must be a direct child of Mods: {destination}")
    if source.is_symlink() or source.parent.is_symlink():
        raise ValueError(f"Restore source must not be a symlink: {source}")
    shutil.move(str(source), str(destination))
    record["status"] = "restored"


def _remove_current_removed(session: dict[str, Any], unit_path: str) -> None:
    session["current_removed"] = [
        path for path in session.get("current_removed", []) if path != unit_path
    ]


def _record_unit_path(record: dict[str, Any]) -> str:
    return str(record.get("unit_path") or record["source"])


def _is_restorable_record(record: dict[str, Any], current_removed: set[str]) -> bool:
    status = record.get("status")
    if status in RESTORABLE_RECORD_STATUSES:
        return True
    if status != "blocked":
        return False
    unit_path = _record_unit_path(record)
    if unit_path not in current_removed:
        return False
    return Path(str(record.get("destination", ""))).expanduser().exists()


def _restore_current_removed_for_next_step(
    session: dict[str, Any],
    mods: Path,
    disabled: Path,
) -> None:
    targets = {str(path) for path in session.get("current_removed", [])}
    restored: set[str] = set()
    blocked_step: dict[str, Any] | None = None
    blocked_record: dict[str, Any] | None = None
    try:
        for restore_step in reversed(session.get("steps", [])):
            if not isinstance(restore_step, dict):
                continue
            blocked_step = restore_step
            step_restored = False
            records = cast(list[dict[str, Any]], restore_step.get("removed_units", []))
            for record in records:
                unit_path = _record_unit_path(record)
                if unit_path not in targets or not _is_restorable_record(record, targets):
                    continue
                blocked_record = record
                _restore_record(record, mods, disabled)
                _remove_current_removed(session, unit_path)
                restored.add(unit_path)
                step_restored = True
                _save_loaded(session)
                blocked_record = None
            if step_restored:
                restore_step["status"] = "restored"
                _save_loaded(session)
        missing = targets - restored
        if missing:
            raise ValueError(
                "Could not find restorable records for current removed candidates: "
                + ", ".join(sorted(missing))
            )
    except Exception:
        if blocked_record is not None:
            blocked_record["status"] = "blocked"
        if blocked_step is not None:
            blocked_step["status"] = "blocked"
        session["status"] = "blocked"
        _save_loaded(session)
        raise


def _latest_step(session: dict[str, Any]) -> dict[str, Any]:
    steps = session.get("steps", [])
    if not steps:
        raise ValueError("Treatment session has no steps")
    latest = steps[-1]
    if not isinstance(latest, dict):
        raise ValueError("Latest treatment step is invalid")
    return cast(dict[str, Any], latest)


def restore_session(manifest_path: str | Path, step: str = "latest") -> dict[str, Any]:
    assert_sims_not_running()
    session = load_session(manifest_path)
    mods = Path(str(session["mods_dir"]))
    disabled = Path(str(session["disabled_dir"]))
    if step == "all":
        steps = list(reversed(session["steps"]))
    elif step == "latest":
        steps = [_latest_step(session)]
    else:
        raise ValueError("Unsupported restore step selector")

    blocked_step: dict[str, Any] | None = None
    blocked_record: dict[str, Any] | None = None
    current_removed = {str(path) for path in session.get("current_removed", [])}
    try:
        for restore_step in steps:
            blocked_step = restore_step
            records = cast(list[dict[str, Any]], restore_step.get("removed_units", []))
            step_restored = False
            for record in records:
                if not _is_restorable_record(record, current_removed):
                    continue
                blocked_record = record
                _restore_record(record, mods, disabled)
                restored_unit = _record_unit_path(record)
                _remove_current_removed(session, restored_unit)
                current_removed.discard(restored_unit)
                step_restored = True
                _save_loaded(session)
                blocked_record = None
            if step_restored:
                restore_step["status"] = "restored"
                _save_loaded(session)
    except Exception:
        if blocked_record is not None:
            blocked_record["status"] = "blocked"
        if blocked_step is not None:
            blocked_step["status"] = "blocked"
        session["status"] = "blocked"
        _save_loaded(session)
        raise

    if session["current_removed"]:
        session["status"] = "blocked"
        _save_loaded(session)
        raise ValueError(
            "Could not restore all current removed candidates: "
            + ", ".join(sorted(str(path) for path in session["current_removed"]))
        )

    latest = _latest_step(session)
    if latest.get("outcome") == "same_issue":
        _finalize_status(session)
    else:
        session["status"] = "planned"
        session["next_batch"] = _next_batch(session)
    return _save_loaded(session)


def _finalize_status(session: dict[str, Any]) -> None:
    remaining = session["remaining_candidates"]
    if len(remaining) == 1:
        session["status"] = "confirmed_candidate"
    elif not remaining:
        session["status"] = "inconclusive"
    else:
        session["status"] = "planned"
    session["next_batch"] = _next_batch(session)


def _quote_command_arg(value: object) -> str:
    return str(value).replace('"', '\\"')


def _count_items(session: dict[str, Any], key: str) -> int:
    value = session.get(key, [])
    return len(value) if isinstance(value, list) else 0


def _append_paths(lines: list[str], paths: list[Any]) -> None:
    if not paths:
        lines.append("- None")
        return
    for path in paths:
        lines.append(f"- `{path}`")


def _append_candidate(lines: list[str], candidate: dict[str, Any]) -> None:
    name = candidate.get("unit_name") or Path(str(candidate.get("unit_path", ""))).name
    kind = candidate.get("unit_kind", "unknown")
    unit_path = candidate.get("unit_path", "")
    lines.append(f"- `{name}` - {kind} - `{unit_path}`")
    evidence_items = candidate.get("evidence", [])
    if not isinstance(evidence_items, list):
        return
    for evidence in evidence_items:
        if not isinstance(evidence, dict):
            continue
        source = evidence.get("source", "unknown")
        finding = evidence.get("finding", "unknown finding")
        reason = evidence.get("reason", "no reason recorded")
        path = evidence.get("path", "")
        lines.append(f"  - Evidence: `{source}` - {finding} - {reason} - `{path}`")


def render_handoff(session: dict[str, Any]) -> str:
    """Render a read-only Markdown handoff for a Treatment/Auto-Bisect session."""
    manifest = session.get("manifest_path") or "(not saved)"
    session_id = session.get("session_id", "unknown")
    status = session.get("status", "unknown")
    manifest_arg = _quote_command_arg(manifest)

    lines = [
        "# Simanalysis Bisect Handoff",
        "",
        "Handoff generation is read-only; it does not move, restore, or edit Sims files.",
        "",
        "## Session",
        f"Session: `{session_id}`",
        f"Status: `{status}`",
        f"Manifest: `{manifest}`",
        f"Sims 4 Folder: `{session.get('sims4_dir', '')}`",
        f"Mods Folder: `{session.get('mods_dir', '')}`",
        f"Disabled Folder: `{session.get('disabled_dir', '')}`",
        f"Created: `{session.get('created_at', 'unknown')}`",
        f"Updated: `{session.get('updated_at', 'unknown')}`",
        "",
        "## Current State",
        f"Candidates: {_count_items(session, 'active_candidates')}",
        f"Remaining: {_count_items(session, 'remaining_candidates')}",
        f"Current Removed: {_count_items(session, 'current_removed')}",
        "",
        "### Next Batch",
    ]
    _append_paths(lines, cast(list[Any], session.get("next_batch", [])))
    lines.extend(["", "### Current Removed"])
    _append_paths(lines, cast(list[Any], session.get("current_removed", [])))

    lines.extend(["", "## Candidates"])
    candidates = session.get("active_candidates", [])
    if isinstance(candidates, list) and candidates:
        for candidate in candidates:
            if isinstance(candidate, dict):
                _append_candidate(lines, candidate)
    else:
        lines.append("- None")

    lines.extend(["", "## Steps"])
    steps = session.get("steps", [])
    if isinstance(steps, list) and steps:
        for step in steps:
            if not isinstance(step, dict):
                continue
            step_id = step.get("step_id", "unknown")
            step_status = step.get("status", "unknown")
            outcome = step.get("outcome") or "pending"
            lines.append(f"- Step `{step_id}` - `{step_status}` - outcome `{outcome}`")
            removed_units = step.get("removed_units", [])
            if not isinstance(removed_units, list):
                continue
            for record in removed_units:
                if not isinstance(record, dict):
                    continue
                name = Path(str(record.get("source", ""))).name
                record_status = record.get("status", "unknown")
                source = record.get("source", "")
                destination = record.get("destination", "")
                lines.append(f"  - `{name}` - `{record_status}` - `{source}` -> `{destination}`")
    else:
        lines.append("- No steps have been applied yet.")

    lines.extend(["", "## Warnings"])
    _append_paths(lines, cast(list[Any], session.get("warnings", [])))
    lines.extend(["", "## Blockers"])
    _append_paths(lines, cast(list[Any], session.get("blockers", [])))

    lines.extend(
        [
            "",
            "## Recovery Commands",
            f'- Inspect: `simanalysis bisect status "{manifest_arg}"`',
            f'- Apply next step: `simanalysis bisect next "{manifest_arg}"`',
            (
                f"- Record same issue: `simanalysis bisect record-verdict "
                f'"{manifest_arg}" --verdict same_issue`'
            ),
            (
                f"- Record issue gone: `simanalysis bisect record-verdict "
                f'"{manifest_arg}" --verdict issue_gone`'
            ),
            (
                f"- Record different issue: `simanalysis bisect record-verdict "
                f'"{manifest_arg}" --verdict different_issue`'
            ),
            f'- Restore latest step: `simanalysis bisect restore "{manifest_arg}"`',
            f'- Restore all: `simanalysis bisect restore "{manifest_arg}" --step all`',
            "",
            "## Trust Notes",
            "- Treat candidates as suspects until a user-recorded game test confirms them.",
            "- Restore or continue only through the manifest-based commands above.",
            "- Do not edit saves; this handoff is for Mods-folder bisection only.",
        ]
    )
    return "\n".join(lines) + "\n"


def record_outcome(manifest_path: str | Path, outcome: str) -> dict[str, Any]:
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"Unsupported treatment outcome: {outcome}")
    assert_sims_not_running()
    session = load_session(manifest_path)
    latest = _latest_step(session)
    if latest.get("status") != "applied":
        raise ValueError("Latest treatment step is not applied")
    latest["outcome"] = outcome

    if outcome == "different_issue":
        session["status"] = "manual_review"
        return _save_loaded(session)

    if outcome == "same_issue":
        removed = list(session["current_removed"])
        session["remaining_candidates"] = [
            path for path in session["remaining_candidates"] if path not in removed
        ]
        _save_loaded(session)
        session = restore_session(manifest_path)
        latest = _latest_step(session)
        latest["outcome"] = "same_issue"
        session["current_removed"] = []
        _finalize_status(session)
        return _save_loaded(session)

    for record in latest.get("removed_units", []):
        if isinstance(record, dict) and record.get("status") == "moved":
            record["status"] = "kept_disabled"
    session["remaining_candidates"] = list(session["current_removed"])
    _finalize_status(session)
    return _save_loaded(session)


def contains_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    if not path.is_dir():
        return False
    return any(child.is_symlink() for child in path.rglob("*"))


def assert_safe_unit_move(
    source: Path,
    destination: Path,
    mods_dir: Path,
    disabled_dir: Path,
) -> None:
    source_path = Path(source).expanduser()
    destination_path = Path(destination).expanduser()
    mods_path = Path(mods_dir).expanduser()
    if mods_path.is_symlink():
        raise ValueError(f"Mods folder must not be a symlink: {mods_dir}")
    mods = _logical_absolute(mods_path)
    disabled_path = Path(disabled_dir).expanduser()
    disabled = _logical_absolute(disabled_path)

    if contains_symlink(source_path):
        raise ValueError(f"Refusing to move symlinked unit: {source}")
    if not source_path.exists():
        raise ValueError(f"Source path is missing: {source}")

    logical_source = _logical_absolute(source_path)
    try:
        rel_source = logical_source.relative_to(mods)
    except ValueError as exc:
        raise ValueError(f"Source is outside Mods folder: {source}") from exc
    if len(rel_source.parts) != 1:
        raise ValueError(f"Source must be a direct child of Mods: {source}")

    if destination_path.exists():
        raise ValueError(f"Destination already exists: {destination}")

    logical_destination_parent = _logical_absolute(destination_path.parent)
    if logical_destination_parent != disabled:
        raise ValueError(f"Destination must be inside active disabled folder: {destination}")
    if not disabled_path.exists() or not disabled_path.is_dir():
        raise ValueError(f"Disabled folder does not exist: {disabled_dir}")
    if disabled_path.is_symlink() or destination_path.parent.is_symlink():
        raise ValueError(f"Disabled folder must not be a symlink: {disabled_dir}")


def create_plan(
    sims4_dir: str | Path,
    mods_dir: str | Path | None,
    doctor_payload: dict[str, Any],
    *,
    save: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    base = Path(sims4_dir).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        raise ValueError(f"Invalid Sims 4 directory path: {sims4_dir}")
    mods = Path(mods_dir).expanduser().resolve() if mods_dir else base / "Mods"
    plan = _base_plan(base, mods, doctor_payload, now=now or utc_now())
    if save:
        manifest = manifest_path_for(base, plan["session_id"])
        plan["manifest_path"] = str(manifest)
        return _write_session(plan)
    return plan
