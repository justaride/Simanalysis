from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from simanalysis.analysis.inventory import scan_mods_dir
from simanalysis.cli import app


def test_scan_mods_dir_collects_supported_files(mods_dir: Path, write_file) -> None:
    package = write_file(mods_dir / "mod.package", b"package data")
    xml = write_file(mods_dir / "loose.xml", "<root />")
    py = write_file(mods_dir / "script.py", "print('hi')\n")
    write_file(mods_dir / "ignored.txt", "nope")

    indexes = scan_mods_dir(mods_dir)
    assert {index.package_path for index in indexes} == {package, xml, py}

    xml_index = next(index for index in indexes if index.package_path == xml)
    assert xml_index.entries[0].resource_type == "xml"
    assert xml_index.entries[0].path_in_package == "loose.xml"

    py_index = next(index for index in indexes if index.package_path == py)
    assert py_index.entries[0].resource_type == "py"

    package_index = next(index for index in indexes if index.package_path == package)
    assert package_index.entries == []
    assert len(package_index.sha256) == 64


def test_cli_scan_writes_index(mods_dir: Path, write_file) -> None:
    write_file(mods_dir / "mod.package", b"package")
    out_path = mods_dir.parent / "index.json"

    runner = CliRunner()
    result = runner.invoke(app, ["scan", str(mods_dir), "--out", str(out_path)])
    assert result.exit_code == 0, result.stdout

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
