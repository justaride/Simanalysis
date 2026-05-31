"""Safe Treatment + Auto-Bisect planning and session operations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

SESSION_ROOT_NAME = "_Simanalysis_Treatment"
DISABLED_PREFIX = "_Disabled_Simanalysis_Bisect_"
VALID_OUTCOMES = {"same_issue", "issue_gone", "different_issue"}


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
                    finding=str(report.get("source_file") or report.get("signature") or "ui finding"),
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
        "steps",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"Manifest is missing required keys: {', '.join(sorted(missing))}")

    data["manifest_path"] = str(path)
    return data


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
    mods = _logical_absolute(mods_dir)
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
