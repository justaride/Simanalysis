# DBPF Parser Current Status

**Last consolidated:** 2026-06-15
**Status source:** Phase 0 truth pass plus True Engine STBL reader slice

The old generated DBPF status report is archived at
`docs/archive/status/DBPF_IMPLEMENTATION_STATUS_2025-10-24.md`.

## Implemented

- Reads DBPF headers and Sims 4 v2 index tables, including index constant-field
  flags.
- Extracts TGI resource keys.
- Extracts uncompressed and zlib-compressed resources.
- Treats zlib-compressed resources as compressed based on the DBPF index
  compression flag, even when compressed and decompressed sizes match.
- Parses Sims 4 STBL version 5 string tables into keyed UTF-8 strings with
  explicit `parsed`, `unsupported`, or `malformed` status and warnings.
- Parses Sims 4 SimData `DATA` resources into read-only table, schema, and
  column metadata with explicit `parsed`, `unsupported`, or `malformed` status.
- Surfaces compact parser truth in mod analysis JSON: resource type names,
  resource counts, STBL/SimData parse-status counts, and parser warnings are
  available without dumping full STBL strings or SimData column payloads.
- Handles corrupted or unsupported package data with parser errors instead of
  silent success.
- Uses verified Sims 4 resource type constants from
  `src/simanalysis/formats/types.py`.
- Uses a committed real fixture corpus to pin basic DBPF behavior:
  - S4TK-generated tuning package
  - save-like DBPF resource categorization fixture

## Not Implemented

- RefPack decompression.
- Full SimData row/value decoding, OBJD, image, mesh, and other resource
  payload parsers.
- STBL editing/writing, language inference, and non-v5 STBL parsing.
- Broad curated third-party package corpus. Non-redistributable package testing
  remains local-only through `tests/fixtures/build_real_corpus.py`.
- Complete real-world save parsing beyond DBPF resource-key categorization.

## Verification

Primary gates:

```bash
COVERAGE_FILE=/tmp/simanalysis-real.coverage .venv/bin/python -m pytest -m real --no-cov
COVERAGE_FILE=/tmp/simanalysis-full.coverage .venv/bin/python -m pytest -q
```

The real marker suite is now CI-gated and covers the committed package, script,
log, save, and Tray fixture families.
