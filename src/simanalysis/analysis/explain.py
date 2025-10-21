"""Conflict explanation helpers."""

from __future__ import annotations

import datetime as dt
from typing import Iterable

from simanalysis.analysis.tuning_diff import diff_tuning
from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey


def _describe_entry(package: PackageIndex, entry: ResourceEntry) -> str:
    path = package.package_path
    try:
        stats = path.stat()
        size = f"{stats.st_size} bytes"
        modified = dt.datetime.fromtimestamp(stats.st_mtime).isoformat(timespec="seconds")
    except OSError:
        size = "unknown"
        modified = "unknown"
    detail_line = (
        "  resource type: "
        f"{entry.resource_type or 'unknown'}, "
        f"in-package path: {entry.path_in_package or '-'}, "
        f"payload size: {entry.size} bytes"
    )
    return "\n".join([f"- {path} (file size: {size}, modified: {modified})", detail_line])


def _summarize_diff(diff: dict) -> list[str]:
    lines: list[str] = []
    for category in ("added", "removed"):
        for section, items in diff[category].items():
            if items:
                lines.append(f"  {category.title()} {len(items)} {section} node(s)")
    for section, changes in diff["changed"].items():
        for change in changes[:3]:
            snippet_from = change["from"].split("\n", 1)[0]
            snippet_to = change["to"].split("\n", 1)[0]
            lines.append(f"  Changed {section}: {snippet_from} -> {snippet_to}")
        if len(changes) > 3:
            lines.append(f"  ... and {len(changes) - 3} more {section} change(s)")
    return lines


def explain_conflict(indexes: Iterable[PackageIndex], key: ResourceKey) -> str:
    """Return a human-readable explanation for a resource conflict."""

    matches: list[tuple[PackageIndex, ResourceEntry]] = []
    for package in indexes:
        for entry in package.entries:
            if entry.key == key:
                matches.append((package, entry))

    if not matches:
        return f"No packages contain resource {key}."

    lines = [f"Resource {key} is present in {len(matches)} package(s):"]
    for package, entry in matches:
        lines.append(_describe_entry(package, entry))

    xml_matches = [
        (package, entry)
        for package, entry in matches
        if entry.resource_type == "xml" and package.package_path.exists()
    ]
    if len(xml_matches) >= 2:
        base_package, base_entry = xml_matches[0]
        try:
            base_xml = base_package.package_path.read_text(encoding="utf-8")
        except OSError:
            base_xml = None
        if base_xml:
            lines.append("")
            lines.append("Tuning differences:")
            for other_package, _ in xml_matches[1:]:
                try:
                    other_xml = other_package.package_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                diff = diff_tuning(base_xml, other_xml)
                lines.append(f"- Compared with {other_package.package_path}:")
                diff_lines = _summarize_diff(diff)
                if diff_lines:
                    lines.extend(diff_lines)
                else:
                    lines.append("  No structural differences detected.")
    return "\n".join(lines)
