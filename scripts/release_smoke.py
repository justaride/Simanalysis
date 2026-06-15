#!/usr/bin/env python3
"""Release smoke gate for Simanalysis desktop packaging.

The default `audit` mode is intentionally lightweight and CI-friendly. It
checks that the repository still exposes the packaging contracts a release
build depends on. `full` mode runs the heavier clean-checkout build sequence.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str) -> dict[str, object]:
    return json.loads(_read(path))


def _has_project_script(pyproject: str, name: str, target: str) -> bool:
    return f'{name} = "{target}"' in pyproject


def audit_release_contract(root: Path = ROOT) -> list[Check]:
    global ROOT
    previous_root = ROOT
    ROOT = root
    try:
        tauri_conf = _json("src-tauri/tauri.conf.json")
        web_package = _json("web/package.json")
        root_package = _json("package.json")
        pyproject = _read("pyproject.toml")
        sidecar_script = _read("scripts/build-sidecar.sh")
        bridge_spec = _read("simanalysis-bridge.spec")

        build = tauri_conf.get("build", {})
        bundle = tauri_conf.get("bundle", {})
        web_scripts = web_package.get("scripts", {})
        root_scripts = root_package.get("scripts", {})
        external_bins = bundle.get("externalBin", [])

        return [
            Check(
                "tauri frontend dist",
                isinstance(build, dict) and build.get("frontendDist") == "../web/dist",
                "Tauri must bundle the Vite build output from web/dist.",
            ),
            Check(
                "tauri frontend build command",
                isinstance(build, dict)
                and build.get("beforeBuildCommand") == "npm --prefix web run build",
                "Tauri release builds must regenerate the web frontend.",
            ),
            Check(
                "tauri sidecar slot",
                isinstance(external_bins, list) and "binaries/simanalysis-bridge" in external_bins,
                "Tauri must declare the simanalysis-bridge external binary.",
            ),
            Check(
                "root tauri cli script",
                isinstance(root_scripts, dict) and root_scripts.get("tauri") == "tauri",
                "Root package.json must expose the Tauri CLI.",
            ),
            Check(
                "web build script",
                isinstance(web_scripts, dict) and web_scripts.get("build") == "vite build",
                "web/package.json must expose a Vite build script.",
            ),
            Check(
                "python bridge console script",
                _has_project_script(pyproject, "simanalysis-bridge", "simanalysis.bridge:main"),
                "pyproject.toml must expose simanalysis-bridge for PyInstaller/source smoke.",
            ),
            Check(
                "sidecar pyinstaller spec",
                "simanalysis-bridge.spec" in sidecar_script
                and "dist/simanalysis-bridge" in sidecar_script,
                "scripts/build-sidecar.sh must build the bridge sidecar, not the old GUI app.",
            ),
            Check(
                "sidecar target triple staging",
                "rustc -Vv" in sidecar_script
                and "src-tauri/binaries/simanalysis-bridge-${TRIPLE}" in sidecar_script,
                "The sidecar must be staged with Tauri's target-triple suffix.",
            ),
            Check(
                "bridge entrypoint",
                "run_bridge.py" in bridge_spec and "name='simanalysis-bridge'" in bridge_spec,
                "simanalysis-bridge.spec must package the headless bridge entrypoint.",
            ),
        ]
    finally:
        ROOT = previous_root


def assert_audit_passes(checks: list[Check]) -> None:
    failed = [check for check in checks if not check.ok]
    for check in checks:
        prefix = "PASS" if check.ok else "FAIL"
        print(f"{prefix}: {check.name} - {check.detail}")
    if failed:
        names = ", ".join(check.name for check in failed)
        raise SystemExit(f"Release smoke audit failed: {names}")


def _env_with_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT / "src") if not current else f"{ROOT / 'src'}{os.pathsep}{current}"
    return env


def run_command(cmd: list[str], *, cwd: Path = ROOT, timeout: int = 900) -> None:
    printable = " ".join(cmd)
    print(f"$ {printable}")
    subprocess.run(cmd, cwd=cwd, env=_env_with_pythonpath(), check=True, timeout=timeout)


def install_python_build_dependencies() -> None:
    if shutil.which("uv"):
        run_command(["uv", "pip", "install", "-e", ".[dev]", "pyinstaller"], timeout=1200)
        return
    run_command([sys.executable, "-m", "pip", "install", "-e", ".[dev]", "pyinstaller"])


def _bridge_json_events(cmd: list[str], *, timeout: int = 60) -> list[dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "run_bridge.py"), *cmd],
        cwd=ROOT,
        env=_env_with_pythonpath(),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    events: list[dict[str, object]] = []
    for line in completed.stdout.splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def run_source_bridge_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="simanalysis-release-smoke-") as tmp:
        root = Path(tmp)
        sims4 = root / "The Sims 4"
        mods = sims4 / "Mods"
        staging = root / "Update Staging"
        mods.mkdir(parents=True)
        staging.mkdir(parents=True)
        (mods / "baseline.package").write_bytes(b"DBPF")
        (staging / "candidate.package").write_bytes(b"DBPF")

        scan_events = _bridge_json_events(["scan-mods", str(mods), "--quick", "--no-recursive"])
        doctor_events = _bridge_json_events(["doctor-scan", str(sims4), "--mods", str(mods)])
        plan_events = _bridge_json_events(
            ["update-staging-plan", str(staging), "--mods", str(mods)]
        )

        for name, events in {
            "scan-mods": scan_events,
            "doctor-scan": doctor_events,
            "update-staging-plan": plan_events,
        }.items():
            kinds = [event.get("type") for event in events]
            if "error" in kinds or "result" not in kinds:
                raise SystemExit(f"{name} bridge smoke failed: {events}")
            print(f"PASS: bridge {name} emitted result without mutating live Sims paths")

        if not (staging / "candidate.package").exists():
            raise SystemExit("update-staging-plan mutated the staged package during smoke")
        if (mods / "candidate.package").exists():
            raise SystemExit("update-staging-plan copied into Mods during smoke")


def verify_tauri_app_bundle() -> None:
    app_dir = ROOT / "src-tauri" / "target" / "release" / "bundle" / "macos" / "Simanalysis.app"
    if platform.system() != "Darwin":
        print("SKIP: app bundle content check is currently macOS-specific")
        return
    desktop_bin = app_dir / "Contents" / "MacOS" / "simanalysis-desktop"
    bridge_bin = app_dir / "Contents" / "MacOS" / "simanalysis-bridge"
    missing = [str(path) for path in (desktop_bin, bridge_bin) if not path.exists()]
    if missing:
        raise SystemExit(f"Tauri app bundle is missing expected binaries: {missing}")
    print(f"PASS: Tauri app bundle contains desktop binary and bridge sidecar: {app_dir}")


def run_full_release_smoke(skip_tauri_bundle: bool = False, include_dmg: bool = False) -> None:
    assert_audit_passes(audit_release_contract())
    install_python_build_dependencies()
    run_command(["npm", "ci"], timeout=1200)
    run_command(["npm", "--prefix", "web", "ci"], timeout=1200)
    run_command(["npm", "--prefix", "web", "run", "build"], timeout=900)
    run_command(["./scripts/build-sidecar.sh"], timeout=1200)
    run_source_bridge_smoke()
    run_command(["cargo", "fmt", "--manifest-path", "src-tauri/Cargo.toml", "--check"])
    run_command(["cargo", "test", "--manifest-path", "src-tauri/Cargo.toml", "--lib"], timeout=1200)
    run_command(["cargo", "build", "--manifest-path", "src-tauri/Cargo.toml"], timeout=1200)
    if skip_tauri_bundle:
        print("SKIP: Tauri bundle build skipped by --skip-tauri-bundle")
    elif include_dmg:
        run_command(["npm", "run", "tauri", "--", "build"], timeout=2400)
    else:
        run_command(["npm", "run", "tauri", "--", "build", "--bundles", "app"], timeout=2400)
        verify_tauri_app_bundle()
    host = platform.machine().lower()
    if shutil.which("rustc"):
        print(f"PASS: release smoke completed on {platform.system()} {host}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("audit", "source", "full"), default="audit")
    parser.add_argument(
        "--skip-tauri-bundle",
        action="store_true",
        help="Run full smoke through cargo build but skip the final GUI bundle.",
    )
    parser.add_argument(
        "--include-dmg",
        action="store_true",
        help="Use Tauri's default platform bundle set, including DMG on macOS.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "audit":
        assert_audit_passes(audit_release_contract())
    elif args.mode == "source":
        assert_audit_passes(audit_release_contract())
        run_source_bridge_smoke()
    else:
        run_full_release_smoke(
            skip_tauri_bundle=args.skip_tauri_bundle,
            include_dmg=args.include_dmg,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
