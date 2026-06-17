from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zipfile import ZipFile

from simanalysis import doctor as doctor_core
from simanalysis.inventory import InventoryScanner


def _summary(**overrides: int) -> dict[str, int]:
    summary = {
        "script_reports": 0,
        "script_active": 0,
        "script_disabled": 0,
        "script_not_installed": 0,
        "script_base_game_only": 0,
        "ui_findings": 0,
        "ui_occurrences": 0,
        "ui_active": 0,
        "ui_disabled": 0,
        "ui_not_found": 0,
        "ui_no_key": 0,
        "parse_errors": 0,
        "index_errors": 0,
    }
    summary.update(overrides)
    return summary


def test_doctor_verdicts_prioritize_active_script_suspects() -> None:
    verdicts = doctor_core.doctor_verdicts(_summary(script_reports=2, script_active=1, ui_active=1))

    assert verdicts[0] == {
        "id": "active-script-suspects",
        "status": "needs_action",
        "severity": "high",
        "title": "Active script suspects found",
        "recommended_next_action": "start_bisect",
        "confidence": "direct",
        "evidence": [
            {"label": "Active script suspects", "value": 1},
            {"label": "Script crash reports", "value": 2},
        ],
    }
    assert verdicts[1]["id"] == "active-ui-findings"
    assert verdicts[1]["recommended_next_action"] == "start_bisect"


def test_doctor_playbooks_offer_manifest_bisection_for_active_candidates() -> None:
    playbooks = doctor_core.doctor_playbooks(_summary(script_active=1, ui_active=1))

    assert playbooks == [
        {
            "id": "bisect-active-doctor-candidates",
            "title": "Start bisection from Doctor JSON",
            "symptom": "active_crash_candidates",
            "available": True,
            "next_command": ("simanalysis bisect start <The Sims 4> --doctor-json <doctor.json>"),
            "requires": ["saved Doctor JSON", "manifest-based bisection session"],
            "reason": "Active Doctor candidates are present.",
        }
    ]


def test_doctor_verdicts_mark_partial_evidence_when_inputs_are_incomplete() -> None:
    verdicts = doctor_core.doctor_verdicts(_summary(parse_errors=1, index_errors=2))
    playbooks = doctor_core.doctor_playbooks(_summary(parse_errors=1, index_errors=2))

    assert verdicts == [
        {
            "id": "partial-doctor-evidence",
            "status": "partial",
            "severity": "medium",
            "title": "Doctor evidence is partial",
            "recommended_next_action": "review_doctor_inputs",
            "confidence": "partial",
            "evidence": [
                {"label": "Parse errors", "value": 1},
                {"label": "Index errors", "value": 2},
            ],
        }
    ]
    assert playbooks == [
        {
            "id": "review-doctor-inputs",
            "title": "Review partial Doctor evidence",
            "symptom": "partial_evidence",
            "available": True,
            "next_command": (
                "simanalysis doctor <The Sims 4> --recursive --format json --output <doctor.json>"
            ),
            "requires": ["readable exception logs", "readable Mods package index"],
            "reason": "Doctor could not parse or index every evidence source.",
        }
    ]


def test_doctor_verdicts_emit_clean_result_without_findings_or_warnings() -> None:
    assert doctor_core.doctor_verdicts(_summary()) == [
        {
            "id": "doctor-clean",
            "status": "clean",
            "severity": "info",
            "title": "No active Doctor findings found",
            "recommended_next_action": "none",
            "confidence": "direct",
            "evidence": [],
        }
    ]
    assert doctor_core.doctor_playbooks(_summary()) == []


