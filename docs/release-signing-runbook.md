# Public v3 Release Signing Runbook

This runbook turns the Public v3 signing blocker into an operational checklist.
It does not replace the security gate in `scripts/release_security.py`; it
explains how to satisfy that gate without weakening the release claim.

Primary platform references:

- Apple: https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution
- Microsoft SignTool: https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool
- Microsoft SignTool CLI: https://learn.microsoft.com/en-us/dotnet/framework/tools/signtool-exe

## Current Blocker

Public v3 is blocked until strict artifact verification passes on real release
artifacts. The current local signing preflight reports:

- macOS: no valid code signing identities.
- macOS: `APPLE_SIGNING_IDENTITY` is not set.
- macOS: `APPLE_ID`, `APPLE_PASSWORD`, and `APPLE_TEAM_ID` are not set.
- Windows: `WINDOWS_SIGNING_CERT` is not set.

Do not publish a release, README claim, changelog claim, or download link that
describes Simanalysis as signed, notarized, or distribution-ready while these
remain blocked.

## Inputs

macOS release signing requires:

- An Apple Developer Program account.
- A Developer ID Application certificate with private key available in the
  release keychain.
- `APPLE_SIGNING_IDENTITY` set to the non-secret identity label used by
  `codesign`.
- `APPLE_ID`, `APPLE_PASSWORD`, and `APPLE_TEAM_ID` available only in the
  release environment.
- Xcode command line tools with `codesign`, `xcrun notarytool`, and
  `xcrun stapler`.

Windows release signing requires:

- A code signing certificate suitable for Authenticode signing.
- The certificate installed or otherwise available to the Windows signing
  environment.
- `WINDOWS_SIGNING_CERT` set to the non-secret certificate selector used by the
  release signing step.
- Windows SDK SignTool available in the release environment.

Linux release signing requires:

- An explicit distribution decision for the artifact format used.
- Any signing key, checksum, or package repository evidence attached to the
  release artifact set.

## Preflight

Run the non-secret readiness check before building release candidates:

```bash
python scripts/release_security.py --mode full --output dist/sbom
cat dist/sbom/signing-status.json
```

Expected before final artifact signing:

- `macos.status` is `ready_for_artifact_verification`.
- `macos.codesigning_identities.valid_count` is greater than `0`.
- `macos.developer_id_identity_env.present` is `true`.
- `macos.notarization_env.missing` is empty.
- `windows.status` is `ready_for_artifact_verification` for Windows release
  candidates.

The preflight intentionally does not print secret values. It is still not a
release pass; it only proves the signing environment is ready for artifact
verification.

## Build Candidate

Build from a clean checkout or a clean release worktree:

```bash
python scripts/release_smoke.py --mode full
python scripts/release_security.py --mode full --output dist/sbom
```

The smoke gate must build the `.app`, include both `simanalysis-desktop` and
`simanalysis-bridge`, and run scan, Doctor, and Update Desk planning against
temporary fixtures without mutating live Sims paths.

## macOS Signing And Notarization

The exact signing command may need adjustment if the Tauri bundle layout changes.
The required invariant is that the final `.app` passes deep strict verification,
notarization, and stapler validation.

Use the Developer ID Application identity from the preflight:

```bash
codesign --force --deep --options runtime \
  --sign "$APPLE_SIGNING_IDENTITY" \
  src-tauri/target/release/bundle/macos/Simanalysis.app

ditto -c -k --keepParent \
  src-tauri/target/release/bundle/macos/Simanalysis.app \
  dist/Simanalysis-macos.zip

xcrun notarytool submit dist/Simanalysis-macos.zip \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait

xcrun stapler staple src-tauri/target/release/bundle/macos/Simanalysis.app
```

Then verify with the repo gate:

```bash
python scripts/release_security.py --mode sbom --output dist/sbom \
  --artifact src-tauri/target/release/bundle/macos/Simanalysis.app \
  --strict-signing
```

The macOS artifact is release-ready only when
`dist/sbom/release-artifact-status.json` reports:

- `distribution_ready: true`
- `codesign.status: verified`
- `notarization.status: verified`
- `required_files_present: true`

## Windows Signing

Build the Windows release artifact in the Windows release environment, then sign
the `.exe` or `.msi` with SignTool using the selected certificate. The timestamp
server may vary by certificate provider; keep it in the release record.

Example shape:

```powershell
signtool sign /fd SHA256 /td SHA256 /tr <timestamp-url> `
  /n "$env:WINDOWS_SIGNING_CERT" `
  path\to\Simanalysis.exe

signtool verify /pa /v path\to\Simanalysis.exe
```

Then verify with the repo gate:

```bash
python scripts/release_security.py --mode sbom --output dist/sbom \
  --artifact path/to/Simanalysis.exe \
  --strict-signing
```

The Windows artifact is release-ready only when
`dist/sbom/release-artifact-status.json` reports:

- `distribution_ready: true`
- `signature.status: verified`
- `signature.authenticode_status: Valid`

## Linux Decision

Before shipping Linux artifacts, record the actual distribution path and signing
decision in the release notes. Acceptable evidence could be a signed package
repository, signed checksum files, or an explicit "unsigned local build only"
status if Linux is not part of the Public v3 binary release.

Do not imply Linux artifacts are signed unless the release artifact set includes
that evidence.

## Final Release Evidence

Attach or retain:

- `dist/sbom/simanalysis-combined.cdx.json`
- platform-specific SBOM files from `dist/sbom/`
- `dist/sbom/signing-status.json`
- `dist/sbom/release-artifact-status.json`
- GitHub CI run URL for the release commit
- release smoke command output
- release security command output
- platform artifact paths and hashes

Public v3 can be described as distribution-ready only after strict artifact
verification passes for every artifact being offered to users.
