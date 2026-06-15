#!/usr/bin/env python3
"""Release security and SBOM gate for Simanalysis Public v3."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
MACOS_APP_REQUIRED_FILES = (
    Path("Contents/MacOS/simanalysis-desktop"),
    Path("Contents/MacOS/simanalysis-bridge"),
)
WINDOWS_ARTIFACT_TYPES = {
    ".exe": "windows_executable",
    ".msi": "windows_installer",
}


@dataclass(frozen=True)
class CommandCheck:
    name: str
    cmd: list[str]
    cwd: Path = ROOT
    optional: bool = False
    quiet_stdout: bool = False


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _component(component_type: str, name: str, version: str | None = None) -> dict[str, str]:
    payload = {"type": component_type, "name": name}
    if version:
        payload["version"] = version
    return payload


def _cyclonedx_bom(name: str, components: list[dict[str, str]]) -> dict[str, object]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "component": {"type": "application", "name": name},
        },
        "components": sorted(
            components,
            key=lambda item: (item.get("type", ""), item.get("name", ""), item.get("version", "")),
        ),
    }


def _npm_components(lock_path: Path) -> list[dict[str, str]]:
    data = json.loads(_read(lock_path))
    packages = data.get("packages", {})
    components: list[dict[str, str]] = []
    if not isinstance(packages, dict):
        return components
    for path, payload in packages.items():
        if not path.startswith("node_modules/") or not isinstance(payload, dict):
            continue
        version = payload.get("version")
        if not isinstance(version, str):
            continue
        name = path.removeprefix("node_modules/")
        components.append(_component("library", name, version))
    return components


def _cargo_components(lock_path: Path) -> list[dict[str, str]]:
    components: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in _read(lock_path).splitlines():
        line = raw_line.strip()
        if line == "[[package]]":
            if current.get("name") and current.get("version"):
                components.append(_component("library", current["name"], current["version"]))
            current = {}
            continue
        if line.startswith("name = "):
            current["name"] = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("version = "):
            current["version"] = line.split("=", 1)[1].strip().strip('"')
    if current.get("name") and current.get("version"):
        components.append(_component("library", current["name"], current["version"]))
    return components


def _python_dependencies(pyproject_path: Path) -> list[dict[str, str]]:
    components: list[dict[str, str]] = []
    in_dependencies = False
    for raw_line in _read(pyproject_path).splitlines():
        line = raw_line.strip()
        if line == "dependencies = [":
            in_dependencies = True
            continue
        if in_dependencies and line == "]":
            break
        if not in_dependencies or not line.startswith('"'):
            continue
        requirement = line.rstrip(",").strip().strip('"')
        name = requirement
        for marker in ("<", ">", "=", "~", "!", ";", "["):
            if marker in name:
                name = name.split(marker, 1)[0]
        name = name.strip()
        if name:
            components.append(_component("library", name))
    return components


def generate_sboms(output_dir: Path = ROOT / "dist" / "sbom") -> list[Path]:
    manifests = {
        "simanalysis-python.cdx.json": _python_dependencies(ROOT / "pyproject.toml"),
        "simanalysis-root-npm.cdx.json": _npm_components(ROOT / "package-lock.json"),
        "simanalysis-web-npm.cdx.json": _npm_components(ROOT / "web" / "package-lock.json"),
        "simanalysis-rust.cdx.json": _cargo_components(ROOT / "src-tauri" / "Cargo.lock"),
    }
    written: list[Path] = []
    combined_components: list[dict[str, str]] = []
    for filename, components in manifests.items():
        combined_components.extend(components)
        path = output_dir / filename
        _write_json(path, _cyclonedx_bom(filename.removesuffix(".cdx.json"), components))
        written.append(path)
    combined = output_dir / "simanalysis-combined.cdx.json"
    _write_json(combined, _cyclonedx_bom("simanalysis", combined_components))
    written.append(combined)
    return written


def assert_sbom_shape(paths: list[Path]) -> None:
    for path in paths:
        payload = json.loads(_read(path))
        if payload.get("bomFormat") != "CycloneDX":
            raise SystemExit(f"{path} is not a CycloneDX BOM")
        components = payload.get("components")
        if not isinstance(components, list) or not components:
            raise SystemExit(f"{path} has no components")
        print(f"PASS: SBOM {path} contains {len(components)} components")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT / "src") if not current else f"{ROOT / 'src'}{os.pathsep}{current}"
    return env


def run_check(check: CommandCheck) -> bool:
    if check.optional and not shutil.which(check.cmd[0]):
        print(f"SKIP: {check.name} requires {check.cmd[0]}")
        return True
    print(f"$ {' '.join(check.cmd)}")
    completed = subprocess.run(
        check.cmd,
        cwd=check.cwd,
        env=_env(),
        check=False,
        stdout=subprocess.DEVNULL if check.quiet_stdout else None,
    )
    if completed.returncode == 0:
        print(f"PASS: {check.name}")
        return True
    print(f"FAIL: {check.name} exited {completed.returncode}")
    return False


def run_security_checks(*, include_cargo_audit: bool = False) -> None:
    checks = [
        CommandCheck(
            "Bandit static scan",
            [sys.executable, "-m", "bandit", "-r", "src/simanalysis", "-c", "pyproject.toml"],
        ),
        CommandCheck("pip-audit local environment", [sys.executable, "-m", "pip_audit", "--local"]),
        CommandCheck(
            "root npm production audit", ["npm", "audit", "--audit-level=high", "--omit=dev"]
        ),
        CommandCheck(
            "web npm production audit",
            ["npm", "--prefix", "web", "audit", "--audit-level=high", "--omit=dev"],
        ),
        CommandCheck(
            "Cargo lock metadata",
            [
                "cargo",
                "metadata",
                "--manifest-path",
                "src-tauri/Cargo.toml",
                "--locked",
                "--format-version",
                "1",
            ],
            quiet_stdout=True,
        ),
    ]
    if include_cargo_audit:
        checks.append(CommandCheck("cargo-audit advisory scan", ["cargo", "audit"], optional=True))
    failed = [check.name for check in checks if not run_check(check)]
    if failed:
        raise SystemExit(f"Release security checks failed: {', '.join(failed)}")


def _run_status(cmd: list[str]) -> dict[str, object]:
    if not shutil.which(cmd[0]):
        return {
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": f"{cmd[0]} is not available",
        }
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return {
        "available": True,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _codesign_status(path: Path) -> dict[str, object]:
    result = _run_status(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(path)])
    if not result["available"]:
        return {"status": "not_checked", **result}
    if result["returncode"] == 0:
        return {"status": "verified", **result}
    stderr = str(result.get("stderr", "")).lower()
    if (
        "not signed" in stderr
        or "code object is not signed" in stderr
        or "bundle format unrecognized" in stderr
        or "unsuitable" in stderr
    ):
        return {"status": "unsigned", **result}
    return {"status": "failed", **result}


def _notarization_status(path: Path, codesign: dict[str, object]) -> dict[str, object]:
    if codesign.get("status") != "verified":
        return {
            "status": "not_verified",
            "reason": "codesign verification must pass before notarization is trusted",
        }
    result = _run_status(["xcrun", "stapler", "validate", str(path)])
    if not result["available"]:
        return {"status": "not_checked", **result}
    if result["returncode"] == 0:
        return {"status": "verified", **result}
    return {"status": "not_verified", **result}


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _windows_signature_status(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"status": "missing"}
    executable = _powershell_executable()
    if executable is None:
        return {
            "status": "not_checked",
            "available": False,
            "returncode": None,
            "stdout": "",
            "stderr": "PowerShell is not available",
        }
    command = """
