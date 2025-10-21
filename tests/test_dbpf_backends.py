from __future__ import annotations

from pathlib import Path

import pytest

from simanalysis.io import ExternalCLIReader, get_dbpf_reader
from simanalysis.model import ResourceKey


def test_external_backend_requires_cli_path(tmp_path: Path) -> None:
    cli = tmp_path / "cli.exe"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")

    reader = get_dbpf_reader("external", cli_path=cli)
    assert isinstance(reader, ExternalCLIReader)

    with pytest.raises(FileNotFoundError):
        get_dbpf_reader("external", cli_path=tmp_path / "missing.exe")

    with pytest.raises(ValueError):
        get_dbpf_reader("external", cli_path=tmp_path)


def test_external_backend_methods_unimplemented(tmp_path: Path) -> None:
    cli = tmp_path / "cli.exe"
    cli.write_text("#!/bin/sh\n", encoding="utf-8")

    reader = get_dbpf_reader("external", cli_path=cli)

    with pytest.raises(NotImplementedError):
        list(reader.iter_resources(tmp_path / "package.package"))

    with pytest.raises(NotImplementedError):
        key = ResourceKey(type_id=0, group_id=0, instance_id=0)
        reader.extract_xml(tmp_path / "package.package", key)
