"""Lightweight tuning diff helpers."""

from __future__ import annotations

from collections import defaultdict

from lxml import etree

from simanalysis.io.xml_loader import parse_xml

_TARGETS = {
    "loot": "//T[@n='loot']/T",
    "interaction": "//I[@n='interaction']/*",
    "tests": "//L[@n='tests']/*",
}


def _collect_signatures(xml_str: str) -> dict[str, dict[str, str]]:
    root = parse_xml(xml_str)
    signatures: dict[str, dict[str, str]] = {}
    for key, xpath in _TARGETS.items():
        seen: dict[str, str] = {}
        counters: dict[str, int] = defaultdict(int)
        for node in root.xpath(xpath):
            if not isinstance(node, etree._Element):
                continue
            node_key = node.get("n") or node.tag
            counters[node_key] += 1
            unique_key = node_key if counters[node_key] == 1 else f"{node_key}#{counters[node_key]}"
            seen[unique_key] = etree.tostring(node, encoding="unicode").strip()
        signatures[key] = seen
    return signatures


def _diff_category(a: dict[str, str], b: dict[str, str]) -> dict[str, list]:
    added_keys = sorted(set(b) - set(a))
    removed_keys = sorted(set(a) - set(b))
    common_keys = sorted(set(a) & set(b))
    changed = [
        {"key": key, "from": a[key], "to": b[key]} for key in common_keys if a[key] != b[key]
    ]
    return {
        "added": [b[key] for key in added_keys],
        "removed": [a[key] for key in removed_keys],
        "changed": changed,
    }


def diff_tuning(a_xml: str, b_xml: str) -> dict[str, dict[str, list]]:
    """Compute heuristic diffs between two tuning XML payloads."""

    a_signatures = _collect_signatures(a_xml)
    b_signatures = _collect_signatures(b_xml)

    diff: dict[str, dict[str, list]] = {}
    for category in _TARGETS:
        diff[category] = _diff_category(
            a_signatures.get(category, {}),
            b_signatures.get(category, {}),
        )
    return {
        "added": {category: diff[category]["added"] for category in diff},
        "removed": {category: diff[category]["removed"] for category in diff},
        "changed": {category: diff[category]["changed"] for category in diff},
    }
