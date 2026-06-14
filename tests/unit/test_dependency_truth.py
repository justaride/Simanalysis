"""Dependency declaration truth tests."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def _requirement_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_runtime_requirements_defer_to_pyproject() -> None:
    """requirements.txt must not reintroduce stale runtime dependencies."""
    lines = _requirement_lines(REPO_ROOT / "requirements.txt")

    assert lines == ["-e ."]


def test_dev_requirements_defer_to_pyproject_extras() -> None:
    """requirements-dev.txt must install pyproject extras instead of a parallel list."""
    lines = _requirement_lines(REPO_ROOT / "requirements-dev.txt")

    assert lines == ["-e .[dev,docs]"]


def test_legacy_unimported_dependencies_are_not_declared() -> None:
    """Old generated requirements must not claim unused top-level packages."""
    combined = "\n".join(
        (
            (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8"),
            (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8"),
        )
    ).lower()

    for stale_name in ("numpy", "pandas", "dbpf", "anthropic", "black"):
        assert stale_name not in combined
