#!/usr/bin/env bash
# Build the stdio bridge as a single binary. When a Rust toolchain + src-tauri
# exist, also stage it under the Tauri sidecar slot with the target-triple suffix.
set -euo pipefail

# Prefer the project venv's pyinstaller if present.
if [ -x ".venv/bin/pyinstaller" ]; then PYI=".venv/bin/pyinstaller"; else PYI="pyinstaller"; fi
"$PYI" --clean --noconfirm simanalysis-bridge.spec

SRC="dist/simanalysis-bridge"
[ -f "${SRC}.exe" ] && SRC="${SRC}.exe"
echo "Built: ${SRC}"

if command -v rustc >/dev/null 2>&1 && [ -d src-tauri ]; then
  TRIPLE="$(rustc -Vv | sed -n 's/^host: //p')"
  mkdir -p src-tauri/binaries
  DEST="src-tauri/binaries/simanalysis-bridge-${TRIPLE}"
  [ -f "${SRC}.exe" ] 2>/dev/null && DEST="${DEST}.exe"
  cp "${SRC}" "${DEST}"
  chmod +x "${DEST}" 2>/dev/null || true
  echo "Sidecar staged: ${DEST}"
else
  echo "NOTE: rustc/src-tauri not present; skipping target-triple staging (done in the Tauri phase)."
fi
