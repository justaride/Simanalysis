from pathlib import Path
from types import SimpleNamespace
from typing import Any

from simanalysis import doctor as doctor_core


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
    assert payload["verdicts"][0]["id"] == "active-script-suspects"
    assert payload["verdicts"][1]["id"] == "active-ui-findings"
    assert payload["playbooks"][0]["id"] == "bisect-active-doctor-candidates"


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
