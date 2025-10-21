from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.analysis.conflicts import find_duplicate_keys, format_conflicts
from simanalysis.cli import app
from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey

_DEF_SHA = "0" * 64


def _package(path: Path, *keys: ResourceKey) -> PackageIndex:
    entries = [
        ResourceEntry(key=key, resource_type="xml", size=10, path_in_package="file.xml")
        for key in keys
    ]
    return PackageIndex(package_path=path, entries=entries, sha256=_DEF_SHA)


def test_find_duplicate_keys(tmp_path: Path) -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    indexes = [
        _package(tmp_path / "a.package", key),
        _package(tmp_path / "b.package", key),
        _package(tmp_path / "c.package", ResourceKey(type_id=4, group_id=5, instance_id=6)),
    ]

    duplicates = find_duplicate_keys(indexes)
    assert key in duplicates
    assert duplicates[key] == [tmp_path / "a.package", tmp_path / "b.package"]


def test_format_conflicts_outputs_table(tmp_path: Path) -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    conflicts = {key: [tmp_path / "a.package", tmp_path / "b.package"]}
    text = format_conflicts(conflicts)
    assert "Duplicate resources" in text
    assert str(key) in text


def test_cli_conflicts_writes_report(tmp_path: Path) -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    indexes = [_package(tmp_path / "a.package", key), _package(tmp_path / "b.package", key)]
    index_path = tmp_path / "index.json"
    index_payload = [index.model_dump(mode="json") for index in indexes]
    index_path.write_text(json.dumps(index_payload), encoding="utf-8")

    report_path = tmp_path / "report.txt"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["conflicts", "--index", str(index_path), "--report", str(report_path)],
    )
    assert result.exit_code == 0, result.stdout
    assert str(key) in report_path.read_text(encoding="utf-8")
