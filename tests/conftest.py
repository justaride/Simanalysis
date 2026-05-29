"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path

import pytest

# Ensure the worktree's src directory is first on sys.path so that editable
# installs from other checkouts of the same package do not shadow our code.
_WORKTREE_SRC = str(Path(__file__).parent.parent / "src")
if _WORKTREE_SRC not in sys.path:
    sys.path.insert(0, _WORKTREE_SRC)


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_mods_dir(fixtures_dir: Path) -> Path:
    """Get the sample mods directory path."""
    return fixtures_dir / "sample_mods"


@pytest.fixture
def mock_data_dir(fixtures_dir: Path) -> Path:
    """Get the mock data directory path."""
    return fixtures_dir / "mock_data"


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path
