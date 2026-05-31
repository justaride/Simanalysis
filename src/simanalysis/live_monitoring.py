"""Read-only live monitoring for Sims 4 crash logs."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

LOG_GLOBS = (("script", "lastException*.txt"), ("ui", "lastUIException*.txt"))
DoctorBuilder = Callable[[Path, Path, bool], dict[str, Any]]
TreatmentPlanner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class DiscoveredLog:
    kind: str
    path: Path


@dataclass(frozen=True)
class LogFingerprint:
    path: str
    name: str
    kind: str
    size: int
    mtime_ns: int
    digest: str

    def to_event(self) -> dict[str, object]:
        return asdict(self)


def discover_log_files(sims4_dir: str | Path) -> list[DiscoveredLog]:
    base = Path(sims4_dir).expanduser().resolve()
    logs: list[DiscoveredLog] = []
    for kind, pattern in LOG_GLOBS:
        for path in sorted(base.glob(pattern), key=lambda item: item.name.casefold()):
            if path.is_file():
                logs.append(DiscoveredLog(kind=kind, path=path.resolve()))
    return logs


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def fingerprint_log(discovered: DiscoveredLog) -> LogFingerprint:
    stat = discovered.path.stat()
    return LogFingerprint(
        path=str(discovered.path),
        name=discovered.path.name,
        kind=discovered.kind,
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        digest=_digest_file(discovered.path),
    )


def build_snapshot(sims4_dir: str | Path) -> tuple[dict[str, LogFingerprint], list[str]]:
    snapshot: dict[str, LogFingerprint] = {}
    warnings: list[str] = []
    for discovered in discover_log_files(sims4_dir):
        try:
            fingerprint = fingerprint_log(discovered)
        except OSError as exc:
            warnings.append(f"Could not read {discovered.path.name}: {exc}")
            continue
        snapshot[fingerprint.path] = fingerprint
    return snapshot, warnings


def changed_fingerprints(
    previous: dict[str, LogFingerprint],
    current: dict[str, LogFingerprint],
) -> list[LogFingerprint]:
    changed = [
        fingerprint
        for path, fingerprint in current.items()
        if previous.get(path) != fingerprint
    ]
    return sorted(changed, key=lambda item: (item.kind, item.name.casefold()))


def _empty_treatment_summary() -> dict[str, object]:
    return {
        "candidate_count": 0,
        "first_batch_count": 0,
        "manifest_path": None,
        "warnings": [],
        "blockers": [],
    }


def _doctor_has_evidence(summary: dict[str, Any]) -> bool:
    return any(
        int(summary.get(key, 0) or 0) > 0
        for key in (
            "script_reports",
            "script_disabled",
            "script_not_installed",
            "script_base_game_only",
            "ui_findings",
            "ui_disabled",
            "ui_not_found",
            "ui_no_key",
        )
    )


def _doctor_needs_review(summary: dict[str, Any]) -> bool:
    return any(
        int(summary.get(key, 0) or 0) > 0
        for key in ("script_active", "ui_active", "parse_errors", "index_errors")
    )


def _treatment_summary(plan: dict[str, Any]) -> dict[str, object]:
    return {
        "candidate_count": len(plan.get("active_candidates", [])),
        "first_batch_count": len(plan.get("next_batch", [])),
        "manifest_path": plan.get("manifest_path"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _recommended_action(
    changed: list[LogFingerprint],
    doctor_summary: dict[str, Any],
    treatment: dict[str, object],
) -> str:
    if not changed:
        return "waiting"
    if int(treatment.get("candidate_count", 0) or 0) > 0:
        return "open_treatment"
    if _doctor_needs_review(doctor_summary):
        return "review_doctor"
    if _doctor_has_evidence(doctor_summary):
        return "no_movable_candidates"
    return "review_doctor"


class LiveMonitor:
    def __init__(
        self,
        sims4_dir: str | Path,
        mods_dir: str | Path | None = None,
        *,
        initial_snapshot: dict[str, LogFingerprint] | None = None,
    ) -> None:
        self.sims4_dir = Path(sims4_dir).expanduser().resolve()
        self.mods_dir = (
            Path(mods_dir).expanduser().resolve()
            if mods_dir is not None
            else self.sims4_dir / "Mods"
        )
        if initial_snapshot is None:
            self.snapshot, self.startup_warnings = build_snapshot(self.sims4_dir)
        else:
            self.snapshot = dict(initial_snapshot)
            self.startup_warnings = []

    def poll(
        self,
        doctor_builder: DoctorBuilder,
        treatment_planner: TreatmentPlanner,
    ) -> dict[str, Any]:
        current, warnings = build_snapshot(self.sims4_dir)
        changed = changed_fingerprints(self.snapshot, current)
        self.snapshot = current
        all_warnings = [*self.startup_warnings, *warnings]
        self.startup_warnings = []

        if not changed:
            return {
                "changed_logs": [],
                "watched_log_count": len(current),
                "doctor_summary": {},
                "treatment": _empty_treatment_summary(),
                "recommended_next_action": "waiting",
                "warnings": all_warnings,
            }

        doctor_payload = doctor_builder(self.sims4_dir, self.mods_dir, False)
        doctor_summary = dict(doctor_payload.get("summary", {}))
        try:
            plan = treatment_planner(
                self.sims4_dir,
                self.mods_dir,
                doctor_payload,
                save=False,
            )
            treatment = _treatment_summary(plan)
        except Exception as exc:
            treatment = _empty_treatment_summary()
            treatment["warnings"] = [f"Treatment planning failed: {exc}"]

        return {
            "changed_logs": [fingerprint.to_event() for fingerprint in changed],
            "watched_log_count": len(current),
            "doctor_summary": doctor_summary,
            "treatment": treatment,
            "recommended_next_action": _recommended_action(changed, doctor_summary, treatment),
            "warnings": all_warnings,
        }
