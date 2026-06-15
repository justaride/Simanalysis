from __future__ import annotations

import shutil
from pathlib import Path

from scripts.release_smoke import audit_release_contract

ROOT = Path(__file__).resolve().parents[2]


def test_release_smoke_audit_passes_for_current_packaging_contract() -> None:
    checks = audit_release_contract(ROOT)

    assert checks
    assert all(check.ok for check in checks)


def test_release_smoke_audit_catches_missing_tauri_sidecar(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", ".venv", "node_modules"))

    config_path = repo / "src-tauri" / "tauri.conf.json"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            '"externalBin": ["binaries/simanalysis-bridge"]',
            '"externalBin": []',
        ),
        encoding="utf-8",
    )

    checks = audit_release_contract(repo)
    sidecar_check = next(check for check in checks if check.name == "tauri sidecar slot")

    assert not sidecar_check.ok
