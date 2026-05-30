"""Dispatch desktop-bridge commands onto the existing analysis core."""

from __future__ import annotations

import argparse
from pathlib import Path

from simanalysis import serialization
from simanalysis.analyzers.crash_analyzer import CrashAnalyzer, _is_disabled_name
from simanalysis.analyzers.mod_analyzer import ModAnalyzer
from simanalysis.analyzers.save_analyzer import SaveAnalyzer
from simanalysis.analyzers.tray_analyzer import TrayAnalyzer
from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
from simanalysis.bridge.protocol import Emitter
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


def doctor_scan(args: argparse.Namespace, emit: Emitter) -> None:
    base = _require_dir(args.path)
    mods_dir = _require_dir(args.mods) if args.mods else base / "Mods"

    emit.start("doctor-scan", total=2)

    pattern = "**/lastException*.txt" if args.recursive else "lastException*.txt"
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
    emit.progress(1, 2, stage="script-crashes", force=True)

    ui_pattern = "**/lastUIException*.txt" if args.recursive else "lastUIException*.txt"
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
    emit.progress(2, 2, stage="ui-crashes", force=True)

    emit.result(
        {
            "summary": _doctor_summary(crash_payload, ui_payload),
            "script_crashes": crash_payload,
            "ui_crashes": ui_payload,
        }
    )
    emit.done()


DISPATCH = {
    "scan-mods": scan_mods,
    "scan-tray": scan_tray,
    "analyze-save": analyze_save,
    "thumbnail": thumbnail,
    "doctor-scan": doctor_scan,
}
