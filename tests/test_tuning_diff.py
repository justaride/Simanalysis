from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.analysis.tuning_diff import diff_tuning
from simanalysis.cli import app
from tests.fixtures.xml_samples import basic_interaction, loot_variation


def test_diff_tuning_detects_changes() -> None:
    base = loot_variation("Example", "Foo.Bar")
    updated = basic_interaction("Example", loot_value="Foo.Baz", test_value="Test.Value")

    diff = diff_tuning(base, updated)
    assert diff["added"]["tests"]
    assert any("Test.Value" in snippet for snippet in diff["added"]["tests"])
    assert diff["removed"]["tests"] == []
    assert diff["changed"]["loot"]
    change_entry = diff["changed"]["loot"][0]
    assert "Foo.Bar" in change_entry["from"]
    assert "Foo.Baz" in change_entry["to"]


def test_cli_tuning_diff(tmp_path: Path, write_file) -> None:
    a = write_file(tmp_path / "a.xml", loot_variation("Example", "Foo.Bar"))
    b = write_file(tmp_path / "b.xml", loot_variation("Example", "Foo.Baz"))

    out = tmp_path / "diff.json"
    runner = CliRunner()
    result = runner.invoke(app, ["tuning-diff", "--a", str(a), "--b", str(b), "--out", str(out)])
    assert result.exit_code == 0, result.stdout

    data = json.loads(out.read_text(encoding="utf-8"))
    assert "Foo.Bar" in json.dumps(data)
