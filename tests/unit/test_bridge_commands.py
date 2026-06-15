# mypy: disable-error-code="no-untyped-def"
import argparse
import io
import json
from typing import Any

import pytest

from simanalysis.bridge import commands
from simanalysis.bridge.protocol import Emitter


def test_scan_mods_drives_emitter_in_order(monkeypatch, tmp_path):
    class FakeModAnalyzer:
        def __init__(self, calculate_hashes=True):
            self.calculate_hashes = calculate_hashes

        def analyze_directory(self, path, recursive=True, progress_callback=None):
            progress_callback(1, 1, "a.package")
            return object()

        def get_summary(self, r):
            return {}

        def get_recommendations(self, r):
            return []

    monkeypatch.setattr(commands, "ModAnalyzer", FakeModAnalyzer)
    monkeypatch.setattr(commands.serialization, "mod_result_to_dict", lambda a, r: {"mods": []})

    buf = io.StringIO()
    args = argparse.Namespace(path=str(tmp_path), quick=True, recursive=True)
    commands.scan_mods(args, Emitter(buf))

    kinds = [json.loads(line)["type"] for line in buf.getvalue().splitlines()]
    assert kinds == ["start", "progress", "result", "done"]


def test_scan_mods_rejects_missing_dir(tmp_path):
    missing = tmp_path / "nope"
    args = argparse.Namespace(path=str(missing), quick=False, recursive=True)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.scan_mods(args, Emitter(io.StringIO()))


def test_scan_tray_drives_emitter_in_order(monkeypatch, tmp_path):
    class FakeTrayAnalyzer:
        def analyze_directory(self, path, progress_callback=None):
            progress_callback(1, 1, "household.trayitem")
            return object()

        def get_summary(self, r):
            return {}

    monkeypatch.setattr(commands, "TrayAnalyzer", FakeTrayAnalyzer)
    monkeypatch.setattr(commands.serialization, "tray_result_to_dict", lambda a, r: {"items": []})

    buf = io.StringIO()
    args = argparse.Namespace(path=str(tmp_path))
    commands.scan_tray(args, Emitter(buf))

    kinds = [json.loads(line)["type"] for line in buf.getvalue().splitlines()]
    assert kinds == ["start", "progress", "result", "done"]


def test_analyze_save_uses_stage_callback_and_emits_in_order(monkeypatch, tmp_path):
    save_file = tmp_path / "Slot.save"
    save_file.write_bytes(b"x")
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()

    class FakeSaveAnalyzer:
        def analyze_save(self, save_path, mods_path, progress_callback=None):
            progress_callback("reading", 1, 3)  # (stage, current, total)
            return object()

        def get_summary(self, r):
            return {}

    monkeypatch.setattr(commands, "SaveAnalyzer", FakeSaveAnalyzer)
    monkeypatch.setattr(
        commands.serialization, "save_result_to_dict", lambda a, r: {"save_info": {}}
    )

    buf = io.StringIO()
    args = argparse.Namespace(save_path=str(save_file), mods_path=str(mods_dir))
    commands.analyze_save(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [e["type"] for e in events] == ["start", "progress", "result", "done"]
    progress = next(e for e in events if e["type"] == "progress")
    assert progress["stage"] == "reading"
    assert progress["current"] == 1
    assert progress["total"] == 3


def test_analyze_save_rejects_missing_save_file(tmp_path):
    mods_dir = tmp_path / "Mods"
    mods_dir.mkdir()
    args = argparse.Namespace(save_path=str(tmp_path / "missing.save"), mods_path=str(mods_dir))
    with pytest.raises(ValueError, match="Save file not found"):
        commands.analyze_save(args, Emitter(io.StringIO()))


def test_inventory_scan_records_to_db_and_emits_snapshot(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "Options.ini").write_text("uiscale = 100", encoding="utf-8")
    db_path = tmp_path / "inventory.sqlite3"

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), export=True)
    commands.inventory_scan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert result["files_total"] == 1
    assert result["added"] == 1
    assert result["snapshot"]["files"][0]["relative_path"] == "Options.ini"
    assert db_path.exists()