$ErrorActionPreference = 'Stop'
$sig = Get-AuthenticodeSignature -LiteralPath $args[0]
$cert = $sig.SignerCertificate
[PSCustomObject]@{
  Status = [string]$sig.Status
  StatusMessage = [string]$sig.StatusMessage
  Subject = if ($cert) { [string]$cert.Subject } else { $null }
  Thumbprint = if ($cert) { [string]$cert.Thumbprint } else { $null }
} | ConvertTo-Json -Compress
""".strip()
    result = _run_status(
        [executable, "-NoProfile", "-NonInteractive", "-Command", command, str(path)]
    )
    if not result["available"]:
        return {"status": "not_checked", **result}
    if result["returncode"] != 0:
        return {"status": "failed", **result}
    try:
        payload = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError:
        return {"status": "failed", "reason": "Authenticode output was not JSON", **result}
    if not isinstance(payload, dict):
        return {"status": "failed", "reason": "Authenticode output was not an object", **result}
    authenticode_status = str(payload.get("Status", ""))
    if authenticode_status.casefold() == "valid":
        status = "verified"
    elif authenticode_status.casefold() == "notsigned":
        status = "unsigned"
    else:
        status = "not_verified"
    return {
        "status": status,
        "authenticode_status": authenticode_status,
        "status_message": payload.get("StatusMessage"),
        "subject": payload.get("Subject"),
        "thumbprint": payload.get("Thumbprint"),
        **result,
    }


def _verify_macos_app(path: Path) -> dict[str, object]:
    missing = [
        required.as_posix()
        for required in MACOS_APP_REQUIRED_FILES
        if not (path / required).exists()
    ]
    codesign = _codesign_status(path) if path.exists() else {"status": "missing"}
    notarization = _notarization_status(path, codesign)
    ready = (
        not missing
        and codesign.get("status") == "verified"
        and notarization.get("status") == "verified"
    )
    return {
        "path": str(path),
        "artifact_type": "macos_app",
        "exists": path.exists(),
        "required_files_present": not missing,
        "missing_files": missing,
        "codesign": codesign,
        "notarization": notarization,
        "distribution_ready": ready,
    }


def _verify_windows_artifact(path: Path) -> dict[str, object]:
    signature = _windows_signature_status(path)
    return {
        "path": str(path),
        "artifact_type": WINDOWS_ARTIFACT_TYPES[path.suffix.casefold()],
        "exists": path.exists(),
        "signature": signature,
        "distribution_ready": path.exists() and signature.get("status") == "verified",
    }


def _verify_unknown_artifact(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "artifact_type": "unsupported",
        "exists": path.exists(),
        "distribution_ready": False,
        "reason": "No release verifier is defined for this artifact type",
    }


def _verify_release_artifact(path: Path) -> dict[str, object]:
    if path.name.endswith(".app"):
        return _verify_macos_app(path)
    if path.suffix.casefold() in WINDOWS_ARTIFACT_TYPES:
        return _verify_windows_artifact(path)
    return _verify_unknown_artifact(path)


def verify_release_artifacts(paths: list[Path], *, strict: bool = False) -> dict[str, object]:
    artifacts = [_verify_release_artifact(path) for path in paths]
    ready = bool(artifacts) and all(
        bool(artifact.get("distribution_ready")) for artifact in artifacts
    )
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "distribution_ready": ready,
        "artifacts": artifacts,
        "claim": "Do not distribute as signed/notarized unless distribution_ready is true.",
    }
    if strict and not ready:
        raise SystemExit("Release artifacts are not distribution-ready")
    return report


def _env_status(name: str, *, expose_value: bool = False) -> dict[str, object]:
    value = os.environ.get(name)
    status: dict[str, object] = {"name": name, "present": bool(value)}
    if expose_value and value:
        status["value"] = value
    return status


def _notarization_env_status() -> dict[str, object]:
    names = ["APPLE_ID", "APPLE_PASSWORD", "APPLE_TEAM_ID"]
    missing = [name for name in names if not os.environ.get(name)]
    return {
        "required": names,
        "present": [name for name in names if name not in missing],
        "missing": missing,
    }


def _codesigning_identity_status() -> dict[str, object]:
    result = _run_status(["security", "find-identity", "-v", "-p", "codesigning"])
    stdout = str(result.get("stdout", ""))
    valid_count = 0
    for line in stdout.splitlines():
        if "valid identities found" not in line:
            continue
        parts = line.strip().split()
        if parts and parts[0].isdigit():
            valid_count = int(parts[0])
            break
    return {
        "valid_count": valid_count,
        **result,
    }


def _macos_signing_status() -> dict[str, object]:
    identity_env = _env_status("APPLE_SIGNING_IDENTITY", expose_value=True)
    notarization_env = _notarization_env_status()
    identities = _codesigning_identity_status()
    blockers: list[str] = []
    if identities.get("available") is False:
        blockers.append("macOS security tool is not available")
    elif int(identities.get("valid_count", 0)) <= 0:
        blockers.append("No valid macOS code signing identities found")
    if not identity_env["present"]:
        blockers.append("APPLE_SIGNING_IDENTITY is not set")
    for name in notarization_env["missing"]:
        blockers.append(f"{name} is not set")
    return {
        "developer_id_identity_env": identity_env,
        "notarization_env": notarization_env,
        "codesigning_identities": identities,
        "blockers": blockers,
        "status": "blocked" if blockers else "ready_for_artifact_verification",
    }


def _windows_signing_status() -> dict[str, object]:
    certificate_env = _env_status("WINDOWS_SIGNING_CERT")
    blockers = []
    if not certificate_env["present"]:
        blockers.append("WINDOWS_SIGNING_CERT is not set")
    return {
        "certificate_env": certificate_env,
        "blockers": blockers,
        "status": "blocked" if blockers else "ready_for_artifact_verification",
    }


def signing_status() -> dict[str, object]:
    return {
        "macos": _macos_signing_status(),
        "windows": _windows_signing_status(),
        "linux": {
            "signing_status": "pending if distributing packaged artifacts",
            "status": "pending",
        },
        "claim": "Do not describe artifacts as signed or notarized until the relevant status is verified.",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("sbom", "check", "full"), default="check")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "sbom")
    parser.add_argument("--include-cargo-audit", action="store_true")
    parser.add_argument(
        "--artifact",
        action="append",
        type=Path,
        default=[],
        help="Release artifact path to verify for distribution readiness.",
    )
    parser.add_argument(
        "--strict-signing",
        action="store_true",
        help="Fail if provided release artifacts are not distribution-ready.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths: list[Path] = []
    if args.mode in {"sbom", "full"}:
        paths = generate_sboms(args.output)
        assert_sbom_shape(paths)
    if args.mode in {"check", "full"}:
        run_security_checks(include_cargo_audit=args.include_cargo_audit)
    if args.mode == "full":
        _write_json(args.output / "signing-status.json", signing_status())
        print(f"PASS: signing status checklist written to {args.output / 'signing-status.json'}")
    if args.artifact:
        report = verify_release_artifacts(args.artifact)
        path = args.output / "release-artifact-status.json"
        _write_json(path, report)
        status = "PASS" if report["distribution_ready"] else "BLOCKED"
        print(f"{status}: release artifact status written to {path}")
        if args.strict_signing and not report["distribution_ready"]:
            raise SystemExit("Release artifacts are not distribution-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
