"""Tests for static TS4Script security review signals."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from simanalysis.script_security import analyze_script_archive, summarize_script_security


def _write_script(path: Path, files: dict[str, str | bytes]) -> None:
    with ZipFile(path, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)


def test_safe_script_reports_low_risk_without_execution(tmp_path: Path) -> None:
    script = tmp_path / "safe.ts4script"
    _write_script(
        script,
        {
            "safe_mod/main.py": "import sims4\n\ndef run():\n    return None\n",
            "README.md": "Safe fixture",
        },
    )

    result = analyze_script_archive(script)

    assert result["status"] == "reviewed"
    assert result["risk_level"] == "low"
    assert result["elevated_signal_count"] == 0
    assert result["module_count"] == 1
    assert result["executes_code"] is False


def test_network_subprocess_and_dynamic_execution_are_elevated_risk(
    tmp_path: Path,
) -> None:
    script = tmp_path / "risky.ts4script"
    _write_script(
        script,
        {
            "risky/main.py": """
import socket
import subprocess

def run(payload):
    subprocess.Popen(["echo", "hi"])
    return eval(payload)
""",
        },
    )

    result = analyze_script_archive(script)

    assert result["risk_level"] == "elevated"
    assert {signal["id"] for signal in result["signals"]} >= {
        "network_import",
        "subprocess_import",
        "subprocess_call",
        "dynamic_execution",
    }
    assert all("malware" not in signal["message"].lower() for signal in result["signals"])


def test_obfuscation_and_unexpected_binary_are_review_signals(tmp_path: Path) -> None:
    script = tmp_path / "packed.ts4script"
    _write_script(
        script,
        {
            "packed/main.py": "import marshal\nblob = '" + ("A" * 360) + "'\n",
            "packed/native.dll": b"MZ\x00\x00",
        },
    )

    result = analyze_script_archive(script)

    assert result["risk_level"] == "elevated"
    assert {signal["id"] for signal in result["signals"]} >= {
        "obfuscation_hint",
        "unexpected_binary",
    }


def test_corrupt_script_archive_is_reported_not_raised(tmp_path: Path) -> None:
    script = tmp_path / "broken.ts4script"
    script.write_bytes(b"not a zip")

    result = analyze_script_archive(script)

    assert result["status"] == "unreadable_archive"
    assert result["risk_level"] == "unknown"
    assert result["signals"][0]["id"] == "archive_unreadable"
    assert result["executes_code"] is False


def test_archive_path_traversal_is_blocked_without_extraction(tmp_path: Path) -> None:
    script = tmp_path / "escape.ts4script"
    _write_script(script, {"../escape.py": "print('no extract')"})

    result = analyze_script_archive(script)

    assert result["status"] == "blocked"
    assert result["risk_level"] == "elevated"
    assert result["signals"][0]["id"] == "archive_path_traversal"
    assert not (tmp_path / "escape.py").exists()


def test_script_security_summary_counts_elevated_and_unknown(tmp_path: Path) -> None:
    _write_script(tmp_path / "safe.ts4script", {"safe.py": "import sims4\n"})
    _write_script(tmp_path / "risky.ts4script", {"risky.py": "import socket\n"})
    (tmp_path / "broken.ts4script").write_bytes(b"not zip")

    summary = summarize_script_security(tmp_path)

    assert summary["status"] == "available"
    assert summary["script_count"] == 3
    assert summary["risk_counts"] == {"elevated": 1, "low": 1, "unknown": 1}
    assert summary["elevated_count"] == 1
    assert summary["executes_code"] is False
