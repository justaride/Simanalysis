"""Dispatch desktop-bridge commands onto the existing analysis core."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Callable, cast

from simanalysis import live_monitoring, serialization, treatment
from simanalysis.analyzers.crash_analyzer import CrashAnalyzer, _is_disabled_name
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
from simanalysis.bridge.protocol import Emitter
from simanalysis.inventory import InventoryScanner, default_inventory_db_path
from simanalysis.parsers.exception_log import parse_exception_file
from simanalysis.parsers.ui_exception_log import parse_ui_exception_file
from simanalysis.services.thumbnail_service import ThumbnailService


def _require_dir(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"Invalid directory path: {path}")
    return p


def scan_mods(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-mods")
    analyzer = ModAnalyzer(calculate_hashes=not args.quick)
    result = analyzer.analyze_directory(
        path,
        recursive=args.recursive,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.mod_result_to_dict(analyzer, result))
    emit.done()


def scan_tray(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    emit.start("scan-tray")
    analyzer = TrayAnalyzer()
    result = analyzer.analyze_directory(
        path,
        progress_callback=lambda c, t, f: emit.progress(c, t, file=f),
    )
    emit.result(serialization.tray_result_to_dict(analyzer, result))
    emit.done()


def analyze_save(args: argparse.Namespace, emit: Emitter) -> None:
    save_path = Path(args.save_path).expanduser().resolve()
    if not save_path.exists() or not save_path.is_file():
        raise ValueError("Save file not found")
    mods_path = _require_dir(args.mods_path)
    emit.start("analyze-save")
    analyzer = SaveAnalyzer()
    result = analyzer.analyze_save(
        save_path,
        mods_path,
        progress_callback=lambda stage, c, t: emit.progress(c, t, stage=stage),
    )
    emit.result(serialization.save_result_to_dict(analyzer, result))
    emit.done()


def inventory_scan(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    db_path = Path(args.db).expanduser() if args.db else default_inventory_db_path()
    scanner = InventoryScanner(db_path)

    emit.start("inventory-scan")
    result = scanner.scan(path).to_dict()
    result["db_path"] = str(db_path)
    if args.export:
        result["snapshot"] = scanner.export_latest_snapshot(path)
    emit.result(result)
    emit.done()


def inventory_history(args: argparse.Namespace, emit: Emitter) -> None:
    path = _require_dir(args.path)
    db_path = Path(args.db).expanduser() if args.db else default_inventory_db_path()
    scanner = InventoryScanner(db_path)

    emit.start("inventory-history")
    emit.result(
        {
            "root_path": str(path),
            "db_path": str(db_path),
            "scans": scanner.list_scan_history(path, limit=args.limit),
        }
    )
    emit.done()


def thumbnail(args: argparse.Namespace, emit: Emitter) -> None:
    import base64

    path = Path(args.path).expanduser().resolve()
    svc = ThumbnailService()
    data = svc.get_thumbnail(path)
    if data:
        emit.result({"found": True, "b64": base64.b64encode(data).decode("ascii")})
    else:
        emit.result({"found": False, "b64": None})
    emit.done()


def _doctor_summary(script_payload: dict, ui_payload: dict) -> dict[str, int]:
    script_summary = script_payload.get("summary", {})
    ui_summary = ui_payload.get("summary", {})
    return {
        "script_reports": int(script_summary.get("reports", 0)),
        "script_active": int(script_summary.get("active_culprits", 0)),
        "script_disabled": int(script_summary.get("disabled_culprits", 0)),
        "script_not_installed": int(script_summary.get("not_installed_culprits", 0)),
        "script_base_game_only": int(script_summary.get("base_game_only", 0)),
        "ui_findings": int(ui_summary.get("unique_findings", 0)),
        "ui_occurrences": int(ui_summary.get("occurrences", 0)),
        "ui_active": int(ui_summary.get("active_findings", 0)),
        "ui_disabled": int(ui_summary.get("disabled_findings", 0)),
        "ui_not_found": int(ui_summary.get("not_found_findings", 0)),
        "ui_no_key": int(ui_summary.get("no_key_findings", 0)),
        "parse_errors": len(script_payload.get("parse_errors", []))
        + len(ui_payload.get("parse_errors", [])),
        "index_errors": len(ui_payload.get("index_errors", [])),
    }


def _build_doctor_payload(
    base: Path,
    mods_dir: Path,
    recursive: bool,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    pattern = "**/lastException*.txt" if recursive else "lastException*.txt"
    crash_reports = []
    crash_parse_errors = []
    seen = set()
    for log_file in sorted(base.glob(pattern)):
        try:
            for report in parse_exception_file(log_file):
                if report.signature in seen:
                    continue
                seen.add(report.signature)
                crash_reports.append(report)
        except Exception as exc:
            crash_parse_errors.append(f"{log_file.name}: {exc}")

    crash_analyzer = CrashAnalyzer()
    extra_roots = [d for d in base.glob("**/_*") if d.is_dir() and _is_disabled_name(d.name)]
    module_index = crash_analyzer.build_module_index(mods_dir, extra_roots=extra_roots)
    crash_result = crash_analyzer.analyze(crash_reports, module_index)
    crash_result.parse_errors = crash_parse_errors
    crash_payload = serialization.crash_result_to_dict(crash_result)
    if progress_callback:
        progress_callback("script-crashes")

    ui_pattern = "**/lastUIException*.txt" if recursive else "lastUIException*.txt"
    ui_reports = []
    ui_parse_errors = []
    for log_file in sorted(base.glob(ui_pattern)):
        try:
            ui_reports.extend(parse_ui_exception_file(log_file))
        except Exception as exc:
            ui_parse_errors.append(f"{log_file.name}: {exc}")

    ui_analyzer = UICrashAnalyzer()
    target_keys = {key for report in ui_reports for key in report.keys}
    if target_keys:
        resource_index = ui_analyzer.build_resource_index(
            mods_dir,
            extra_roots=discover_disabled_roots(base),
            target_keys=target_keys,
        )
    else:
        resource_index = {}
    ui_result = ui_analyzer.analyze(ui_reports, resource_index)
    ui_result.parse_errors = ui_parse_errors
    ui_payload = serialization.ui_result_to_dict(ui_result)
    if progress_callback:
        progress_callback("ui-crashes")

    return {
        "summary": _doctor_summary(crash_payload, ui_payload),
        "script_crashes": crash_payload,
        "ui_crashes": ui_payload,
    }


def doctor_scan(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"

    emit.start("doctor-scan", total=2)
    progress_count = 0

    def emit_doctor_progress(stage: str) -> None:
        nonlocal progress_count
        progress_count += 1
        emit.progress(progress_count, 2, stage=stage, force=True)

    payload = _build_doctor_payload(base, mods_dir, args.recursive, emit_doctor_progress)
    emit.result(payload)
    emit.done()


def _require_doctor_json_list(section: dict[str, Any], key: str, label: str) -> list[Any]:
    value = section.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"Doctor JSON field {label} must be a list")
    return value


def _require_doctor_json_object_list(
    section: dict[str, Any],
    key: str,
    label: str,
) -> list[dict[str, Any]]:
    value = _require_doctor_json_list(section, key, label)
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Doctor JSON field {label} must contain objects")
    return cast(list[dict[str, Any]], value)


def _validate_doctor_json_shape(data: dict[str, Any]) -> None:
    if not isinstance(data.get("script_crashes"), dict) or not isinstance(
        data.get("ui_crashes"), dict
    ):
        raise ValueError("Doctor JSON must contain script_crashes and ui_crashes")

    script = cast(dict[str, Any], data["script_crashes"])
    ui = cast(dict[str, Any], data["ui_crashes"])
    if "summary" in script and not isinstance(script["summary"], dict):
        raise ValueError("Doctor JSON field script_crashes.summary must be an object")
    if "summary" in ui and not isinstance(ui["summary"], dict):
        raise ValueError("Doctor JSON field ui_crashes.summary must be an object")

    _require_doctor_json_object_list(script, "ranked_mods", "script_crashes.ranked_mods")
    script_findings = _require_doctor_json_object_list(
        script,
        "findings",
        "script_crashes.findings",
    )
    _require_doctor_json_list(script, "parse_errors", "script_crashes.parse_errors")
    for index, finding in enumerate(script_findings):
        suspects = finding.get("suspects", [])
        if not isinstance(suspects, list):
            raise ValueError(
                f"Doctor JSON field script_crashes.findings[{index}].suspects must be a list"
            )
        for suspect in suspects:
            if not isinstance(suspect, dict):
                raise ValueError(
                    f"Doctor JSON field script_crashes.findings[{index}].suspects "
                    "must contain objects"
                )

    ui_findings = _require_doctor_json_object_list(ui, "findings", "ui_crashes.findings")
    _require_doctor_json_list(ui, "parse_errors", "ui_crashes.parse_errors")
    _require_doctor_json_list(ui, "index_errors", "ui_crashes.index_errors")
    for index, finding in enumerate(ui_findings):
        report = finding.get("report")
        if report is not None and not isinstance(report, dict):
            raise ValueError(
                f"Doctor JSON field ui_crashes.findings[{index}].report must be an object"
            )
        hits = finding.get("hits", [])
        if not isinstance(hits, list):
            raise ValueError(f"Doctor JSON field ui_crashes.findings[{index}].hits must be a list")
        for hit in hits:
            if not isinstance(hit, dict):
                raise ValueError(
                    f"Doctor JSON field ui_crashes.findings[{index}].hits must contain objects"
                )


def _load_doctor_json(path: str | Path) -> dict[str, Any]:
    doctor_path = Path(path).expanduser().resolve()
    if not doctor_path.exists() or not doctor_path.is_file():
        raise ValueError(f"Doctor JSON not found: {path}")
    try:
        parsed = json.loads(doctor_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Doctor JSON is not valid JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Doctor JSON must be a JSON object")
    _validate_doctor_json_shape(parsed)
    return parsed


def treatment_plan(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"

    emit.start("treatment-plan")
    doctor_payload = (
        _load_doctor_json(args.doctor_json)
        if args.doctor_json
        else _build_doctor_payload(base, mods_dir, recursive=False)
    )
    emit.result(treatment.create_plan(base, mods_dir, doctor_payload, save=args.save))
    emit.done()


def live_monitor(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    if args.interval <= 0:
        raise ValueError("Live monitor interval must be greater than zero")
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"
    monitor = live_monitoring.LiveMonitor(base, mods_dir)

    emit.start("live-monitor")
    while True:
        result = monitor.poll(_build_doctor_payload, treatment.create_plan)
        watched_count = int(result.get("watched_log_count", 0) or 0)
        emit.progress(
            watched_count,
            watched_count,
            stage=str(result.get("recommended_next_action", "waiting")),
            force=True,
        )
        if result.get("changed_logs") or args.once:
            emit.result(result)
        if args.once:
            emit.done()
            return
        time.sleep(args.interval)


def treatment_apply(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-apply")
    emit.result(treatment.apply_next_step(args.manifest_path))
    emit.done()


def treatment_outcome(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-outcome")
    emit.result(treatment.record_outcome(args.manifest_path, args.outcome))
    emit.done()


def treatment_restore(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-restore")
    emit.result(treatment.restore_session(args.manifest_path, step=args.step))
    emit.done()


def treatment_status(args: argparse.Namespace, emit: Emitter) -> None:
    emit.start("treatment-status")
    emit.result(treatment.load_session(args.manifest_path))
    emit.done()


DISPATCH = {
    "scan-mods": scan_mods,
    "scan-tray": scan_tray,
    "analyze-save": analyze_save,
    "inventory-scan": inventory_scan,
    "inventory-history": inventory_history,
    "thumbnail": thumbnail,
    "doctor-scan": doctor_scan,
    "treatment-plan": treatment_plan,
    "live-monitor": live_monitor,
    "treatment-apply": treatment_apply,
    "treatment-outcome": treatment_outcome,
    "treatment-restore": treatment_restore,
    "treatment-status": treatment_status,
}
