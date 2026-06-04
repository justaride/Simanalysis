from __future__ import annotations

from pathlib import Path

from simanalysis.world import scan_world


def test_scan_world_indexes_active_disabled_archive_and_game_state(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    creator = mods / "CreatorPack"
    creator.mkdir(parents=True)
    (creator / "alpha.package").write_bytes(b"package-a")
    (creator / "alpha.ts4script").write_bytes(b"script-a")
    (mods / "loose.package").write_bytes(b"loose-package")
    (mods / "notes.txt").write_text("ignore", encoding="utf-8")

    disabled = sims4 / "_Disabled_Broken_20260604"
    disabled.mkdir(parents=True)
    (disabled / "broken.package").write_bytes(b"broken-package")

    quarantined = sims4 / "_Quarantine_UI_Breakage"
    quarantined.mkdir()
    (quarantined / "bad_ui.package").write_bytes(b"bad-ui")

    archive = sims4 / "Archive" / "Import_Staging"
    archive.mkdir(parents=True)
    (archive / "old.ts4script").write_bytes(b"old-script")

    tray = sims4 / "Tray"
    tray.mkdir()
    (tray / "lot.trayitem").write_bytes(b"tray")

    saves = sims4 / "saves"
    saves.mkdir()
    (saves / "Slot_00000001.save").write_bytes(b"save")

    (sims4 / "lastException.txt").write_text("script crash", encoding="utf-8")
    (sims4 / "lastUIException.txt").write_text("ui crash", encoding="utf-8")
    (sims4 / "localthumbcache.package").write_bytes(b"cache")

    world = scan_world(sims4)

    assert world["schema_version"] == 1
    assert world["sims4_dir"] == str(sims4.resolve())
    assert world["summary"] == {
        "active_units": 2,
        "disabled_units": 1,
        "quarantined_units": 1,
        "archived_units": 1,
        "package_files": 4,
        "script_files": 2,
        "tray_files": 1,
        "save_files": 1,
        "log_files": 2,
        "cache_files": 1,
        "warnings": 0,
    }
    assert world["game_state"]["logs"] == [
        {"kind": "script", "name": "lastException.txt", "path": str((sims4 / "lastException.txt").resolve())},
        {"kind": "ui", "name": "lastUIException.txt", "path": str((sims4 / "lastUIException.txt").resolve())},
    ]
    assert [unit["name"] for unit in world["units"]] == [
        "CreatorPack",
        "loose.package",
        "_Disabled_Broken_20260604",
        "_Quarantine_UI_Breakage",
        "Archive",
    ]
    assert [unit["status"] for unit in world["units"]] == [
        "active",
        "active",
        "disabled",
        "quarantined",
        "archived",
    ]
    creator_unit = world["units"][0]
    assert creator_unit["kind"] == "folder"
    assert creator_unit["package_count"] == 1
    assert creator_unit["script_count"] == 1
    assert creator_unit["file_count"] == 2
    assert len(creator_unit["identity"]["sha256"]) == 64


def test_scan_world_is_read_only_and_warns_when_mods_folder_is_missing(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    world = scan_world(sims4)

    assert world["summary"]["active_units"] == 0
    assert world["summary"]["warnings"] == 1
    assert world["warnings"] == ["Mods folder not found"]
    assert not (sims4 / "_Simanalysis_World").exists()
    assert not (sims4 / "_Simanalysis_Treatment").exists()
