"""Conflict detection utilities."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from simanalysis.model import PackageIndex, ResourceKey


def find_duplicate_keys(indexes: Iterable[PackageIndex]) -> dict[ResourceKey, list[Path]]:
    """Return resource keys that appear in more than one package."""

    occurrences: dict[ResourceKey, set[Path]] = defaultdict(set)
    for package in indexes:
        package_path = package.package_path
        for entry in package.entries:
            occurrences[entry.key].add(package_path)

    duplicates: dict[ResourceKey, list[Path]] = {}
    for key, paths in occurrences.items():
        if len(paths) >= 2:
            duplicates[key] = sorted(paths)
    return duplicates


def format_conflicts(conflicts: dict[ResourceKey, list[Path]]) -> str:
    """Format duplicate resource conflicts for display."""

    if not conflicts:
        return "No duplicate resources detected."

    lines = ["Duplicate resources detected:"]
    for key in sorted(conflicts, key=str):
        lines.append(f"- {key}")
        for path in conflicts[key]:
            lines.append(f"    • {path}")
    return "\n".join(lines)
