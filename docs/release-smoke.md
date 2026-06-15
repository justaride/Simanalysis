# Public v3 Release Smoke

This checklist is the packaging smoke gate for Public v3. It is not a signing,
notarization, or security audit replacement; it proves that a clean checkout can
build the desktop shell, stage the Python sidecar, and run core read-only flows
without touching live Sims files.

## Fast Contract Audit

Run this on every release-related PR:

```bash
python scripts/release_smoke.py --mode audit
```

It verifies the current release contract:

- Tauri bundles `web/dist`.
- Tauri regenerates the frontend with `npm --prefix web run build`.
- Tauri declares the `simanalysis-bridge` sidecar.
- The sidecar build script stages the target-triple suffixed binary under
  `src-tauri/binaries/`.
- `pyproject.toml` exposes the `simanalysis-bridge` console entry point.

## Source Bridge Smoke

Run this when bridge commands or release packaging changes:

```bash
python scripts/release_smoke.py --mode source
```

The smoke creates a temporary Sims-like tree and runs:

- `scan-mods`
- `doctor-scan`
- `update-staging-plan`

The temporary Update Desk plan must not copy into Mods and must leave staged
downloads in place.

## Full Local Release Smoke

Run from a fresh checkout when cutting a Public v3 release candidate:

```bash
python scripts/release_smoke.py --mode full
```

This performs the heavier build path:

1. Install Python development dependencies plus PyInstaller.
2. Install the root Tauri CLI dependencies.
3. Install and build the web frontend.
4. Build and stage the `simanalysis-bridge` sidecar.
5. Run the source bridge smoke.
6. Run Rust fmt/test/build for `src-tauri`.
7. Run the Tauri bundle build.

Use `--skip-tauri-bundle` only for local diagnosis where the final platform
bundle is known to be blocked by host tooling. It is not a release pass.

On macOS, the default full smoke builds the `.app` bundle and verifies that it
contains both the desktop binary and the `simanalysis-bridge` sidecar. Use
`--include-dmg` for the later distributable DMG check; that path can require
additional host permissions/tooling and belongs with the final release/Slice 12
signing pass.

## Manual First-Run Checklist

After the full build, start the generated app bundle on a clean test profile.
Use a fixture or disposable Sims folder first, not the user's live Mods folder.

- The app opens without a terminal-only workaround.
- The sidecar responds through the desktop shell.
- A basic Mods scan completes.
- Doctor runs and shows static script security evidence.
- Update Desk preview can read a staged loose package and does not apply it.
- No horizontal overflow appears on desktop or a narrow viewport.
- No workflow mutates live Sims files without a manifest/snapshot and explicit
  user confirmation.
