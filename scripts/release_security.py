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


def signing_status() -> dict[str, object]:
    return {
        "macos": {
            "developer_id_identity_env": "APPLE_SIGNING_IDENTITY",
            "notarization_env": ["APPLE_ID", "APPLE_PASSWORD", "APPLE_TEAM_ID"],
            "status": "pending",
        },
        "windows": {
            "certificate_env": "WINDOWS_SIGNING_CERT",
            "status": "pending",
        },
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
