# Simanalysis

Simanalysis is a local-first safety and analysis toolkit for The Sims 4 mods,
custom content, saves, Tray files, cache files, and update staging.

It is not made by, endorsed by, or affiliated with Electronic Arts, Maxis, or
The Sims. It does not run mod code, edit saves, claim malware verdicts, or mark
unknown mods safe.

## Current Status

Simanalysis is in active Public v3 development. It is not generally
production-ready yet, and public release docs should not describe it that way.

The current codebase has several verified foundations:

- Static package, resource, tuning, script-archive, STBL, and SimData parsing.
- Local SQLite inventory ledger with snapshots and file-change history.
- Doctor, Crash Autopsy, Treatment, Operating Table, Patch Day, Cache Doctor,
  Save Protector, Tray Protector, and Update Desk surfaces.
- Manifest-first mutating flows for selected cleanup, cache quarantine, treatment
  steps, explicit loose-file Update Desk copy actions, and safe ZIP-member
  Update Desk actions via staging.
- Conservative classification, conflict metadata, and static script-risk signals.
- Tauri desktop shell with Python sidecar, release smoke harness, and SBOM/security
  gate.

Remaining Public v3 work is tracked in
[docs/public-v3-workplan.md](docs/public-v3-workplan.md).

## What It Can Do Today

Simanalysis can help you inspect a Sims 4 user folder before launching the game:

- Scan Mods and package resources without mutating files.
- Detect exact duplicates, likely overrides, tuning/resource conflicts, and
  suspicious or unsupported parser states.
- Track local file history through an app-owned inventory ledger.
- Review Patch Day state without automatically re-enabling unknown mods.
- Review saves, Tray groups, and known cache targets with evidence labels.
- Stage, apply, and undo only the mutating actions that already have manifest
  support and explicit user approval.
- Generate Update Desk plans for staged downloads and commit selected safe ZIP
  package/script members through extraction staging, without extracting archives
  directly into Mods.
- Generate release SBOMs and run Python, web, npm, and Cargo lock security gates.

## What It Does Not Claim Yet

These boundaries are deliberate:

- No automatic mod update installation.
- No archive extraction directly to `Mods`.
- No save-file editing, repair, or restore.
- No malware detection verdicts.
- No guarantee that a likely dependency or conflict is definitely the cause of a
  gameplay issue.
- No EA/Maxis official status, branding, or asset affiliation.
- No signed/notarized public release artifact until real release evidence exists.

## Install From Source

PyPI publishing is planned for Public v3. Until then, use a source checkout.

```bash
git clone https://github.com/justaride/Simanalysis.git
cd Simanalysis
python -m pip install -e ".[dev,docs]"
```

The compatibility shims also install from `pyproject.toml`:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Useful CLI Commands

```bash
# Static Mods analysis
simanalysis analyze "~/Documents/Electronic Arts/The Sims 4/Mods" --output report.json --format json

# Local inventory ledger
simanalysis ledger scan "~/Documents/Electronic Arts/The Sims 4" --format json
simanalysis ledger history --format json

# Doctor and trust surfaces
simanalysis doctor "~/Documents/Electronic Arts/The Sims 4" --format json
simanalysis patch-day status "~/Documents/Electronic Arts/The Sims 4" --format json
simanalysis cache status "~/Documents/Electronic Arts/The Sims 4" --format json
simanalysis save-protector status "~/Documents/Electronic Arts/The Sims 4" --format json
simanalysis tray status "~/Documents/Electronic Arts/The Sims 4" --format json

# Update Desk planning and guarded loose-file or ZIP-member actions
simanalysis updates plan /path/to/staging --mods "~/Documents/Electronic Arts/The Sims 4/Mods" --format json
simanalysis updates commit /path/to/plan.json --action update-001 --format json
simanalysis updates undo /path/to/update-manifest.json --format json
```

Mutating commands are intentionally narrow. They should refuse unsafe paths,
symlinks, stale evidence, process-guard failures, collisions, and missing
manifest proof.

## Desktop Development

```bash
npm install
npm --prefix web install
npm run tauri dev
```

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) and
[docs/release-smoke.md](docs/release-smoke.md) for the Tauri sidecar packaging
path.

## Release Gates

Before a Public v3 release candidate, run the relevant local gates:

```bash
ruff check .
ruff format --check .
mypy src
pytest -q
pytest -m real --no-cov
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --lib
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
node --test web/src/*.test.js web/src/views/*.test.js
npm --prefix web run lint
npm --prefix web run build
python scripts/release_smoke.py --mode full
python scripts/release_security.py --mode full --output dist/sbom
python scripts/release_security.py --mode sbom --output dist/sbom \
  --artifact src-tauri/target/release/bundle/macos/Simanalysis.app \
  --artifact path/to/Simanalysis.exe \
  --strict-signing
```

CI must be green before merging release work. Signing/notarization must be
verified on real artifacts before docs or changelogs claim signed builds.

## Documentation

- [Current status](docs/STATUS.md)
- [Implementation status](IMPLEMENTATION_STATUS.md)
- [Public v3 workplan](docs/public-v3-workplan.md)
- [Implementation roadmap](IMPLEMENTATION_ROADMAP.md)
- [Release smoke harness](docs/release-smoke.md)
- [Release security and SBOM gate](docs/release-security.md)
- [Release signing runbook](docs/release-signing-runbook.md)
- [DBPF format notes](docs/DBPF_FORMAT.md)

## License

MIT License. See [LICENSE](LICENSE).
