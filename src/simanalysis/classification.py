"""Conservative Sims mod file classification.

Classification is evidence for review surfaces only. It must not mark mods as
safe after a patch, and it must not execute mod code.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from simanalysis.formats.types import (
    CASP,
    COBJ,
    GEOM,
    MLOD,
    MODL,
    OBJD,
    STBL,
    BinaryResourceType,
    TuningResourceType,
    is_tuning_type,
    type_name,
)
from simanalysis.parsers.dbpf import DBPFReader

CLASSIFICATION_LABELS = (
    "cas",
    "build_buy",
    "gameplay_tuning",
    "ui",
    "script",
    "localization",
    "default_replacement",
    "animation",
    "dependency",
    "unknown",
)

_CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}
_LABEL_TIEBREAK = {
    "script": 90,
    "cas": 80,
    "build_buy": 70,
    "gameplay_tuning": 60,
    "ui": 55,
    "localization": 50,
    "animation": 45,
    "default_replacement": 30,
    "dependency": 20,
    "unknown": 0,
}

_CAS_RESOURCE_TYPES = {
    int(CASP),
    int(BinaryResourceType.CasPartThumbnail),
    int(BinaryResourceType.CasPreset),
    int(TuningResourceType.CasMenu),
    int(TuningResourceType.CasMenuItem),
    int(TuningResourceType.CasPreferenceCategory),
    int(TuningResourceType.CasPreferenceItem),
    int(TuningResourceType.CasStoriesAnswer),
    int(TuningResourceType.CasStoriesQuestion),
    int(TuningResourceType.CasStoriesTraitChooser),
}
_BUILD_BUY_RESOURCE_TYPES = {
    int(OBJD),
    int(COBJ),
    int(BinaryResourceType.ObjectCatalogSet),
    int(BinaryResourceType.Footprint),
    int(BinaryResourceType.Light),
    int(BinaryResourceType.Slot),
    int(MODL),
    int(MLOD),
    int(GEOM),
    int(TuningResourceType.LotDecoration),
    int(TuningResourceType.LotDecorationPreset),
    int(TuningResourceType.LotTuning),
    int(TuningResourceType.Object),
    int(TuningResourceType.ObjectPart),
    int(TuningResourceType.ObjectState),
    int(TuningResourceType.SlotType),
    int(TuningResourceType.SlotTypeSet),
}
_UI_RESOURCE_TYPES = {
    int(TuningResourceType.PieMenuCategory),
    int(TuningResourceType.UserInterfaceInfo),
}
_LOCALIZATION_RESOURCE_TYPES = {int(STBL)}
_ANIMATION_RESOURCE_TYPES = {
    int(TuningResourceType.Animation),
    int(BinaryResourceType.AnimationStateMachine),
    int(BinaryResourceType.Rig),
}


def _signal(
    signal_id: str,
    label: str,
    confidence: str,
    evidence: str,
    *,
    resource_type: int | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    signal: dict[str, Any] = {
        "id": signal_id,
        "label": label,
        "confidence": confidence,
        "evidence": evidence,
    }
    if resource_type is not None:
        signal["resource_type"] = f"0x{resource_type:08x}"
        signal["resource_type_name"] = type_name(resource_type)
    if count is not None:
        signal["count"] = count
    return signal


def _label_for_resource_type(resource_type: int) -> str | None:
    value = int(resource_type)
    if value in _CAS_RESOURCE_TYPES:
        return "cas"
    if value in _BUILD_BUY_RESOURCE_TYPES:
        return "build_buy"
    if value in _UI_RESOURCE_TYPES:
        return "ui"
    if value in _LOCALIZATION_RESOURCE_TYPES:
        return "localization"
    if value in _ANIMATION_RESOURCE_TYPES:
        return "animation"
    if is_tuning_type(value) or value == int(BinaryResourceType.CombinedTuning):
        return "gameplay_tuning"
    return None


def _path_text(path: Path, relative_path: str | None) -> str:
    return (relative_path or path.as_posix()).casefold().replace("\\", "/")


def _weak_path_signals(path: Path, relative_path: str | None) -> list[dict[str, Any]]:
    text = _path_text(path, relative_path)
    signals: list[dict[str, Any]] = []
    if any(token in text for token in ("default replacement", "default_replacement")) or any(
        token in text for token in ("/overrides/", "/override/", " override")
    ):
        signals.append(
            _signal(
                "path_hint",
                "default_replacement",
                "medium",
                "Path or filename suggests an override/default replacement.",
            )
        )
    if any(token in text for token in ("dependency", "required", "/core", " core.", "/lib")):
        signals.append(
            _signal(
                "path_hint",
                "dependency",
                "low",
                "Path or filename suggests a required dependency/core library.",
            )
        )
    if any(token in text for token in ("buildbuy", "build_buy", "/ui/", "ui.package")):
        signals.append(
            _signal(
                "path_hint",
                "ui",
                "medium",
                "Path or filename suggests UI-related content.",
            )
        )
    return signals


def _resource_signals(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reader = DBPFReader(path)
    resource_counts = Counter(int(resource.type) for resource in reader.read_index())
    resource_type_counts = [
        {
            "resource_type": f"0x{resource_type:08x}",
            "resource_type_name": type_name(resource_type),
            "count": count,
        }
        for resource_type, count in sorted(resource_counts.items())
    ]
    signals = [
        _signal(
            "resource_type",
            label,
            "high",
            f"Package contains {type_name(resource_type)} resource(s).",
            resource_type=resource_type,
            count=count,
        )
        for resource_type, count in sorted(resource_counts.items())
        if (label := _label_for_resource_type(resource_type)) is not None
    ]
    return signals, resource_type_counts


def _choose_label(signals: list[dict[str, Any]]) -> tuple[str, str]:
    if not signals:
        return "unknown", "unknown"
    best = max(
        signals,
        key=lambda signal: (
            _CONFIDENCE_RANK.get(str(signal.get("confidence")), 0),
            _LABEL_TIEBREAK.get(str(signal.get("label")), 0),
        ),
    )
    label = str(best.get("label") or "unknown")
    confidence = str(best.get("confidence") or "unknown")
    if label not in CLASSIFICATION_LABELS:
        return "unknown", "unknown"
    return label, confidence


def classify_file(path: Path | str, *, relative_path: str | None = None) -> dict[str, Any]:
    """Classify one file without mutating it or executing mod code."""
    file_path = Path(path)
    extension = file_path.suffix.lower()
    signals: list[dict[str, Any]] = []
    resource_type_counts: list[dict[str, Any]] = []

    if extension == ".ts4script":
        signals.append(
            _signal(
                "ts4script_extension",
                "script",
                "high",
                "File extension is .ts4script; contents are not executed.",
            )
        )
    elif extension == ".package":
        try:
            resource_signals, resource_type_counts = _resource_signals(file_path)
            signals.extend(resource_signals)
        except Exception as exc:
            signals.append(
                _signal(
                    "package_parse_error",
                    "unknown",
                    "unknown",
                    f"Package resource index could not be read: {exc}",
                )
            )

    signals.extend(_weak_path_signals(file_path, relative_path))
    label, confidence = _choose_label(
        [signal for signal in signals if signal.get("label") != "unknown"]
    )
    if label == "unknown":
        confidence = "unknown"

    return {
        "label": label,
        "confidence": confidence,
        "signals": signals,
        "resource_type_counts": resource_type_counts,
        "automatic_safe_marking": False,
    }


def summarize_classifications(root: Path | str) -> dict[str, Any]:
    """Return a compact classification summary for a Mods-like folder."""
    base = Path(root).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        return {
            "status": "missing",
            "root_path": str(base),
            "file_count": 0,
            "label_counts": {},
            "unknown_count": 0,
            "items": [],
            "automatic_safe_marking": False,
        }

    items: list[dict[str, Any]] = []
    for file_path in sorted(base.rglob("*"), key=lambda candidate: candidate.as_posix().casefold()):
        if file_path.is_symlink() or not file_path.is_file():
            continue
        relative_path = file_path.relative_to(base).as_posix()
        classification = classify_file(file_path, relative_path=relative_path)
        items.append(
            {
                "name": file_path.name,
                "relative_path": relative_path,
                "path": str(file_path),
                "classification": classification,
            }
        )

    label_counts = Counter(str(item["classification"]["label"]) for item in items)
    return {
        "status": "available",
        "root_path": str(base),
        "file_count": len(items),
        "label_counts": dict(sorted(label_counts.items())),
        "unknown_count": int(label_counts.get("unknown", 0)),
        "items": items,
        "automatic_safe_marking": False,
    }
