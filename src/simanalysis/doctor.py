"""Read-only Sims Doctor orchestration shared by CLI and desktop bridge."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from simanalysis import serialization
from simanalysis.analyzers.crash_analyzer import CrashAnalyzer, _is_disabled_name
from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
from simanalysis.parsers.exception_log import parse_exception_file
from simanalysis.parsers.ui_exception_log import parse_ui_exception_file


def doctor_summary(script_payload: dict[str, Any], ui_payload: dict[str, Any]) -> dict[str, int]:
    """Return the compact summary shared by bridge, CLI, and live-monitoring flows."""
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


def build_doctor_payload(
    base: Path,
    mods_dir: Path,
    recursive: bool,
    progress_callback: Callable[[str], None] | None = None,
    *,
    crash_analyzer_factory: Callable[[], Any] = CrashAnalyzer,
    ui_analyzer_factory: Callable[[], Any] = UICrashAnalyzer,
    parse_exception: Callable[[Path], Iterable[Any]] = parse_exception_file,
    parse_ui_exception: Callable[[Path], Iterable[Any]] = parse_ui_exception_file,
    is_disabled_name: Callable[[str], bool] = _is_disabled_name,
    discover_disabled_roots_fn: Callable[[Path], Iterable[Path]] = discover_disabled_roots,
    crash_serializer: Callable[[Any], dict[str, Any]] = serialization.crash_result_to_dict,
    ui_serializer: Callable[[Any], dict[str, Any]] = serialization.ui_result_to_dict,
) -> dict[str, Any]:
    """Build a combined script/UI Doctor payload without mutating the Sims folder."""
    pattern = "**/lastException*.txt" if recursive else "lastException*.txt"
    crash_reports: list[Any] = []
    crash_parse_errors = []
    seen = set()
    for log_file in sorted(base.glob(pattern)):
        try:
            for report in parse_exception(log_file):
                if report.signature in seen:
                    continue
                seen.add(report.signature)
                crash_reports.append(report)
        except Exception as exc:
            crash_parse_errors.append(f"{log_file.name}: {exc}")

    crash_analyzer = crash_analyzer_factory()
    extra_roots = [d for d in base.glob("**/_*") if d.is_dir() and is_disabled_name(d.name)]
    module_index = crash_analyzer.build_module_index(mods_dir, extra_roots=extra_roots)
    crash_result = crash_analyzer.analyze(crash_reports, module_index)
    crash_result.parse_errors = crash_parse_errors
    crash_payload = crash_serializer(crash_result)
    if progress_callback:
        progress_callback("script-crashes")

    ui_pattern = "**/lastUIException*.txt" if recursive else "lastUIException*.txt"
    ui_reports: list[Any] = []
    ui_parse_errors = []
    for log_file in sorted(base.glob(ui_pattern)):
        try:
            ui_reports.extend(parse_ui_exception(log_file))
        except Exception as exc:
            ui_parse_errors.append(f"{log_file.name}: {exc}")

    ui_analyzer = ui_analyzer_factory()
    target_keys = {key for report in ui_reports for key in report.keys}
    if target_keys:
        resource_index = ui_analyzer.build_resource_index(
            mods_dir,
            extra_roots=discover_disabled_roots_fn(base),
            target_keys=target_keys,
        )
    else:
        resource_index = {}
    ui_result = ui_analyzer.analyze(ui_reports, resource_index)
    ui_result.parse_errors = ui_parse_errors
    ui_payload = ui_serializer(ui_result)
    if progress_callback:
        progress_callback("ui-crashes")

    return {
        "summary": doctor_summary(crash_payload, ui_payload),
        "script_crashes": crash_payload,
        "ui_crashes": ui_payload,
    }


def format_doctor_text(payload: dict[str, Any], limit: int = 20) -> str:
    """Format a compact, evidence-labeled Doctor report for terminal use."""
    summary = payload.get("summary", {})
    lines = [
        "Sims Doctor",
        (
            "Script crashes: "
            f"{summary.get('script_reports', 0)} report(s) | "
            f"active: {summary.get('script_active', 0)} | "
            f"disabled: {summary.get('script_disabled', 0)} | "
            f"not-installed: {summary.get('script_not_installed', 0)} | "
            f"base-game-only: {summary.get('script_base_game_only', 0)}"
        ),
        (
            "UI crashes: "
            f"{summary.get('ui_findings', 0)} finding(s), "
            f"{summary.get('ui_occurrences', 0)} occurrence(s) | "
            f"active: {summary.get('ui_active', 0)} | "
            f"disabled: {summary.get('ui_disabled', 0)} | "
            f"not-found: {summary.get('ui_not_found', 0)} | "
            f"no-key: {summary.get('ui_no_key', 0)}"
        ),
        (
            "Warnings: "
            f"parse errors: {summary.get('parse_errors', 0)} | "
            f"index errors: {summary.get('index_errors', 0)}"
        ),
        "",
    ]

    safe_limit = max(limit, 0)
    script_mods = [
        mod
        for mod in payload.get("script_crashes", {}).get("ranked_mods", [])
        if mod.get("status") == "active"
    ]
    if script_mods:
        lines.append("Active script suspects:")
        for mod in script_mods[:safe_limit]:
            lines.append(
                "  - "
                f"{mod.get('mod')} "
                f"({mod.get('confidence', 'unknown')}, "
                f"top suspect in {mod.get('top_suspect_count', 0)} crash(es))"
            )
        hidden = len(script_mods) - safe_limit
        if hidden > 0:
            lines.append(f"  ... {hidden} more hidden by --limit")
        lines.append("")

    ui_findings = [
        finding
        for finding in payload.get("ui_crashes", {}).get("findings", [])
        if finding.get("status") == "active"
    ]
    if ui_findings:
        lines.append("Active UI findings:")
        for finding in ui_findings[:safe_limit]:
            hits = finding.get("hits", [])
            packages = ", ".join(dict.fromkeys(hit.get("package_name", "") for hit in hits))
            key_values = ", ".join(key.get("hex", str(key)) for key in finding.get("keys", []))
            suffix = f" in {packages}" if packages else ""
            lines.append(f"  - {key_values or 'no key'}{suffix}")
        hidden = len(ui_findings) - safe_limit
        if hidden > 0:
            lines.append(f"  ... {hidden} more hidden by --limit")
        lines.append("")

    if not script_mods and not ui_findings:
        lines.append("No active Doctor findings found.")

    return "\n".join(lines).rstrip()
