"""Build the committed minimal .ts4script real fixture from source files."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_ZIP_TIME = (2026, 6, 11, 0, 0, 0)
SOURCE_ROOT = Path(__file__).with_name("ts4script_probe")
OUTPUT_PATH = Path(__file__).parents[1] / "scripts" / "minimal_probe.ts4script"


def main() -> None:
    """Write a deterministic ZIP-backed .ts4script fixture."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT_PATH, "w") as archive:
        for source_path in sorted(path for path in SOURCE_ROOT.rglob("*") if path.is_file()):
            archive_name = source_path.relative_to(SOURCE_ROOT).as_posix()
            info = ZipInfo(archive_name, FIXED_ZIP_TIME)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source_path.read_bytes())
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
