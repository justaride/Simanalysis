from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.analysis.inventory import scan_mods_dir
from simanalysis.analysis.tuning import extract_tuning_from_xml
from simanalysis.cli import app
from simanalysis.model import TuningNode
from simanalysis.model.graph import DepGraph
from tests.fixtures.xml_samples import basic_interaction


def test_extract_tuning_from_xml(tmp_path: Path, write_file) -> None:
    xml = write_file(tmp_path / "tuning.xml", basic_interaction("Example.Tuning"))

    node = extract_tuning_from_xml(xml)
    assert node is not None
    assert node.tuning_id == "example.tuning"
    assert node.tuning_type == "I"
    assert "example.tuning.loot" in node.references
    assert "example.tuning.test" in node.references


def test_dep_graph_serialization() -> None:
    node = TuningNode(tuning_id="a", tuning_type="I", references=set(), raw_xml="<I />")
    graph = DepGraph()
    graph.add_node(node)
    graph.add_edge("a", "b")
    data = graph.to_json()
    assert any(item["id"] == "a" for item in data["nodes"])
    assert {edge["source"] for edge in data["edges"]} == {"a"}


def test_cli_graph_generates_output(tmp_path: Path, write_file) -> None:
    write_file(tmp_path / "tuning.xml", basic_interaction("Example.Tuning"))

    indexes = scan_mods_dir(tmp_path)
    index_path = tmp_path / "index.json"
    index_payload = [item.model_dump(mode="json") for item in indexes]
    index_path.write_text(json.dumps(index_payload), encoding="utf-8")

    deps_path = tmp_path / "deps.json"
    runner = CliRunner()
    result = runner.invoke(app, ["graph", "--index", str(index_path), "--deps", str(deps_path)])
    assert result.exit_code == 0, result.stdout

    data = json.loads(deps_path.read_text(encoding="utf-8"))
    assert data["nodes"]
    assert data["edges"]
