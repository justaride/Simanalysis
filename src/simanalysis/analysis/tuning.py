"""Tuning extraction utilities."""

from __future__ import annotations

import re
from pathlib import Path

from simanalysis.io.xml_loader import find_attr, parse_xml
from simanalysis.model import TuningNode, normalize_tuning_id

_REFERENCE_PATTERN = re.compile(r"[a-zA-Z0-9_.:]+")


def extract_tuning_from_xml(path: Path) -> TuningNode | None:
    """Extract tuning metadata from an XML file."""

    if not path.exists():
        return None

    raw_xml = path.read_text(encoding="utf-8")
    root = parse_xml(raw_xml)
    tag = root.tag.split("}")[-1]

    tuning_ids = find_attr(root, "//I", "n") or find_attr(root, "//T", "n")
    if not tuning_ids:
        return None

    tuning_id = normalize_tuning_id(tuning_ids[0])

    references: set[str] = set()
    for match in _REFERENCE_PATTERN.finditer(raw_xml):
        token = match.group(0)
        if token == "":
            continue
        normalized = normalize_tuning_id(token)
        if normalized and normalized != tuning_id and ("." in token or ":" in token):
            references.add(normalized)

    return TuningNode(
        tuning_id=tuning_id,
        tuning_type=tag,
        references=references,
        raw_xml=raw_xml,
    )
