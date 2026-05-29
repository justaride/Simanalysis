"""Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


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
