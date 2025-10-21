from __future__ import annotations

from pathlib import Path

import pytest

from simanalysis.io import DummyDBPFReader, get_dbpf_reader
from simanalysis.model import ResourceKey


def test_dummy_reader_logs_and_returns_empty(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    package = tmp_path / "test.package"
    package.write_bytes(b"")

    reader = DummyDBPFReader()
    caplog.set_level("WARNING")
    assert list(reader.iter_resources(package)) == []
    assert "dummy" in caplog.text.lower()

    caplog.clear()
    key = ResourceKey(type_id=0, group_id=0, instance_id=0)
    reader.extract_xml(package, key)
    assert "cannot extract" in caplog.text.lower()


def test_get_dbpf_reader_variants() -> None:
    reader = get_dbpf_reader()
    assert isinstance(reader, DummyDBPFReader)

    reader_auto = get_dbpf_reader("auto")
    assert isinstance(reader_auto, DummyDBPFReader)

    with pytest.raises(ValueError):
        get_dbpf_reader("unknown")  # type: ignore[arg-type]
