"""Tests for read-only Cache Doctor status."""

import json
from pathlib import Path

from click.testing import CliRunner

from simanalysis.cache_doctor import build_cache_status, format_cache_status_text
from simanalysis.cli import cli


def test_cache_status_reports_present_cache_targets_without_mutating(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    thumb = sims4 / "localthumbcache.package"
    thumb.write_bytes(b"thumb-cache")
    cache_dir = sims4 / "cache"
    cache_dir.mkdir()
    (cache_dir / "cached.bin").write_bytes(b"cached")

    status = build_cache_status(sims4)

    assert status["status"] == "review_recommended"
    assert status["root_path"] == str(sims4.resolve())
    targets = {target["id"]: target for target in status["targets"]}
    assert targets["localthumbcache"]["present"] is True
    assert targets["localthumbcache"]["size_bytes"] == len(b"thumb-cache")
    assert targets["cache_dir"]["present"] is True
    assert targets["cache_dir"]["item_count"] == 1
    assert status["mutates_files"] is False
    assert thumb.exists()
    assert (cache_dir / "cached.bin").exists()
    assert any("Operating Table" in item for item in status["recommendations"])


def test_cache_status_is_clear_when_known_targets_are_absent(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    status = build_cache_status(sims4)

    assert status["status"] == "no_cache_targets_found"
    assert all(target["present"] is False for target in status["targets"])
    assert status["recommendations"] == [
        "No known Sims 4 cache targets were found in the selected folder."
    ]


def test_cache_status_skips_symlinked_cache_targets(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    external = tmp_path / "external-cache"
    external.mkdir()
    (sims4 / "cache").symlink_to(external, target_is_directory=True)

    status = build_cache_status(sims4)

    cache_target = next(target for target in status["targets"] if target["id"] == "cache_dir")
    assert cache_target["present"] is False
    assert cache_target["status"] == "skipped_symlink"
    assert any("symlink" in warning.lower() for warning in status["warnings"])


def test_format_cache_status_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "localthumbcache.package").write_bytes(b"cache")

    text = format_cache_status_text(build_cache_status(sims4))

    assert "Cache Doctor" in text
    assert "Read-only: yes" in text
    assert "localthumbcache.package" in text


def test_cache_cli_status_outputs_json(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "avatarcache.package").write_bytes(b"avatar")

    result = CliRunner().invoke(cli, ["cache", "status", str(sims4), "--format", "json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert any(target["id"] == "avatarcache" for target in data["targets"])
