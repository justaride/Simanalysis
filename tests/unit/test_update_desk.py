"""Tests for read-only Update Desk staging status."""

import json
from pathlib import Path
from zipfile import ZipFile

from click.testing import CliRunner

from simanalysis.cli import cli
from simanalysis.update_desk import (
    build_update_staging_status,
    format_update_staging_text,
)


def test_update_staging_status_classifies_downloads_and_source_bindings(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Simanalysis Staging"
    staging.mkdir()
    archive = staging / "cool_mod.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("Mods/cool.package", b"package")
    (staging / "cool_mod.zip.source.json").write_text(
        json.dumps(
            {
                "source_url": "https://example.test/cool",
                "creator": "Example Creator",
                "downloaded_at": "2026-06-15T07:00:00Z",
            }
        )
    )
    package = staging / "loose.package"
    script = staging / "helper.ts4script"
    package.write_bytes(b"package")
    script.write_bytes(b"script")

    status = build_update_staging_status(staging)

    assert status["status"] == "review_recommended"
    assert status["staging_path"] == str(staging.resolve())
    assert status["item_count"] == 3
    assert status["archive_count"] == 1
    assert status["package_count"] == 1
    assert status["script_count"] == 1
    assert status["mutates_files"] is False
    items = {item["name"]: item for item in status["items"]}
    assert items["cool_mod.zip"]["kind"] == "archive"
    assert items["cool_mod.zip"]["archive_scan"]["status"] == "readable_zip"
    assert items["cool_mod.zip"]["archive_scan"]["member_count"] == 1
    assert items["cool_mod.zip"]["source_binding"]["status"] == "bound"
    assert items["loose.package"]["source_binding"]["status"] == "missing"
    assert package.exists()
    assert script.exists()
    assert archive.exists()


def test_update_staging_status_surfaces_archive_path_escape(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    archive = staging / "unsafe.zip"
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escape.package", b"package")

    status = build_update_staging_status(staging)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert "archive_path_escape" in signal_ids
    item = status["items"][0]
    assert item["archive_scan"]["status"] == "unsafe_members"
    assert item["archive_scan"]["unsafe_members"] == ["../escape.package"]
    assert archive.exists()


def test_update_staging_status_surfaces_corrupt_archives_and_path_safety(
    tmp_path: Path,
) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "broken.zip").write_bytes(b"not a zip")
    (staging / "._broken.zip").write_bytes(b"appledouble")
    (staging / "download.package.icloud").write_bytes(b"icloud")
    external = tmp_path / "external.package"
    external.write_bytes(b"external")
    (staging / "linked.package").symlink_to(external)

    status = build_update_staging_status(staging)

    signal_ids = {signal["id"] for signal in status["signals"]}
    assert {
        "archive_unreadable",
        "appledouble_noise",
        "icloud_placeholder",
        "symlink_skipped",
    } <= signal_ids
    assert status["item_count"] == 1
    assert status["items"][0]["archive_scan"]["status"] == "unreadable_zip"


def test_update_staging_status_reports_missing_staging_folder(tmp_path: Path) -> None:
    staging = tmp_path / "Missing Staging"

    status = build_update_staging_status(staging)

    assert status["status"] == "missing_staging_folder"
    assert status["item_count"] == 0
    assert status["signals"][0]["id"] == "missing_staging_folder"
    assert status["mutates_files"] is False


def test_format_update_staging_text_surfaces_read_only_boundary(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    text = format_update_staging_text(build_update_staging_status(staging))

    assert "Update Desk" in text
    assert "Read-only: yes" in text
    assert "loose.package" in text


def test_update_staging_status_cli_outputs_json(tmp_path: Path) -> None:
    staging = tmp_path / "Staging"
    staging.mkdir()
    (staging / "loose.package").write_bytes(b"package")

    result = CliRunner().invoke(
        cli,
        ["updates", "status", str(staging), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "review_recommended"
    assert data["package_count"] == 1
    assert data["mutates_files"] is False