def test_inventory_history_emits_latest_scans(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    options = sims4 / "Options.ini"
    options.write_text("uiscale = 100", encoding="utf-8")
    db_path = tmp_path / "inventory.sqlite3"

    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )
    options.write_text("uiscale = 90", encoding="utf-8")
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), limit=1)
    commands.inventory_history(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert result["root_path"] == str(sims4.resolve())
    assert len(result["scans"]) == 1
    assert result["scans"][0]["modified"] == 1


def test_inventory_file_events_emits_latest_changes(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    options = sims4 / "Options.ini"
    options.write_text("uiscale = 100", encoding="utf-8")
    db_path = tmp_path / "inventory.sqlite3"

    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )
    options.write_text("uiscale = 90", encoding="utf-8")
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), include_unchanged=False)
    commands.inventory_file_events(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert result["root_path"] == str(sims4.resolve())
    assert result["db_path"] == str(db_path)
    assert result["summary"]["modified"] == 1
    assert [(event["relative_path"], event["change_status"]) for event in result["events"]] == [
        ("Options.ini", "modified")
    ]


def test_patch_day_status_emits_changed_risk_classes(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "GameVersion.txt").write_text("1.108.329.1020\n", encoding="utf-8")
    state_path = tmp_path / "patch-day-state.json"
    state_path.write_text(
        json.dumps(
            {
                "roots": {
                    str(sims4.resolve()): {
                        "game_version": "1.107.151.1020",
                        "recorded_at": "2026-06-14T20:00:00Z",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), state=str(state_path))
    commands.patch_day_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "patch-day-status"
    result = events[1]["data"]
    assert result["status"] == "changed"
    assert result["patch_detected"] is True
    assert {risk["id"]: risk["status"] for risk in result["risk_classes"]} == {
        "script_mods": "unknown_after_patch",
        "ui_mods": "unknown_after_patch",
        "gameplay_tuning": "unknown_after_patch",
        "build_buy_and_cas": "unknown_after_patch",
    }
    assert result["automatic_reenable"] is False


def test_patch_day_record_emits_recorded_baseline(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "GameVersion.txt").write_text("1.108.329.1020\n", encoding="utf-8")
    state_path = tmp_path / "patch-day-state.json"

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), state=str(state_path))
    commands.patch_day_record(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "patch-day-record"
    result = events[1]["data"]
    assert result["status"] == "recorded"
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["roots"][str(sims4.resolve())]["game_version"] == "1.108.329.1020"


def test_cache_status_emits_read_only_cache_payload(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    cache_file = sims4 / "localthumbcache.package"
    cache_file.write_bytes(b"thumb-cache")

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4))
    commands.cache_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "cache-status"
    result = events[1]["data"]
    assert result["status"] == "review_recommended"
    assert result["mutates_files"] is False
    assert result["present_count"] == 1
    assert any(target["id"] == "localthumbcache" for target in result["targets"])
    assert cache_file.exists()


def test_save_protector_status_emits_read_only_save_payload(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    saves = sims4 / "saves"
    saves.mkdir(parents=True)
    save_file = saves / "Slot_00000001.save"
    backup_file = saves / "Slot_00000001.save.ver0"
    save_file.write_bytes(b"save")
    backup_file.write_bytes(b"backup")

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4))
    commands.save_protector_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "save-protector-status"
    result = events[1]["data"]
    assert result["status"] == "review_recommended"
    assert result["mutates_files"] is False
    assert result["primary_save_count"] == 1
    assert result["backup_count"] == 1
    assert result["save_groups"][0]["slot"] == "Slot_00000001"
    assert save_file.exists()
    assert backup_file.exists()


def test_tray_protector_status_emits_read_only_tray_payload(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    tray = sims4 / "Tray"
    tray.mkdir(parents=True)
    trayitem = tray / "family.trayitem"
    sidecar = tray / "family.hhi"
    orphan = tray / "orphan.bpi"
    trayitem.write_bytes(b"tray")
    sidecar.write_bytes(b"hhi")
    orphan.write_bytes(b"bpi")

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4))
    commands.tray_protector_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "tray-protector-status"
    result = events[1]["data"]
    assert result["status"] == "review_recommended"
    assert result["mutates_files"] is False
    assert result["tray_file_count"] == 3
    assert result["anchored_group_count"] == 1
    assert result["sidecar_only_group_count"] == 1
    assert trayitem.exists()
    assert sidecar.exists()
    assert orphan.exists()