def test_build_doctor_payload_includes_verdicts_and_playbooks(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    with ZipFile(mods / "helper.ts4script", "w") as zip_file:
        zip_file.writestr("helper.py", "import subprocess\n")
    (sims4 / "lastException.txt").write_text("crash", encoding="utf-8")
    (sims4 / "lastUIException.txt").write_text("ui", encoding="utf-8")
    crash_report = type("CrashReport", (), {"signature": "crash-signature"})()
    ui_report = type("UIReport", (), {"keys": [123]})()

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir: Path, extra_roots: list[Path]) -> dict[str, str]:
            return {"mod.py": "Active.ts4script"}

        def analyze(self, reports: list[Any], index: dict[str, str]) -> Any:
            assert reports == [crash_report]
            assert index == {"mod.py": "Active.ts4script"}
            return SimpleNamespace()

    class FakeUiAnalyzer:
        def build_resource_index(
            self,
            mods_dir: Path,
            extra_roots: list[Path],
            target_keys: set[int],
        ) -> dict[int, list[str]]:
            assert target_keys == {123}
            return {123: ["Active.package"]}

        def analyze(self, reports: list[Any], index: dict[int, list[str]]) -> Any:
            assert reports == [ui_report]
            assert index == {123: ["Active.package"]}
            return SimpleNamespace()

    payload = doctor_core.build_doctor_payload(
        sims4,
        mods,
        recursive=False,
        crash_analyzer_factory=FakeCrashAnalyzer,
        ui_analyzer_factory=FakeUiAnalyzer,
        parse_exception=lambda path: [crash_report],
        parse_ui_exception=lambda path: [ui_report],
        is_disabled_name=lambda name: False,
        discover_disabled_roots_fn=lambda base: [],
        crash_serializer=lambda result: {
            "summary": {
                "reports": 1,
                "active_culprits": 1,
                "disabled_culprits": 0,
                "not_installed_culprits": 0,
                "base_game_only": 0,
            },
            "ranked_mods": [],
            "parse_errors": [],
        },
        ui_serializer=lambda result: {
            "summary": {
                "unique_findings": 1,
                "occurrences": 1,
                "active_findings": 1,
                "disabled_findings": 0,
                "not_found_findings": 0,
                "no_key_findings": 0,
            },
            "findings": [],
            "parse_errors": [],
            "index_errors": [],
        },
    )

    assert payload["summary"]["script_active"] == 1
    assert payload["classification_summary"]["label_counts"] == {"script": 1}
    assert payload["classification_summary"]["automatic_safe_marking"] is False
    assert payload["script_security_summary"]["risk_counts"] == {"elevated": 1}
    assert payload["script_security_summary"]["executes_code"] is False
    assert payload["verdicts"][0]["id"] == "active-script-suspects"
    assert payload["verdicts"][1]["id"] == "active-ui-findings"
    assert payload["playbooks"][0]["id"] == "bisect-active-doctor-candidates"


def test_build_doctor_payload_includes_scope_and_native_crashes(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    archive = sims4 / "_Quarantine_Logs"
    mods.mkdir(parents=True)
    archive.mkdir()
    (sims4 / "lastCrash.txt").write_text(
        "<root><report>"
        "<createtime>2026-06-16 22:19:10</createtime>"
        "<categoryid>gameplay.NativeCrash</categoryid>"
        "<buildsignature>Local.1.124.55.1230</buildsignature>"
        "<currentgamestate>Live_Mode</currentgamestate>"
        "<desyncdata>Modded: False&#13;&#10;Native stack line</desyncdata>"
        "</report></root>",
        encoding="utf-8",
    )
    (archive / "lastCrash_archived.txt").write_text(
        "<root><report><createtime>2026-06-10 10:00:00</createtime></report></root>",
        encoding="utf-8",
    )

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir: Path, extra_roots: list[Path]) -> dict[str, str]:
            return {}

        def analyze(self, reports: list[Any], index: dict[str, str]) -> Any:
            return SimpleNamespace()

    class FakeUiAnalyzer:
        def build_resource_index(
            self,
            mods_dir: Path,
            extra_roots: list[Path],
            target_keys: set[int],
        ) -> dict[int, list[str]]:
            return {}

        def analyze(self, reports: list[Any], index: dict[int, list[str]]) -> Any:
            return SimpleNamespace()

    payload = doctor_core.build_doctor_payload(
        sims4,
        mods,
        recursive=False,
        crash_analyzer_factory=FakeCrashAnalyzer,
        ui_analyzer_factory=FakeUiAnalyzer,
        parse_exception=lambda path: [],
        parse_ui_exception=lambda path: [],
        is_disabled_name=lambda name: False,
        discover_disabled_roots_fn=lambda base: [],
        crash_serializer=lambda result: {
            "summary": {
                "reports": 0,
                "active_culprits": 0,
                "disabled_culprits": 0,
                "not_installed_culprits": 0,
                "base_game_only": 0,
            },
            "ranked_mods": [],
            "parse_errors": [],
        },
        ui_serializer=lambda result: {
            "summary": {
                "unique_findings": 0,
                "occurrences": 0,
                "active_findings": 0,
                "disabled_findings": 0,
                "not_found_findings": 0,
                "no_key_findings": 0,
            },
            "findings": [],
            "parse_errors": [],
            "index_errors": [],
        },
    )

    assert payload["evidence_scope"] == {
        "mode": "current",
        "recursive": False,
        "base_path": str(sims4.resolve()),
        "mods_path": str(mods.resolve()),
        "log_patterns": {
            "script": "lastException*.txt",
            "ui": "lastUIException*.txt",
            "native_crash": "lastCrash*.txt",
        },
        "scanned_log_counts": {"script": 0, "ui": 0, "native_crash": 1},
        "archived_disabled_logs_included": False,
    }
    assert payload["summary"]["native_crash_reports"] == 1
    assert payload["summary"]["latest_evidence"] == {
        "script": None,
        "ui": None,
        "native_crash": "2026-06-16 22:19:10",
        "overall": "2026-06-16 22:19:10",
    }
    assert payload["native_crashes"]["summary"] == {"reports": 1, "unattributed": 1}
    assert payload["native_crashes"]["reports"][0]["status"] == "unattributed_native"
    assert payload["native_crashes"]["reports"][0]["actionability"] == "informational"


