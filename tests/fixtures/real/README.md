# Real Fixture Corpus

This directory is the contract for T0.2 real-file tests.

Real Sims 4 files may only be committed here when redistribution is explicitly
allowed and provenance is recorded in `corpus-manifest.json`. Files from the
local Mods folder, downloaded CC, private saves, tray files, or crash logs with
personal paths must go under the git-ignored `tests/fixtures/local/` tree
instead.

`pytest -m real` reads the manifest and runs every assertion it can prove from
available files. Missing local-only files are skipped, not silently treated as
passing real coverage.

Required package sidecars live under `golden/` and record DBPF metadata checked
against the parser:

- header fields needed by parser tests
- resource count
- selected known TGI keys
- expected tuning IDs/classes when the package is a tuning fixture

The first required real package role is `tuning_mod`; it exists to prevent the
scanner from ever proving tuning extraction only against generated fixtures.

## Committed Redistributable Fixture

`packages/s4tk_minimal_buff_tuning.package` is a self-owned, MIT-licensed test
package generated from `source/s4tk_minimal_buff_tuning.xml` with
`@s4tk/models` 0.6.14. It contains one Buff tuning resource and exists so CI can
prove real DBPF parsing and tuning extraction without relying on third-party CC
redistribution rights.

To regenerate it:

```bash
NODE_PATH=/path/to/node_modules \
  node tests/fixtures/real/source/build_s4tk_minimal_buff_tuning.cjs
```

## Local Corpus Setup

Use the builder with an explicit source override for each local-only manifest
item:

```bash
python tests/fixtures/build_real_corpus.py \
  --source "local_tuning_mod=/path/to/real/tuning_mod.package"
```

The builder copies the package into `tests/fixtures/local/packages/` and writes
the parser-derived golden sidecar into `tests/fixtures/local/golden/`. Both
paths are git-ignored.
