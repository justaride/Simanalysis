"""Patch Day Shield state and read-only risk classification."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simanalysis.classification import summarize_classifications

PATCH_RISK_CLASSES = (
    ("script_mods", "Script mods"),
    ("ui_mods", "UI mods"),
    ("gameplay_tuning", "Gameplay tuning"),
    ("build_buy_and_cas", "Build/Buy and CAS"),
)

PATCH_RECOMMENDATIONS = (
    "Run a vanilla test before re-enabling mods.",
    "Use a save copy test before opening important saves.",
    "Keep script, UI, gameplay, and tuning mods unknown until reviewed after the patch.",
)


def default_patch_state_path() -> Path:
    """Return the app-owned Patch Day state path."""
    return Path.home() / ".simanalysis" / "patch-day-state.json"


def read_game_version(sims4_dir: Path | str) -> str | None:
    """Read the current Sims 4 game version without mutating the selected folder."""
    version_path = Path(sims4_dir).expanduser().resolve() / "GameVersion.txt"
    if not version_path.exists() or not version_path.is_file():
        return None

    for line in version_path.read_text(encoding="utf-8", errors="replace").splitlines():
        version = line.strip()
        if version:
            return version
    return None


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"version": 1, "roots": {}}
    parsed = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        return {"version": 1, "roots": {}}
    roots = parsed.get("roots")
    if not isinstance(roots, dict):
        parsed["roots"] = {}
    parsed.setdefault("version", 1)
    return parsed


def _write_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _changed_risk_classes(current_version: str, last_known_version: str) -> list[dict[str, str]]:
    reason = f"Game version changed from {last_known_version} to {current_version}."
    return [
        {
            "id": risk_id,
            "label": label,
            "status": "unknown_after_patch",
            "reason": reason,
        }
        for risk_id, label in PATCH_RISK_CLASSES
    ]


def _base_status(
    *,
    sims4_dir: Path,
    state_path: Path,
    current_version: str | None,
    last_known_version: str | None,
    status: str,
    patch_detected: bool,
    risk_classes: list[dict[str, str]],
    recommendations: list[str],
    warnings: list[str],
    classification_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "patch_detected": patch_detected,
        "root_path": str(sims4_dir),
        "state_path": str(state_path),
        "current_game_version": current_version,
        "last_known_game_version": last_known_version,
        "risk_classes": risk_classes,
        "recommendations": recommendations,
        "warnings": warnings,
        "automatic_reenable": False,
    }
    if classification_summary is not None:
        payload["classification_summary"] = classification_summary
    return payload


def build_patch_day_status(
    sims4_dir: Path | str,
    *,
    state_path: Path | str | None = None,
    mods_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Compare current game version with the recorded baseline."""
    root = Path(sims4_dir).expanduser().resolve()
    patch_state = (
        Path(state_path).expanduser().resolve() if state_path else default_patch_state_path()
    )
    current_version = read_game_version(root)
    classification_summary = summarize_classifications(mods_dir) if mods_dir is not None else None

    if current_version is None:
        return _base_status(
            sims4_dir=root,
            state_path=patch_state,
            current_version=None,
            last_known_version=None,
            status="missing_game_version",
            patch_detected=False,
            risk_classes=[],
            recommendations=["Select the Sims 4 user folder that contains GameVersion.txt."],
            warnings=["GameVersion.txt was not found in the selected Sims 4 folder."],
            classification_summary=classification_summary,
        )

    state = _load_state(patch_state)
    record = state.get("roots", {}).get(str(root), {})
    last_known_version = record.get("game_version") if isinstance(record, dict) else None

    if not last_known_version:
        return _base_status(
            sims4_dir=root,
            state_path=patch_state,
            current_version=current_version,
            last_known_version=None,
            status="unrecorded",
            patch_detected=False,
            risk_classes=[],
            recommendations=["Record this game version as the Patch Day baseline."],
            warnings=[],
            classification_summary=classification_summary,
        )

    if current_version != last_known_version:
        return _base_status(
            sims4_dir=root,
            state_path=patch_state,
            current_version=current_version,
            last_known_version=last_known_version,
            status="changed",
            patch_detected=True,
            risk_classes=_changed_risk_classes(current_version, last_known_version),
            recommendations=list(PATCH_RECOMMENDATIONS),
            warnings=[],
            classification_summary=classification_summary,
        )

    return _base_status(
        sims4_dir=root,
        state_path=patch_state,
        current_version=current_version,
        last_known_version=last_known_version,
        status="unchanged",
        patch_detected=False,
        risk_classes=[],
        recommendations=["No patch change detected against the recorded baseline."],
        warnings=[],
        classification_summary=classification_summary,
    )


def record_patch_baseline(
    sims4_dir: Path | str,
    *,
    state_path: Path | str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Record the current game version as the explicit Patch Day baseline."""
    root = Path(sims4_dir).expanduser().resolve()
    patch_state = (
        Path(state_path).expanduser().resolve() if state_path else default_patch_state_path()
    )
    current_version = read_game_version(root)
    if current_version is None:
        raise ValueError("GameVersion.txt was not found in the selected Sims 4 folder.")

    timestamp = recorded_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    state = _load_state(patch_state)
    roots = state.setdefault("roots", {})
    roots[str(root)] = {
        "game_version": current_version,
        "recorded_at": timestamp,
    }
    _write_state(patch_state, state)

    status = build_patch_day_status(root, state_path=patch_state)
    status["status"] = "recorded"
    status["recorded_at"] = timestamp
    return status


def format_patch_day_text(status: dict[str, Any]) -> str:
    """Format Patch Day status for terminal review."""
    lines = [
        "Patch Day Shield",
        f"Status: {status.get('status', 'unknown')}",
        f"Patch detected: {'yes' if status.get('patch_detected') else 'no'}",
        f"Current game version: {status.get('current_game_version') or 'unknown'}",
        f"Last known game version: {status.get('last_known_game_version') or 'none'}",
        "Automatic re-enable: no",
    ]

    risk_classes = status.get("risk_classes") or []
    if risk_classes:
        lines.append("")
        lines.append("Risk classes:")
        for risk in risk_classes:
            label = risk.get("label", risk.get("id", "Unknown"))
            risk_status = risk.get("status", "unknown")
            reason = risk.get("reason")
            suffix = f" - {reason}" if reason else ""
            lines.append(f"- {label}: {risk_status}{suffix}")

    classification_summary = status.get("classification_summary")
    if isinstance(classification_summary, dict):
        label_counts = classification_summary.get("label_counts", {})
        if isinstance(label_counts, dict) and label_counts:
            labels = ", ".join(f"{label}: {count}" for label, count in label_counts.items())
        else:
            labels = "none"
        lines.append("")
        lines.append("Classification evidence:")
        lines.append(
            f"- Files: {classification_summary.get('file_count', 0)} | "
            f"unknown: {classification_summary.get('unknown_count', 0)} | labels: {labels}"
        )
        lines.append("- Automatic safe marking: no")

    recommendations = status.get("recommendations") or []
    if recommendations:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {item}" for item in recommendations)

    warnings = status.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in warnings)

    return "\n".join(lines)
