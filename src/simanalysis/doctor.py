"""Read-only Sims Doctor orchestration shared by CLI and desktop bridge."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from simanalysis import serialization
from simanalysis.analyzers.crash_analyzer import CrashAnalyzer, _is_disabled_name
from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
from simanalysis.classification import summarize_classifications
from simanalysis.inventory import InventoryScanner
from simanalysis.parsers.exception_log import parse_exception_file
from simanalysis.parsers.ui_exception_log import parse_ui_exception_file
from simanalysis.script_security import summarize_script_security


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


def _summary_value(summary: dict[str, Any], key: str) -> int:
    try:
        return int(summary.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _evidence(label: str, value: int) -> dict[str, int | str]:
    return {"label": label, "value": value}


def doctor_verdicts(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Return evidence-labeled Doctor verdicts without changing any files."""
    verdicts: list[dict[str, Any]] = []
    script_active = _summary_value(summary, "script_active")
    ui_active = _summary_value(summary, "ui_active")
    script_reports = _summary_value(summary, "script_reports")
    ui_findings = _summary_value(summary, "ui_findings")
    parse_errors = _summary_value(summary, "parse_errors")
    index_errors = _summary_value(summary, "index_errors")

    if script_active:
        verdicts.append(
            {
                "id": "active-script-suspects",
                "status": "needs_action",
                "severity": "high",
                "title": "Active script suspects found",
                "recommended_next_action": "start_bisect",
                "confidence": "direct",
                "evidence": [
                    _evidence("Active script suspects", script_active),
                    _evidence("Script crash reports", script_reports),
                ],
            }
        )

    if ui_active:
        verdicts.append(
            {
                "id": "active-ui-findings",
                "status": "needs_action",
                "severity": "medium",
                "title": "Active UI findings found",
                "recommended_next_action": "start_bisect",
                "confidence": "direct",
                "evidence": [
                    _evidence("Active UI findings", ui_active),
                    _evidence("Unique UI findings", ui_findings),
                ],
            }
        )

    if parse_errors or index_errors:
        verdicts.append(
            {
                "id": "partial-doctor-evidence",
                "status": "partial",
                "severity": "medium",
                "title": "Doctor evidence is partial",
                "recommended_next_action": "review_doctor_inputs",
                "confidence": "partial",
                "evidence": [
                    _evidence("Parse errors", parse_errors),
                    _evidence("Index errors", index_errors),
                ],
            }
        )

    inactive_evidence = sum(
        _summary_value(summary, key)
        for key in (
            "script_disabled",
            "script_not_installed",
            "script_base_game_only",
            "ui_disabled",
            "ui_not_found",
            "ui_no_key",
        )
    )
    if not verdicts and inactive_evidence:
        verdicts.append(
            {
                "id": "inactive-doctor-evidence",
                "status": "needs_review",
                "severity": "low",
                "title": "Doctor found non-active evidence",
                "recommended_next_action": "review_doctor",
                "confidence": "direct",
                "evidence": [_evidence("Non-active findings", inactive_evidence)],
            }
        )

    if not verdicts:
        verdicts.append(
            {
                "id": "doctor-clean",
                "status": "clean",
                "severity": "info",
                "title": "No active Doctor findings found",
                "recommended_next_action": "none",
                "confidence": "direct",
                "evidence": [],
            }
        )

    return verdicts


