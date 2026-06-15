# Building Simanalysis Desktop

Simanalysis desktop is a Tauri app with a Vite/React frontend and a PyInstaller
`simanalysis-bridge` sidecar. The old standalone PyInstaller web-server app is
not the Public v3 release path.

## Prerequisites

- Python 3.9+
- Node.js and npm
- Rust stable toolchain
- Platform-specific Tauri build prerequisites

## Development Build

```bash
python -m pip install -e ".[dev]" pyinstaller
npm ci
npm --prefix web ci
npm --prefix web run build
./scripts/build-sidecar.sh
cargo test --manifest-path src-tauri/Cargo.toml --lib
cargo build --manifest-path src-tauri/Cargo.toml
```

`scripts/build-sidecar.sh` builds the headless `simanalysis-bridge` binary and
stages it under `src-tauri/binaries/` with the target triple Tauri expects.

## Release Smoke

Fast contract audit:

```bash
python scripts/release_smoke.py --mode audit
```

Source bridge smoke with temporary Sims-like fixtures:

```bash
python scripts/release_smoke.py --mode source
```

Full local release smoke from a clean checkout:

```bash
python scripts/release_smoke.py --mode full
```

See [`docs/release-smoke.md`](docs/release-smoke.md) for the first-run checklist
and release-candidate expectations.

## Tauri Bundle

After the sidecar has been staged and `web/dist` exists, build the desktop
bundle:

```bash
npm run tauri -- build
```

The generated bundle is platform-specific and lives under `src-tauri/target/`.
Public v3 artifacts still require the later release slice for SBOM, signing,
notarization where applicable, and final documentation truth checks.

The default full release smoke builds the macOS `.app` bundle. Run
`python scripts/release_smoke.py --mode full --include-dmg` only when validating
the final distributable DMG path.
