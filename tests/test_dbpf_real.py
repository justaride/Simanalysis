from __future__ import annotations

import os
from pathlib import Path

import pytest

from simanalysis.io.backends.dbpf_real import RealDBPFReader
from simanalysis.model import ResourceKey

pytestmark = pytest.mark.slow


@pytest.mark.skipif(
    "SIMANALYSIS_DBPF_TOOL" not in os.environ,
    reason="No real DBPF tool configured",
)
def test_real_dbpf_reader_placeholder(tmp_path: Path) -> None:
    tool_path = Path(os.environ["SIMANALYSIS_DBPF_TOOL"])
    reader = RealDBPFReader(tool_path=tool_path)

    with pytest.raises(NotImplementedError):
        list(reader.iter_resources(tmp_path / "package.package"))

    with pytest.raises(NotImplementedError):
        key = ResourceKey(type_id=0, group_id=0, instance_id=0)
        reader.extract_xml(tmp_path / "package.package", key)
