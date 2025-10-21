from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT.parent / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture
def write_file() -> Callable[[Path, str | bytes], Path]:
    def _write(path: Path, content: str | bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write


@pytest.fixture
def mods_dir(tmp_path: Path) -> Path:
    mods = tmp_path / "Mods"
    mods.mkdir()
    return mods