def test_update_staging_status_emits_read_only_update_payload(tmp_path):
    staging = tmp_path / "Update Staging"
    staging.mkdir()
    archive = staging / "cool_mod.zip"
    archive.write_bytes(b"not a zip")
    package = staging / "loose.package"
    package.write_bytes(b"package")

    buf = io.StringIO()
    args = argparse.Namespace(path=str(staging))
    commands.update_staging_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "update-staging-status"
    result = events[1]["data"]
    assert result["status"] == "review_recommended"
    assert result["mutates_files"] is False
    assert result["item_count"] == 2
    assert result["archive_count"] == 1
    assert result["package_count"] == 1
    assert archive.exists()
    assert package.exists()


def test_update_staging_plan_emits_read_only_install_plan(tmp_path):
    staging = tmp_path / "Update Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    package = staging / "loose.package"
    package.write_bytes(b"package")

    buf = io.StringIO()
    args = argparse.Namespace(path=str(staging), mods_path=str(mods))
    commands.update_staging_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "update-staging-plan"
    result = events[1]["data"]
    assert result["status"] == "ready_for_review"
    assert result["mutates_files"] is False
    assert result["mutates_mods"] is False
    assert result["copy_count"] == 1
    assert result["actions"][0]["action_type"] == "copy_staged_file"
    assert package.exists()
    assert not (mods / "loose.package").exists()


def test_update_staging_plan_writes_explicit_plan_manifest(tmp_path):
    staging = tmp_path / "Update Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    package = staging / "loose.package"
    package.write_bytes(b"package")
    output = tmp_path / "plans" / "update-plan.json"

    buf = io.StringIO()
    args = argparse.Namespace(path=str(staging), mods_path=str(mods), export=str(output))
    commands.update_staging_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    result = events[1]["data"]
    assert output.exists()
    assert result["manifest_path"] == str(output.resolve())
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["manifest_path"] == str(output.resolve())
    assert saved["actions"][0]["action_type"] == "copy_staged_file"


