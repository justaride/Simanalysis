from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.analysis.explain import explain_conflict
from simanalysis.cli import app
from simanalysis.model import PackageIndex, ResourceEntry, ResourceKey
from tests.fixtures.xml_samples import basic_interaction

_DEF_SHA = "0" * 64


def _index_for(path: Path, key: ResourceKey) -> PackageIndex:
    entry = ResourceEntry(
        key=key,
        resource_type="xml",
        size=path.stat().st_size,
        path_in_package=path.name,
    )
    return PackageIndex(package_path=path, entries=[entry], sha256=_DEF_SHA)


def test_explain_conflict_summarizes_packages(tmp_path: Path, write_file) -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    xml_a = write_file(tmp_path / "a.xml", basic_interaction("Example", loot_value="Foo.Bar"))
    xml_b = write_file(tmp_path / "b.xml", basic_interaction("Example", loot_value="Foo.Baz"))

    explanation = explain_conflict([_index_for(xml_a, key), _index_for(xml_b, key)], key)
    assert str(xml_a) in explanation
    assert "Foo.Bar" in explanation or "Foo.Baz" in explanation


def test_cli_explain(tmp_path: Path, write_file) -> None:
    key = ResourceKey(type_id=1, group_id=2, instance_id=3)
    xml_a = write_file(tmp_path / "a.xml", basic_interaction("Example", loot_value="Foo.Bar"))
    xml_b = write_file(tmp_path / "b.xml", basic_interaction("Example", loot_value="Foo.Baz"))

    indexes = [_index_for(xml_a, key), _index_for(xml_b, key)]
    index_path = tmp_path / "index.json"
    index_payload = [idx.model_dump(mode="json") for idx in indexes]
    index_path.write_text(json.dumps(index_payload), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["explain", "--index", str(index_path), "--key", str(key)],
    )
    assert result.exit_code == 0, result.stdout
    assert "Resource" in result.stdout
