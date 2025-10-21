from pathlib import Path

from pytest import CaptureFixture

from simanalysis import __version__
from simanalysis.cli import app


def test_cli_version_option(capsys: CaptureFixture[str]) -> None:
    assert app(["--version"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == __version__


def test_cli_analyze_reports_totals(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "a.package").touch()

    result = app(["analyze", str(tmp_path / "mods")])
    assert result == 0
    captured = capsys.readouterr()
    assert "Total mods discovered: 1" in captured.out
