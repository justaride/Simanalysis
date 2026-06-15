from __future__ import annotations

import json
from pathlib import Path

from scripts.release_security import generate_sboms, signing_status


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
