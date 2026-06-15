from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.release_security as release_security
from scripts.release_security import generate_sboms, main, signing_status, verify_release_artifacts


def test_generate_sboms_writes_cyclonedx_files(tmp_path: Path) -> None:
    paths = generate_sboms(tmp_path)

    names = {path.name for path in paths}
    assert "simanalysis-combined.cdx.json" in names
    assert "simanalysis-web-npm.cdx.json" in names

    combined = json.loads((tmp_path / "simanalysis-combined.cdx.json").read_text())
    assert combined["bomFormat"] == "CycloneDX"
    assert combined["specVersion"] == "1.5"
    assert combined["components"]


def test_generated_web_sbom_reflects_fixed_form_data_lock(tmp_path: Path) -> None:
    paths = generate_sboms(tmp_path)
    web_path = next(path for path in paths if path.name == "simanalysis-web-npm.cdx.json")
    web = json.loads(web_path.read_text())
    form_data = next(
        component for component in web["components"] if component["name"] == "form-data"
    )

    assert form_data["version"] == "4.0.6"


def test_signing_status_never_claims_signed_artifacts() -> None:
    status = signing_status()

    assert status["macos"]["status"] == "pending"
    assert status["windows"]["status"] == "pending"
    assert "Do not describe artifacts as signed" in status["claim"]


def test_verify_release_artifacts_reports_unsigned_macos_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = tmp_path / "Simanalysis.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (macos / "simanalysis-desktop").write_text("desktop", encoding="utf-8")
    (macos / "simanalysis-bridge").write_text("bridge", encoding="utf-8")
    monkeypatch.setattr(
        release_security,
        "_run_status",
        lambda _cmd: {
            "available": True,
            "returncode": 1,
            "stdout": "",
            "stderr": "code object is not signed at all",
        },
    )

    report = verify_release_artifacts([app])

    artifact = report["artifacts"][0]
    assert report["distribution_ready"] is False
    assert artifact["artifact_type"] == "macos_app"
    assert artifact["required_files_present"] is True
    assert artifact["codesign"]["status"] == "unsigned"
    assert artifact["notarization"]["status"] == "not_verified"


def test_verify_release_artifacts_blocks_missing_sidecar(tmp_path: Path) -> None:
    app = tmp_path / "Simanalysis.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (macos / "simanalysis-desktop").write_text("desktop", encoding="utf-8")

    report = verify_release_artifacts([app])

    artifact = report["artifacts"][0]
    assert report["distribution_ready"] is False
    assert artifact["required_files_present"] is False
    assert "Contents/MacOS/simanalysis-bridge" in artifact["missing_files"]


def test_verify_release_artifacts_strict_mode_refuses_unsigned_artifacts(tmp_path: Path) -> None:
    app = tmp_path / "Simanalysis.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    (macos / "simanalysis-desktop").write_text("desktop", encoding="utf-8")
    (macos / "simanalysis-bridge").write_text("bridge", encoding="utf-8")

    with pytest.raises(SystemExit, match="not distribution-ready"):
        verify_release_artifacts([app], strict=True)


def test_verify_release_artifacts_reports_signed_windows_exe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "Simanalysis.exe"
    exe.write_text("desktop", encoding="utf-8")
    monkeypatch.setattr(release_security, "_powershell_executable", lambda: "powershell")
    monkeypatch.setattr(
        release_security,
        "_run_status",
        lambda _cmd: {
            "available": True,
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "Status": "Valid",
                    "StatusMessage": "Signature verified.",
                    "Subject": "CN=Simanalysis Test",
                    "Thumbprint": "ABC123",
                }
            ),
            "stderr": "",
        },
    )

    report = verify_release_artifacts([exe])

    artifact = report["artifacts"][0]
    assert report["distribution_ready"] is True
    assert artifact["artifact_type"] == "windows_executable"
    assert artifact["signature"]["status"] == "verified"
    assert artifact["signature"]["subject"] == "CN=Simanalysis Test"


def test_verify_release_artifacts_blocks_unsigned_windows_installer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = tmp_path / "Simanalysis.msi"
    installer.write_text("installer", encoding="utf-8")
    monkeypatch.setattr(release_security, "_powershell_executable", lambda: "powershell")
    monkeypatch.setattr(
        release_security,
        "_run_status",
        lambda _cmd: {
            "available": True,
            "returncode": 0,
            "stdout": json.dumps(
                {
                    "Status": "NotSigned",
                    "StatusMessage": "The file is not digitally signed.",
                    "Subject": None,
                    "Thumbprint": None,
                }
            ),
            "stderr": "",
        },
    )

    report = verify_release_artifacts([installer])

    artifact = report["artifacts"][0]
    assert report["distribution_ready"] is False
    assert artifact["artifact_type"] == "windows_installer"
    assert artifact["signature"]["status"] == "unsigned"


def test_verify_release_artifacts_blocks_missing_windows_exe(tmp_path: Path) -> None:
    report = verify_release_artifacts([tmp_path / "missing.exe"])

    artifact = report["artifacts"][0]
    assert report["distribution_ready"] is False
    assert artifact["artifact_type"] == "windows_executable"
    assert artifact["exists"] is False
    assert artifact["signature"]["status"] == "missing"


def test_release_security_cli_writes_artifact_report_before_strict_failure(
    tmp_path: Path,
) -> None:
    app = tmp_path / "Simanalysis.app"
    macos = app / "Contents" / "MacOS"
    macos.mkdir(parents=True)
    output = tmp_path / "sbom"

    with pytest.raises(SystemExit, match="not distribution-ready"):
        main(
            [
                "--mode",
                "sbom",
                "--output",
                str(output),
                "--artifact",
                str(app),
                "--strict-signing",
            ]
        )

    report = json.loads((output / "release-artifact-status.json").read_text())
    assert report["distribution_ready"] is False
    assert report["artifacts"][0]["artifact_type"] == "macos_app"