def doctor_playbooks(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Return read-only next-step playbooks based on the Doctor summary."""
    playbooks: list[dict[str, Any]] = []
    if _summary_value(summary, "script_active") or _summary_value(summary, "ui_active"):
        playbooks.append(
            {
                "id": "bisect-active-doctor-candidates",
                "title": "Start bisection from Doctor JSON",
                "symptom": "active_crash_candidates",
                "available": True,
                "next_command": (
                    "simanalysis bisect start <The Sims 4> --doctor-json <doctor.json>"
                ),
                "requires": ["saved Doctor JSON", "manifest-based bisection session"],
                "reason": "Active Doctor candidates are present.",
            }
        )

    if _summary_value(summary, "parse_errors") or _summary_value(summary, "index_errors"):
        playbooks.append(
            {
                "id": "review-doctor-inputs",
                "title": "Review partial Doctor evidence",
                "symptom": "partial_evidence",
                "available": True,
                "next_command": (
                    "simanalysis doctor <The Sims 4> "
                    "--recursive --format json --output <doctor.json>"
                ),
                "requires": ["readable exception logs", "readable Mods package index"],
                "reason": "Doctor could not parse or index every evidence source.",
            }
        )

    return playbooks


def _string_report_attr(report: Any, name: str) -> str | None:
    value = getattr(report, name, None)
    if value is None or value == "":
        return None
    return str(value)


def _timeline_event(kind: str, report: Any) -> dict[str, Any]:
    event: dict[str, Any] = {"kind": kind}
    for attr in ("created", "source_file", "signature", "report_type", "message", "game_version"):
        value = _string_report_attr(report, attr)
        if value is not None:
            event[attr] = value
    source_files = getattr(report, "source_files", None)
    if isinstance(source_files, list) and source_files:
        event["source_files"] = [str(source) for source in source_files]
    return event


def doctor_timeline(
    script_reports: Iterable[Any],
    ui_reports: Iterable[Any],
) -> list[dict[str, Any]]:
    """Return a deterministic read-only timeline across script and UI evidence."""
    events = [
        *(_timeline_event("script", report) for report in script_reports),
        *(_timeline_event("ui", report) for report in ui_reports),
    ]
    return sorted(
        events,
        key=lambda event: (
            0 if event.get("created") else 1,
            str(event.get("created") or ""),
            str(event.get("source_file") or ""),
            str(event.get("kind") or ""),
            str(event.get("signature") or ""),
        ),
    )


def doctor_ledger_history(
    sims4_dir: Path | str,
    inventory_db: Path | str,
    *,
    limit: int = 5,
    scanner_factory: Callable[[Path | str], Any] = InventoryScanner,
) -> dict[str, Any]:
    """Return read-only inventory context for Doctor reports when explicitly requested."""
    root = Path(sims4_dir).expanduser().resolve()
    db_path = Path(inventory_db).expanduser().resolve()
    safe_limit = max(limit, 1)
    scanner = scanner_factory(db_path)
    warnings: list[str] = []
    recent_scans: list[dict[str, object]] = []
    latest_file_events: dict[str, object] | None = None

    try:
        recent_scans = scanner.list_scan_history(root, limit=safe_limit)
    except ValueError as exc:
        warnings.append(str(exc))

    if recent_scans:
        try:
            latest_file_events = scanner.latest_file_events(root, include_unchanged=False)
        except ValueError as exc:
            warnings.append(str(exc))

    return {
        "status": "available" if recent_scans else "no_scans",
        "db_path": str(db_path),
        "recent_scans": recent_scans,
        "latest_file_events": latest_file_events,
        "warnings": warnings,
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
    inventory_db: Path | None = None,
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

    summary = doctor_summary(crash_payload, ui_payload)
    payload = {
        "summary": summary,
        "classification_summary": summarize_classifications(mods_dir),
        "script_security_summary": summarize_script_security(mods_dir),
        "verdicts": doctor_verdicts(summary),
        "playbooks": doctor_playbooks(summary),
        "timeline": doctor_timeline(crash_reports, ui_reports),
        "script_crashes": crash_payload,
        "ui_crashes": ui_payload,
    }
    if inventory_db is not None:
        payload["ledger_history"] = doctor_ledger_history(base, inventory_db)
    return payload


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

    verdicts = payload.get("verdicts")
    if not isinstance(verdicts, list):
        verdicts = doctor_verdicts(summary)
    if verdicts:
        lines.append("Doctor verdicts:")
        for verdict in verdicts:
            title = verdict.get("title", "Doctor verdict")
            status = verdict.get("status", "unknown")
            severity = verdict.get("severity", "unknown")
            confidence = verdict.get("confidence", "unknown")
            lines.append(f"  - Verdict: {title} ({status}, {severity}, {confidence})")
            next_action = verdict.get("recommended_next_action")
            if next_action:
                lines.append(f"    Next action: {next_action}")
        lines.append("")

    playbooks = payload.get("playbooks")
    if not isinstance(playbooks, list):
        playbooks = doctor_playbooks(summary)
    if playbooks:
        lines.append("Doctor playbooks:")
        for playbook in playbooks:
            title = playbook.get("title", "Doctor playbook")
            lines.append(f"  - Playbook: {title}")
            next_command = playbook.get("next_command")
            if next_command:
                lines.append(f"    Command: {next_command}")
        lines.append("")

    classification_summary = payload.get("classification_summary")
    if isinstance(classification_summary, dict):
        label_counts = classification_summary.get("label_counts", {})
        if isinstance(label_counts, dict) and label_counts:
            labels = ", ".join(f"{label}: {count}" for label, count in label_counts.items())
        else:
            labels = "none"
        lines.append("Classification evidence:")
        lines.append(
            f"  - Files: {classification_summary.get('file_count', 0)} | "
            f"unknown: {classification_summary.get('unknown_count', 0)} | labels: {labels}"
        )
        lines.append("  - Automatic safe marking: no")
        lines.append("")

    script_security_summary = payload.get("script_security_summary")
    if isinstance(script_security_summary, dict):
        risk_counts = script_security_summary.get("risk_counts", {})
        if isinstance(risk_counts, dict) and risk_counts:
            risks = ", ".join(f"{risk}: {count}" for risk, count in risk_counts.items())
        else:
            risks = "none"
        lines.append("Script security evidence:")
        lines.append(
            f"  - Scripts: {script_security_summary.get('script_count', 0)} | "
            f"elevated: {script_security_summary.get('elevated_count', 0)} | "
            f"risks: {risks}"
        )
        lines.append("  - Static review only: no script code executed")
        lines.append("")

    safe_limit = max(limit, 0)
    timeline = payload.get("timeline")
    if isinstance(timeline, list) and timeline:
        lines.append("Doctor timeline:")
        for event in timeline[:safe_limit]:
            if not isinstance(event, dict):
                continue
            kind = event.get("kind", "event")
            created = event.get("created") or "unknown time"
            source_file = Path(str(event.get("source_file", ""))).name or "unknown source"
            message = event.get("message") or event.get("signature") or "no message"
            lines.append(f"  - {kind} {created} - {source_file} - {message}")
        hidden = len(timeline) - safe_limit
        if hidden > 0:
            plural = "event" if hidden == 1 else "events"
            lines.append(f"  ... {hidden} more timeline {plural} hidden by --limit")
        lines.append("")

    ledger = payload.get("ledger_history")
    if isinstance(ledger, dict):
        lines.append("Inventory ledger:")
        lines.append(f"  - Status: {ledger.get('status', 'unknown')}")
        db_path = ledger.get("db_path")
        if db_path:
            lines.append(f"  - Database: {db_path}")
        scans = ledger.get("recent_scans", [])
        if isinstance(scans, list) and scans:
            latest_scan = scans[0]
            if isinstance(latest_scan, dict):
                lines.append(
                    "  - Latest scan: "
                    f"{latest_scan.get('scan_id', 'unknown')} | "
                    f"files: {latest_scan.get('files_total', 0)} | "
                    f"added: {latest_scan.get('added', 0)} | "
                    f"moved: {latest_scan.get('moved', 0)} | "
                    f"modified: {latest_scan.get('modified', 0)} | "
                    f"removed: {latest_scan.get('removed', 0)}"
                )
        latest_events = ledger.get("latest_file_events")
        if isinstance(latest_events, dict):
            events = latest_events.get("events", [])
            if isinstance(events, list) and events:
                lines.append("  - Latest file events:")
                for event in events[:safe_limit]:
                    if not isinstance(event, dict):
                        continue
                    relative_path = event.get("relative_path", "unknown")
                    status = event.get("change_status", "unknown")
                    previous = event.get("previous_relative_path")
                    suffix = f" from {previous}" if previous else ""
                    lines.append(f"    - {relative_path} ({status}{suffix})")
                hidden = len(events) - safe_limit
                if hidden > 0:
                    lines.append(f"    ... {hidden} more ledger event(s) hidden by --limit")
        warnings = ledger.get("warnings", [])
        if isinstance(warnings, list):
            for warning in warnings:
                lines.append(f"  - Warning: {warning}")
        lines.append("")

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
