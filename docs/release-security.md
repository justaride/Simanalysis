# Public v3 Release Security

This is the security and SBOM gate for Public v3 release candidates. It does
not make the app production-ready by itself, and it does not claim that builds
are signed or notarized.

## SBOM

Generate CycloneDX JSON SBOM files:

```bash
python scripts/release_security.py --mode sbom --output dist/sbom
```

The script writes separate Python, root npm, web npm, and Rust BOMs plus a
combined BOM. Generated files live under `dist/sbom/` and are release artifacts,
not source files.

## Security Checks

Run the release security gate after installing the usual project dependencies
and audit tools:

```bash
python -m pip install -e ".[dev]" "bandit[toml]>=1.9,<2.0" pip-audit
npm ci
npm --prefix web ci
python scripts/release_security.py --mode check
```

The gate runs:

- Bandit over `src/simanalysis`.
- `pip-audit --local` for the installed Python environment.
- Root npm production audit at high-or-higher severity.
- Web npm production audit at high-or-higher severity.
- Cargo lock metadata resolution with `--locked`.

Use `--include-cargo-audit` when `cargo-audit` is installed. Missing
`cargo-audit` is not treated as a pass for final distribution; it is a tool
availability limitation that must be resolved before a public release candidate
is declared security-ready.

## Signing And Notarization

`python scripts/release_security.py --mode full` also writes
`dist/sbom/signing-status.json`. Public v3 docs and release notes must not
claim signed/notarized artifacts until the relevant platform checks are actually
green.

Verify the built release artifact before publishing:

```bash
python scripts/release_security.py --mode sbom \
  --artifact src-tauri/target/release/bundle/macos/Simanalysis.app \
  --artifact path/to/Simanalysis.exe \
  --strict-signing
```

The command writes `dist/sbom/release-artifact-status.json`. On macOS `.app`
artifacts it checks that the desktop binary and `simanalysis-bridge` sidecar are
present, then verifies `codesign` and `xcrun stapler validate`. On Windows
`.exe` and `.msi` artifacts it uses PowerShell `Get-AuthenticodeSignature` and
requires a `Valid` Authenticode status. `--strict-signing` fails unless every
provided artifact is distribution-ready.
Do not use the non-strict report as approval to publish; it is useful for
recording exactly why a local candidate is still blocked.

Required final evidence:

- macOS: Developer ID identity used for signing and notarization/stapling
  verified.
- Windows: release executable/installer Authenticode status is `Valid` for the
  intended certificate.
- Linux: distribution artifact signing decision recorded, or explicit unsigned
  status documented.
- All platforms: SBOM attached to the release artifact set.