def test_build_doctor_payload_recursive_scope_includes_archived_native_crashes(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    archive = sims4 / "_Quarantine_Logs"
    mods.mkdir(parents=True)
    archive.mkdir()
    (archive / "lastCrash_archived.txt").write_text(
        "<root><report><createtime>2026-06-10 10:00:00</createtime></report></root>",
        encoding="utf-8",
    )

    class FakeAnalyzer:
        def build_module_index(self, mods_dir: Path, extra_roots: list[Path]) -> dict[str, str]:
            return {}

        def build_resource_index(
            self,
            mods_dir: Path,
            extra_roots: list[Path],
            target_keys: set[int],
        ) -> dict[int, list[str]]:
            return {}

        def analyze(self, reports: list[Any], index: Any) -> Any:
            return SimpleNamespace()

    payload = doctor_core.build_doctor_payload(
        sims4,
        mods,
        recursive=True,
        crash_analyzer_factory=FakeAnalyzer,
        ui_analyzer_factory=FakeAnalyzer,
        parse_exception=lambda path: [],
        parse_ui_exception=lambda path: [],
        is_disabled_name=lambda name: False,
        discover_disabled_roots_fn=lambda base: [],
        crash_serializer=lambda result: {
            "summary": {
                "reports": 0,
                "active_culprits": 0,
                "disabled_culprits": 0,
                "not_installed_culprits": 0,
                "base_game_only": 0,
            },
            "ranked_mods": [],
            "parse_errors": [],
        },
        ui_serializer=lambda result: {
            "summary": {
                "unique_findings": 0,
                "occurrences": 0,
                "active_findings": 0,
                "disabled_findings": 0,
                "not_found_findings": 0,
                "no_key_findings": 0,
            },
            "findings": [],
            "parse_errors": [],
            "index_errors": [],
        },
    )

    assert payload["evidence_scope"]["mode"] == "recursive"
    assert payload["evidence_scope"]["log_patterns"]["native_crash"] == "**/lastCrash*.txt"
    assert payload["evidence_scope"]["scanned_log_counts"]["native_crash"] == 1
    assert payload["evidence_scope"]["archived_disabled_logs_included"] is True


def test_build_doctor_payload_includes_chronological_timeline(tmp_path: Path) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    older_script = sims4 / "lastException_old.txt"
    newer_script = sims4 / "lastException.txt"
    ui_log = sims4 / "lastUIException.txt"
    older_script.write_text("old crash", encoding="utf-8")
    newer_script.write_text("new crash", encoding="utf-8")
    ui_log.write_text("ui crash", encoding="utf-8")
    old_report = SimpleNamespace(
        signature="old-script",
        source_file=str(older_script),
        report_type="lastException",
        message="Older script failure",
        created="2026-06-14T20:00:00Z",
        game_version="1.107.151",
    )
    new_report = SimpleNamespace(
        signature="new-script",
        source_file=str(newer_script),
        report_type="lastException",
        message="Newer script failure",
        created="2026-06-15T01:00:00Z",
        game_version="1.107.151",
    )
    ui_report = SimpleNamespace(
        signature="ui-buildbuy",
        source_file=str(ui_log),
        source_files=[str(ui_log)],
        report_type="lastUIException",
        message="BuildBuy03B",
        created="2026-06-15T00:30:00Z",
        game_version="1.107.151",
        keys=[123],
    )

    class FakeCrashAnalyzer:
        def build_module_index(self, mods_dir: Path, extra_roots: list[Path]) -> dict[str, str]:
            return {}

        def analyze(self, reports: list[Any], index: dict[str, str]) -> Any:
            return SimpleNamespace()

    class FakeUiAnalyzer:
        def build_resource_index(
            self,
            mods_dir: Path,
            extra_roots: list[Path],
            target_keys: set[int],
        ) -> dict[int, list[str]]:
            return {}

        def analyze(self, reports: list[Any], index: dict[int, list[str]]) -> Any:
            return SimpleNamespace()

    payload = doctor_core.build_doctor_payload(
        sims4,
        mods,
        recursive=False,
        crash_analyzer_factory=FakeCrashAnalyzer,
        ui_analyzer_factory=FakeUiAnalyzer,
        parse_exception=lambda path: {
            older_script: [old_report],
            newer_script: [new_report],
        }[path],
        parse_ui_exception=lambda path: [ui_report],
        is_disabled_name=lambda name: False,
        discover_disabled_roots_fn=lambda base: [],
        crash_serializer=lambda result: {
            "summary": {
                "reports": 2,
                "active_culprits": 0,
                "disabled_culprits": 0,
                "not_installed_culprits": 0,
                "base_game_only": 2,
            },
            "ranked_mods": [],
            "parse_errors": [],
        },
        ui_serializer=lambda result: {
            "summary": {
                "unique_findings": 1,
                "occurrences": 1,
                "active_findings": 0,
                "disabled_findings": 0,
                "not_found_findings": 1,
                "no_key_findings": 0,
            },
            "findings": [],
            "parse_errors": [],
            "index_errors": [],
        },
    )

    assert payload["timeline"] == [
        {
            "kind": "script",
            "created": "2026-06-14T20:00:00Z",
            "source_file": str(older_script),
            "signature": "old-script",
            "report_type": "lastException",
            "message": "Older script failure",
            "game_version": "1.107.151",
        },
        {
            "kind": "ui",
            "created": "2026-06-15T00:30:00Z",
            "source_file": str(ui_log),
            "source_files": [str(ui_log)],
            "signature": "ui-buildbuy",
            "report_type": "lastUIException",
            "message": "BuildBuy03B",
            "game_version": "1.107.151",
        },
        {
            "kind": "script",
            "created": "2026-06-15T01:00:00Z",
            "source_file": str(newer_script),
            "signature": "new-script",
            "report_type": "lastException",
            "message": "Newer script failure",
            "game_version": "1.107.151",
        },
    ]


def test_format_doctor_text_surfaces_verdicts_and_playbooks() -> None:
    summary = _summary(script_reports=1, script_active=1)
    payload = {
        "summary": summary,
        "verdicts": doctor_core.doctor_verdicts(summary),
        "playbooks": doctor_core.doctor_playbooks(summary),
        "script_crashes": {
            "ranked_mods": [
                {
                    "mod": "Active.ts4script",
                    "status": "active",
                    "confidence": "high",
                    "top_suspect_count": 1,
                }
            ]
        },
        "ui_crashes": {"findings": []},
    }

    report = doctor_core.format_doctor_text(payload)

    assert "Verdict: Active script suspects found (needs_action, high, direct)" in report
    assert "Next action: start_bisect" in report
    assert "Playbook: Start bisection from Doctor JSON" in report
    assert "simanalysis bisect start <The Sims 4> --doctor-json <doctor.json>" in report
    assert "Active.ts4script" in report


def test_format_doctor_text_surfaces_timeline_with_limit() -> None:
    payload = {
        "summary": _summary(script_reports=2, ui_findings=1, ui_occurrences=1),
        "script_crashes": {"ranked_mods": []},
        "ui_crashes": {"findings": []},
        "timeline": [
            {
                "kind": "script",
                "created": "2026-06-14T20:00:00Z",
                "source_file": "/Sims/lastException_old.txt",
                "message": "Older script failure",
            },
            {
                "kind": "ui",
                "created": "2026-06-15T00:30:00Z",
                "source_file": "/Sims/lastUIException.txt",
                "message": "BuildBuy03B",
            },
            {
                "kind": "script",
                "created": "2026-06-15T01:00:00Z",
                "source_file": "/Sims/lastException.txt",
                "message": "Newer script failure",
            },
        ],
    }

    report = doctor_core.format_doctor_text(payload, limit=2)

    assert "Doctor timeline:" in report
    assert "script 2026-06-14T20:00:00Z - lastException_old.txt - Older script failure" in report
    assert "ui 2026-06-15T00:30:00Z - lastUIException.txt - BuildBuy03B" in report
    assert "... 1 more timeline event hidden by --limit" in report
    assert "Newer script failure" not in report


def test_format_doctor_text_surfaces_scope_and_native_crashes() -> None:
    payload = {
        "summary": _summary(native_crash_reports=1),
        "evidence_scope": {
            "mode": "recursive",
            "archived_disabled_logs_included": True,
            "scanned_log_counts": {"script": 2, "ui": 1, "native_crash": 1},
        },
        "script_crashes": {"ranked_mods": []},
        "ui_crashes": {"findings": []},
        "native_crashes": {
            "summary": {"reports": 1, "unattributed": 1},
            "parse_errors": [],
            "reports": [
                {
                    "source_file": "/Sims/lastCrash.txt",
                    "created": "2026-06-16 22:19:10",
                    "category_id": "gameplay.NativeCrash",
                    "build_signature": "Local.1.124.55.1230",
                    "modded": False,
                    "current_game_state": "Live_Mode",
                    "stack_snippet": ["Native stack line"],
                    "status": "unattributed_native",
                    "actionability": "informational",
                }
            ],
        },
    }

    report = doctor_core.format_doctor_text(payload)

    assert "Evidence scope: Archived/quarantined included" in report
    assert "Archived/quarantined logs may be included in this evidence." in report
    assert "Native crashes: 1 report(s) | unattributed: 1" in report
    assert "lastCrash.txt - 2026-06-16 22:19:10 - gameplay.NativeCrash" in report
    assert "No active Doctor findings found." in report


def test_doctor_ledger_history_summarizes_recent_scans_and_latest_events(
    tmp_path: Path,
) -> None:
    sims4 = tmp_path / "The Sims 4"
    mods = sims4 / "Mods"
    mods.mkdir(parents=True)
    package = mods / "Alpha.package"
    package.write_bytes(b"alpha")
    db_path = tmp_path / "inventory.sqlite3"
    scanner = InventoryScanner(db_path)
    first = scanner.scan(sims4)
    moved = mods / "Moved" / "Alpha.package"
    moved.parent.mkdir()
    package.rename(moved)
    (sims4 / "lastException.txt").write_text("latest crash", encoding="utf-8")
    second = scanner.scan(sims4)

    history = doctor_core.doctor_ledger_history(sims4, db_path, limit=2)

    assert history["status"] == "available"
    assert history["db_path"] == str(db_path)
    assert [scan["scan_id"] for scan in history["recent_scans"]] == [
        second.scan_id,
        first.scan_id,
    ]
    assert history["latest_file_events"]["summary"]["moved"] == 1
    assert history["latest_file_events"]["summary"]["added"] == 1
    assert (
        "Mods/Moved/Alpha.package",
        "moved",
        "Mods/Alpha.package",
    ) in {
        (
            event["relative_path"],
            event["change_status"],
            event["previous_relative_path"],
        )
        for event in history["latest_file_events"]["events"]
    }


def test_format_doctor_text_surfaces_ledger_history() -> None:
    payload = {
        "summary": _summary(script_reports=1),
        "script_crashes": {"ranked_mods": []},
        "ui_crashes": {"findings": []},
        "ledger_history": {
            "status": "available",
            "db_path": "/Sims/inventory.sqlite3",
            "recent_scans": [
                {
                    "scan_id": 7,
                    "files_total": 42,
                    "added": 1,
                    "removed": 0,
                    "moved": 1,
                    "modified": 2,
                    "unchanged": 38,
                }
            ],
            "latest_file_events": {
                "events": [
                    {
                        "relative_path": "Mods/Moved/Alpha.package",
                        "change_status": "moved",
                        "previous_relative_path": "Mods/Alpha.package",
                    }
                ]
            },
            "warnings": [],
        },
    }

    report = doctor_core.format_doctor_text(payload)

    assert "Inventory ledger:" in report
    assert "Status: available" in report
    assert "Latest scan: 7 | files: 42 | added: 1 | moved: 1 | modified: 2 | removed: 0" in report
    assert "Mods/Moved/Alpha.package (moved from Mods/Alpha.package)" in report