def test_update_staging_commit_emits_applied_manifest(monkeypatch, tmp_path):
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Update Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    package = staging / "loose.package"
    package.write_bytes(b"package")
    plan = update_desk.write_update_install_plan(
        update_desk.build_update_install_plan(staging, mods),
        tmp_path / "update-plan.json",
    )

    buf = io.StringIO()
    args = argparse.Namespace(
        path=str(plan["manifest_path"]),
        action=["update-copy-001"],
        all_actions=False,
    )
    commands.update_staging_commit(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "update-staging-commit"
    result = events[1]["data"]
    assert result["status"] == "applied"
    assert result["mutates_mods"] is True
    assert (mods / "loose.package").exists()
    assert package.exists()


def test_update_staging_undo_emits_undone_manifest(monkeypatch, tmp_path):
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Update Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    manifest = update_desk.UpdateInstaller().commit_plan(
        update_desk.build_update_install_plan(staging, mods),
        selected_action_ids=["update-copy-001"],
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(manifest["manifest_path"]))
    commands.update_staging_undo(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "update-staging-undo"
    assert events[1]["data"]["status"] == "undone"
    assert not (mods / "loose.package").exists()


def test_update_staging_operation_status_emits_manifest_without_mutation(monkeypatch, tmp_path):
    import simanalysis.update_desk as update_desk

    monkeypatch.setattr(update_desk, "assert_sims_not_running", lambda: None)
    staging = tmp_path / "Update Staging"
    mods = tmp_path / "Mods"
    staging.mkdir()
    mods.mkdir()
    (staging / "loose.package").write_bytes(b"package")
    manifest = update_desk.UpdateInstaller().commit_plan(
        update_desk.build_update_install_plan(staging, mods),
        selected_action_ids=["update-copy-001"],
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(manifest["manifest_path"]))
    commands.update_staging_operation_status(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "update-staging-operation-status"
    result = events[1]["data"]
    assert result["status"] == "applied"
    assert result["manifest_path"] == manifest["manifest_path"]
    assert (mods / "loose.package").exists()


def test_cleanup_plan_emits_latest_plan_without_export(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.zip").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), export=None)
    commands.cleanup_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert result["root_path"] == str(sims4.resolve())
    assert result["db_path"] == str(db_path)
    assert result["summary"]["archives"] == 1
    assert not (sims4 / "_Simanalysis_Cleanup").exists()


def test_cleanup_plan_command_exports_only_when_requested(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    (mods / "download.zip").write_bytes(b"archive")
    db_path = tmp_path / "inventory.sqlite3"
    export_path = tmp_path / "cleanup-plan.json"
    commands.inventory_scan(
        argparse.Namespace(path=str(sims4), db=str(db_path), export=False),
        Emitter(io.StringIO()),
    )

    buf = io.StringIO()
    args = argparse.Namespace(path=str(sims4), db=str(db_path), export=str(export_path))
    commands.cleanup_plan(args, Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    result = next(event["data"] for event in events if event["type"] == "result")
    assert export_path.exists()
    assert json.loads(export_path.read_text(encoding="utf-8")) == result


def test_cleanup_stage_emits_operation_manifest(monkeypatch, tmp_path):
    calls = {}

    class FakeOperatingTable:
        def stage_cleanup_plan_file(
            self,
            root,
            plan,
            *,
            selected_action_ids=None,
            all_actions=False,
        ):
            calls["stage"] = (root, plan, selected_action_ids, all_actions)
            return {"manifest_path": "manifest.json", "status": "planned"}

    monkeypatch.setattr(commands, "OperatingTable", lambda: FakeOperatingTable())

    buf = io.StringIO()
    commands.cleanup_stage(
        argparse.Namespace(
            path=str(tmp_path),
            plan="plan.json",
            action=["duplicate:1"],
            all_actions=False,
        ),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "cleanup-stage"
    assert events[1]["data"] == {"manifest_path": "manifest.json", "status": "planned"}
    assert calls["stage"] == (tmp_path.resolve(), "plan.json", ["duplicate:1"], False)


def test_cleanup_apply_restore_status_emit_results(monkeypatch):
    calls = []

    class FakeOperatingTable:
        def apply(self, manifest_path):
            calls.append(("apply", manifest_path))
            return {"status": "applied"}

        def restore(self, manifest_path):
            calls.append(("restore", manifest_path))
            return {"status": "restored"}

        def load_status(self, manifest_path):
            calls.append(("status", manifest_path))
            return {"status": "planned"}

    monkeypatch.setattr(commands, "OperatingTable", lambda: FakeOperatingTable())

    for handler, task, status in (
        (commands.cleanup_apply, "cleanup-apply", "applied"),
        (commands.cleanup_restore, "cleanup-restore", "restored"),
        (commands.cleanup_status, "cleanup-status", "planned"),
    ):
        buf = io.StringIO()
        handler(argparse.Namespace(manifest_path="manifest.json"), Emitter(buf))
        events = [json.loads(line) for line in buf.getvalue().splitlines()]
        assert [event["type"] for event in events] == ["start", "result", "done"]
        assert events[0]["task"] == task
        assert events[1]["data"] == {"status": status}

    assert calls == [
        ("apply", "manifest.json"),
        ("restore", "manifest.json"),
        ("status", "manifest.json"),
    ]


def test_thumbnail_found(monkeypatch, tmp_path):
    f = tmp_path / "m.package"
    f.write_bytes(b"x")

    class FakeSvc:
        def get_thumbnail(self, p):
            return b"PNGDATA"

    monkeypatch.setattr(commands, "ThumbnailService", FakeSvc)
    buf = io.StringIO()
    commands.thumbnail(argparse.Namespace(path=str(f)), Emitter(buf))
    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    res = next(e for e in events if e["type"] == "result")
    assert res["data"]["found"] is True
    assert res["data"]["b64"]  # base64 string present


def test_thumbnail_missing(monkeypatch, tmp_path):
    f = tmp_path / "m.package"
    f.write_bytes(b"x")

    class FakeSvc:
        def get_thumbnail(self, p):
            return None

    monkeypatch.setattr(commands, "ThumbnailService", FakeSvc)
    buf = io.StringIO()
    commands.thumbnail(argparse.Namespace(path=str(f)), Emitter(buf))
    res = next(
        json.loads(line)
        for line in buf.getvalue().splitlines()
        if json.loads(line)["type"] == "result"
    )
    assert res["data"]["found"] is False


def test_doctor_scan_emits_combined_result(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    (sims4 / "Mods").mkdir()
    crash_log = sims4 / "lastException.txt"
    ui_log = sims4 / "lastUIException.txt"
    crash_log.write_text("crash", encoding="utf-8")
    ui_log.write_text("ui", encoding="utf-8")
    buf = io.StringIO()
    progress_seen_before_ui = {"value": False}

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir, extra_roots=()):
            assert mods_dir == sims4 / "Mods"
            return {"mod.py": "Active.ts4script"}

        def analyze(self, reports, index):
            assert reports == [crash_report]
            assert index == {"mod.py": "Active.ts4script"}
            return type(
                "CrashResult",
                (),
                {
                    "summary": {
                        "reports": 1,
                        "active_culprits": 1,
                        "disabled_culprits": 0,
                        "not_installed_culprits": 0,
                        "base_game_only": 0,
                    },
                    "parse_errors": [],
                },
            )()

    class FakeUICrashAnalyzer:
        def __init__(self):
            self.index_errors = ["bad package"]

        def build_resource_index(self, mods_dir, extra_roots=(), target_keys=None):
            assert mods_dir == sims4 / "Mods"
            assert target_keys == {123}
            return {123: ["hit"]}

        def analyze(self, reports, index):
            assert reports == [ui_report]
            assert index == {123: ["hit"]}
            events_so_far = [json.loads(line) for line in buf.getvalue().splitlines()]
            progress_seen_before_ui["value"] = any(
                event["type"] == "progress" and event.get("stage") == "script-crashes"
                for event in events_so_far
            )
            return type(
                "UIResult",
                (),
                {
                    "summary": {
                        "unique_findings": 1,
                        "occurrences": 3,
                        "active_findings": 0,
                        "disabled_findings": 1,
                        "not_found_findings": 0,
                        "no_key_findings": 0,
                    },
                    "parse_errors": [],
                    "index_errors": ["bad package"],
                },
            )()

    crash_report = type("CrashReport", (), {"signature": "crash-sig"})()
    ui_report = type("UIReport", (), {"keys": [123]})()
    monkeypatch.setattr(commands, "CrashAnalyzer", FakeCrashAnalyzer)
    monkeypatch.setattr(commands, "UICrashAnalyzer", FakeUICrashAnalyzer)
    monkeypatch.setattr(commands, "parse_exception_file", lambda path: [crash_report])
    monkeypatch.setattr(commands, "parse_ui_exception_file", lambda path: [ui_report])
    monkeypatch.setattr(commands, "discover_disabled_roots", lambda base: [])
    monkeypatch.setattr(commands, "_is_disabled_name", lambda name: False)
    monkeypatch.setattr(
        commands.serialization,
        "crash_result_to_dict",
        lambda result: {"summary": result.summary, "parse_errors": result.parse_errors},
    )
    monkeypatch.setattr(
        commands.serialization,
        "ui_result_to_dict",
        lambda result: {
            "summary": result.summary,
            "parse_errors": result.parse_errors,
            "index_errors": result.index_errors,
        },
    )

    commands.doctor_scan(
        argparse.Namespace(path=str(sims4), mods=None, recursive=False),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == [
        "start",
        "progress",
        "progress",
        "result",
        "done",
    ]
    assert progress_seen_before_ui["value"] is True
    data = next(event["data"] for event in events if event["type"] == "result")
    assert data["summary"] == {
        "script_reports": 1,
        "script_active": 1,
        "script_disabled": 0,
        "script_not_installed": 0,
        "script_base_game_only": 0,
        "ui_findings": 1,
        "ui_occurrences": 3,
        "ui_active": 0,
        "ui_disabled": 1,
        "ui_not_found": 0,
        "ui_no_key": 0,
        "parse_errors": 0,
        "index_errors": 1,
    }
    assert data["script_crashes"]["summary"]["reports"] == 1
    assert data["ui_crashes"]["summary"]["unique_findings"] == 1


def test_doctor_scan_passes_explicit_inventory_db(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    db_path = tmp_path / "inventory.sqlite3"
    calls: dict[str, Any] = {}

    def fake_build_doctor_payload(
        base,
        mods_dir,
        recursive,
        progress_callback=None,
        *,
        inventory_db=None,
    ):
        calls["args"] = (base, mods_dir, recursive, inventory_db)
        progress_callback("ledger-context")
        return {"summary": {}, "ledger_history": {"status": "available"}}

    monkeypatch.setattr(commands, "_build_doctor_payload", fake_build_doctor_payload)

    buf = io.StringIO()
    commands.doctor_scan(
        argparse.Namespace(
            path=str(sims4),
            mods=None,
            recursive=False,
            inventory_db=str(db_path),
        ),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert calls["args"] == (sims4, mods, False, db_path)
    assert (
        next(event["data"] for event in events if event["type"] == "result")["ledger_history"][
            "status"
        ]
        == "available"
    )


def test_doctor_scan_rejects_missing_sims_dir(tmp_path):
    args = argparse.Namespace(path=str(tmp_path / "missing"), mods=None, recursive=False)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.doctor_scan(args, Emitter(io.StringIO()))


def test_doctor_scan_allows_missing_default_mods_dir(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir, extra_roots=()):
            assert mods_dir == sims4 / "Mods"
            return {}

        def analyze(self, reports, index):
            return type(
                "CrashResult",
                (),
                {
                    "summary": {
                        "reports": 0,
                        "active_culprits": 0,
                        "disabled_culprits": 0,
                        "not_installed_culprits": 0,
                        "base_game_only": 0,
                    },
                    "parse_errors": [],
                },
            )()

    class FakeUICrashAnalyzer:
        def __init__(self):
            self.index_errors = []

        def analyze(self, reports, index):
            return type(
                "UIResult",
                (),
                {
                    "summary": {
                        "unique_findings": 0,
                        "occurrences": 0,
                        "active_findings": 0,
                        "disabled_findings": 0,
                        "not_found_findings": 0,
                        "no_key_findings": 0,
                    },
                    "parse_errors": [],
                    "index_errors": [],
                },
            )()

    monkeypatch.setattr(commands, "CrashAnalyzer", FakeCrashAnalyzer)
    monkeypatch.setattr(commands, "UICrashAnalyzer", FakeUICrashAnalyzer)
    monkeypatch.setattr(commands, "discover_disabled_roots", lambda base: [])
    monkeypatch.setattr(
        commands.serialization,
        "crash_result_to_dict",
        lambda result: {"summary": result.summary, "parse_errors": result.parse_errors},
    )
    monkeypatch.setattr(
        commands.serialization,
        "ui_result_to_dict",
        lambda result: {
            "summary": result.summary,
            "parse_errors": result.parse_errors,
            "index_errors": result.index_errors,
        },
    )

    buf = io.StringIO()
    commands.doctor_scan(
        argparse.Namespace(path=str(sims4), mods=None, recursive=False),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events][-2:] == ["result", "done"]


def test_doctor_scan_rejects_explicit_missing_mods_dir(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    args = argparse.Namespace(path=str(sims4), mods=str(tmp_path / "missing-mods"), recursive=False)
    with pytest.raises(ValueError, match="Invalid directory path"):
        commands.doctor_scan(args, Emitter(io.StringIO()))


def test_treatment_plan_builds_doctor_payload_and_emits_plan(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    payload: dict[str, Any] = {
        "script_crashes": {"findings": []},
        "ui_crashes": {"findings": []},
    }
    plan = {"status": "planned", "manifest_path": None}
    calls: dict[str, Any] = {}

    def fake_build_doctor_payload(base, mods_dir, recursive):
        calls["doctor"] = (base, mods_dir, recursive)
        return payload

    def fake_create_plan(base, mods_dir, doctor_payload, *, save=False):
        calls["plan"] = (base, mods_dir, doctor_payload, save)
        return plan

    monkeypatch.setattr(commands, "_build_doctor_payload", fake_build_doctor_payload)
    monkeypatch.setattr(commands.treatment, "create_plan", fake_create_plan)

    buf = io.StringIO()
    commands.treatment_plan(
        argparse.Namespace(path=str(sims4), mods=None, doctor_json=None, save=True),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-plan"
    assert events[1]["data"] == plan
    assert calls["doctor"] == (sims4.resolve(), (sims4 / "Mods").resolve(), False)
    assert calls["plan"] == (sims4.resolve(), (sims4 / "Mods").resolve(), payload, True)


def test_treatment_plan_uses_doctor_json_when_provided(monkeypatch, tmp_path):
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    doctor_json = tmp_path / "doctor.json"
    payload: dict[str, Any] = {
        "script_crashes": {"findings": []},
        "ui_crashes": {"findings": []},
    }
    doctor_json.write_text(json.dumps(payload), encoding="utf-8")
    calls: dict[str, Any] = {}

    def fail_build_doctor_payload(base, mods_dir, recursive):
        raise AssertionError("doctor payload should be loaded from JSON")

    def fake_create_plan(base, mods_dir, doctor_payload, *, save=False):
        calls["plan"] = (base, mods_dir, doctor_payload, save)
        return {"loaded": True}

    monkeypatch.setattr(commands, "_build_doctor_payload", fail_build_doctor_payload)
    monkeypatch.setattr(commands.treatment, "create_plan", fake_create_plan)

    buf = io.StringIO()
    commands.treatment_plan(
        argparse.Namespace(
            path=str(sims4), mods=str(mods), doctor_json=str(doctor_json), save=False
        ),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[1]["data"] == {"loaded": True}
    assert calls["plan"] == (sims4.resolve(), mods.resolve(), payload, False)


def test_treatment_plan_rejects_invalid_doctor_json(tmp_path):
    sims4 = tmp_path / "The Sims 4"
    sims4.mkdir()
    doctor_json = tmp_path / "doctor.json"
    doctor_json.write_text(json.dumps({"script_crashes": {}}), encoding="utf-8")

    with pytest.raises(ValueError, match="Doctor JSON must contain script_crashes and ui_crashes"):
        commands.treatment_plan(
            argparse.Namespace(
                path=str(sims4), mods=None, doctor_json=str(doctor_json), save=False
            ),
            Emitter(io.StringIO()),
        )


def test_live_monitor_once_emits_waiting_result(monkeypatch, tmp_path):
    class FakeLiveMonitor:
        def __init__(self, base, mods_dir):
            self.base = base
            self.mods_dir = mods_dir

        def poll(self, doctor_builder, treatment_planner):
            return {
                "changed_logs": [],
                "watched_log_count": 0,
                "doctor_summary": {},
                "treatment": {
                    "candidate_count": 0,
                    "first_batch_count": 0,
                    "manifest_path": None,
                    "warnings": [],
                    "blockers": [],
                },
                "recommended_next_action": "waiting",
                "warnings": [],
            }

    monkeypatch.setattr(commands.live_monitoring, "LiveMonitor", FakeLiveMonitor)
    buf = io.StringIO()

    commands.live_monitor(
        argparse.Namespace(path=str(tmp_path), mods=None, interval=0.2, once=True),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "progress", "result", "done"]
    assert events[0]["task"] == "live-monitor"
    assert events[1]["stage"] == "waiting"
    assert events[2]["data"]["recommended_next_action"] == "waiting"


def test_live_monitor_continuous_mode_sleeps_and_emits_only_changed_results(monkeypatch, tmp_path):
    class SentinelError(Exception):
        pass

    poll_calls = []
    sleep_calls = []

    class FakeLiveMonitor:
        def __init__(self, base, mods_dir):
            self.base = base
            self.mods_dir = mods_dir

        def poll(self, doctor_builder, treatment_planner):
            poll_calls.append((doctor_builder, treatment_planner))
            if len(poll_calls) == 1:
                return {
                    "changed_logs": [],
                    "watched_log_count": 1,
                    "doctor_summary": {},
                    "treatment": {
                        "candidate_count": 0,
                        "first_batch_count": 0,
                        "manifest_path": None,
                        "warnings": [],
                        "blockers": [],
                    },
                    "recommended_next_action": "waiting",
                    "warnings": [],
                }
            return {
                "changed_logs": [
                    {
                        "name": "lastException.txt",
                        "path": str(tmp_path / "lastException.txt"),
                    }
                ],
                "watched_log_count": 1,
                "doctor_summary": {},
                "treatment": {
                    "candidate_count": 1,
                    "first_batch_count": 1,
                    "manifest_path": None,
                    "warnings": [],
                    "blockers": [],
                },
                "recommended_next_action": "open_treatment",
                "warnings": [],
            }

    def fake_sleep(interval):
        sleep_calls.append(interval)
        if len(sleep_calls) == 2:
            raise SentinelError

    monkeypatch.setattr(commands.live_monitoring, "LiveMonitor", FakeLiveMonitor)
    monkeypatch.setattr(commands.time, "sleep", fake_sleep)
    buf = io.StringIO()

    with pytest.raises(SentinelError):
        commands.live_monitor(
            argparse.Namespace(path=str(tmp_path), mods=None, interval=0.2, once=False),
            Emitter(buf),
        )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert len(poll_calls) == 2
    assert sleep_calls == [0.2, 0.2]
    assert [event["type"] for event in events] == ["start", "progress", "progress", "result"]
    assert [event.get("stage") for event in events if event["type"] == "progress"] == [
        "waiting",
        "open_treatment",
    ]

    results = [event["data"] for event in events if event["type"] == "result"]
    assert len(results) == 1
    assert results[0]["recommended_next_action"] == "open_treatment"
    assert results[0]["changed_logs"][0]["name"] == "lastException.txt"


def test_live_monitor_rejects_non_positive_interval(tmp_path):
    with pytest.raises(ValueError, match="Live monitor interval must be greater than zero"):
        commands.live_monitor(
            argparse.Namespace(path=str(tmp_path), mods=None, interval=0, once=True),
            Emitter(io.StringIO()),
        )


def test_treatment_apply_emits_treatment_result(monkeypatch):
    calls = {}

    def fake_apply_next_step(manifest_path):
        calls["manifest_path"] = manifest_path
        return {"status": "awaiting_result"}

    monkeypatch.setattr(commands.treatment, "apply_next_step", fake_apply_next_step)

    buf = io.StringIO()
    commands.treatment_apply(argparse.Namespace(manifest_path="manifest.json"), Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-apply"
    assert events[1]["data"] == {"status": "awaiting_result"}
    assert calls == {"manifest_path": "manifest.json"}


def test_treatment_outcome_emits_recorded_session(monkeypatch):
    calls = {}

    def fake_record_outcome(manifest_path, outcome):
        calls["record"] = (manifest_path, outcome)
        return {"status": "confirmed_candidate"}

    monkeypatch.setattr(commands.treatment, "record_outcome", fake_record_outcome)

    buf = io.StringIO()
    commands.treatment_outcome(
        argparse.Namespace(manifest_path="manifest.json", outcome="issue_gone"),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-outcome"
    assert events[1]["data"] == {"status": "confirmed_candidate"}
    assert calls == {"record": ("manifest.json", "issue_gone")}


def test_treatment_status_emits_loaded_session(monkeypatch):
    monkeypatch.setattr(
        commands.treatment,
        "load_session",
        lambda manifest_path: {"manifest_path": manifest_path, "status": "planned"},
    )

    buf = io.StringIO()
    commands.treatment_status(argparse.Namespace(manifest_path="manifest.json"), Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-status"
    assert events[1]["data"] == {"manifest_path": "manifest.json", "status": "planned"}


def test_treatment_handoff_emits_markdown_payload(monkeypatch):
    calls = {}

    def fake_load_session(manifest_path):
        calls["manifest_path"] = manifest_path
        return {"manifest_path": manifest_path, "status": "planned"}

    def fake_render_handoff(session):
        calls["session"] = session
        return "# Simanalysis Bisect Handoff\n"

    monkeypatch.setattr(commands.treatment, "load_session", fake_load_session)
    monkeypatch.setattr(commands.treatment, "render_handoff", fake_render_handoff)

    buf = io.StringIO()
    commands.treatment_handoff(argparse.Namespace(manifest_path="manifest.json"), Emitter(buf))

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-handoff"
    assert events[1]["data"] == {
        "manifest_path": "manifest.json",
        "handoff": "# Simanalysis Bisect Handoff\n",
    }
    assert calls == {
        "manifest_path": "manifest.json",
        "session": {"manifest_path": "manifest.json", "status": "planned"},
    }


def test_treatment_restore_emits_restored_session(monkeypatch):
    calls = {}

    def fake_restore_session(manifest_path, step="latest"):
        calls["restore"] = (manifest_path, step)
        return {"status": "planned"}

    monkeypatch.setattr(commands.treatment, "restore_session", fake_restore_session)

    buf = io.StringIO()
    commands.treatment_restore(
        argparse.Namespace(manifest_path="manifest.json", step="all"),
        Emitter(buf),
    )

    events = [json.loads(line) for line in buf.getvalue().splitlines()]
    assert [event["type"] for event in events] == ["start", "result", "done"]
    assert events[0]["task"] == "treatment-restore"
    assert events[1]["data"] == {"status": "planned"}
    assert calls == {"restore": ("manifest.json", "all")}
