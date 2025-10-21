"""HTML reporting utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, PackageLoader, select_autoescape

from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey

_ENV = Environment(
    loader=PackageLoader("simanalysis", "templates"),
    autoescape=select_autoescape(["html", "xml"]),
)


def _entry_payload(entry: ResourceEntry) -> dict[str, str | int | None]:
    return {
        "key": str(entry.key),
        "resource_type": entry.resource_type,
        "size": entry.size,
        "path_in_package": entry.path_in_package,
    }


def render_report(
    indexes: Iterable[PackageIndex],
    conflicts: dict[ResourceKey, list[Path]],
    deps_graph_json: dict,
    conflict_text: str | None = None,
) -> str:
    """Render an HTML report summarizing scan results."""

    indexes_list = list(indexes)
    summary = {
        "packages": len(indexes_list),
        "resources": sum(len(index.entries) for index in indexes_list),
        "conflicts": len(conflicts),
    }
    packages = [
        {
            "path": str(index.package_path),
            "sha256": index.sha256,
            "entry_count": len(index.entries),
            "entries": [_entry_payload(entry) for entry in index.entries],
        }
        for index in indexes_list
    ]
    conflict_rows = [
        {
            "key": str(key),
            "packages": [str(path) for path in paths],
        }
        for key, paths in sorted(conflicts.items(), key=lambda item: str(item[0]))
    ]

    template = _ENV.get_template("report.html.j2")
    return template.render(
        summary=summary,
        packages=packages,
        conflicts=conflict_rows,
        deps_json=json.dumps(deps_graph_json),
        conflict_text=conflict_text,
    )
