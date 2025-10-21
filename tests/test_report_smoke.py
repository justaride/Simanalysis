from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.cli import app
from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey
from simanalysis.reporting.report import render_report


def test_render_report_smoke(tmp_path: Path) -> None:
    package = tmp_path / "mod.package"
    package.write_bytes(b"content")
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    entry = ResourceEntry(key=key, resource_type="xml", size=10, path_in_package="file.xml")
    index = PackageIndex(package_path=package, entries=[entry], sha256="0" * 64)

    html = render_report(
        [index],
        {key: [package]},
        {"nodes": [], "edges": []},
        conflict_text="Sample",
    )
    assert "<html" in html.lower()
    assert "Sample" in html


def test_cli_report_generates_file(tmp_path: Path) -> None:
    index_path = tmp_path / "index.json"
    package = tmp_path / "mod.package"
    package.write_bytes(b"content")
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    entry = ResourceEntry(key=key, resource_type="xml", size=10, path_in_package="file.xml")
    index = PackageIndex(package_path=package, entries=[entry], sha256="0" * 64)
    index_payload = [index.model_dump(mode="json") for index in [index]]
    index_path.write_text(json.dumps(index_payload), encoding="utf-8")

    conflicts_path = tmp_path / "conflicts.txt"
    conflicts_path.write_text("No conflicts", encoding="utf-8")

    deps_path = tmp_path / "deps.json"
    deps_path.write_text(json.dumps({"nodes": [], "edges": []}), encoding="utf-8")

    out_path = tmp_path / "report.html"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "report",
            "--index",
            str(index_path),
            "--conflicts",
            str(conflicts_path),
            "--deps",
            str(deps_path),
            "--out",
            str(out_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "<html" in out_path.read_text(encoding="utf-8").lower()
