from pathlib import Path

import pytest

from simanalysis.analyzer import ModAnalyzer


def test_analyze_directory_counts_packages_and_scripts(tmp_path: Path) -> None:
    (tmp_path / "mod_a.package").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "mod_b.ts4script").touch()

    analyzer = ModAnalyzer()
    result = analyzer.analyze_directory(tmp_path)

    assert result.total_mods == 2
    assert pytest.approx(result.performance_score, 0.1) == 99.0
    assert not result.has_conflicts()


def test_analyze_requires_directory(tmp_path: Path) -> None:
    analyzer = ModAnalyzer()

    with pytest.raises(FileNotFoundError):
        analyzer.analyze_directory(tmp_path / "missing")

    file_path = tmp_path / "file.txt"
    file_path.write_text("content")

    with pytest.raises(NotADirectoryError):
        analyzer.analyze_directory(file_path)


def test_analyze_uses_constructor_path(tmp_path: Path) -> None:
    (tmp_path / "mod.package").touch()

    analyzer = ModAnalyzer(mod_path=tmp_path)
    result = analyzer.analyze()

    assert result.total_mods == 1
