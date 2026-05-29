"""`simanalysis-bridge` — headless NDJSON stdio entry point for the Tauri desktop app."""

from __future__ import annotations

import argparse
import sys
import traceback

from simanalysis.bridge import commands
from simanalysis.bridge.protocol import setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simanalysis-bridge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_mods = sub.add_parser("scan-mods")
    p_mods.add_argument("path")
    p_mods.add_argument("--quick", action="store_true")
    p_mods.add_argument("--no-recursive", dest="recursive", action="store_false")
    p_mods.set_defaults(recursive=True)

    p_tray = sub.add_parser("scan-tray")
    p_tray.add_argument("path")

    p_save = sub.add_parser("analyze-save")
    p_save.add_argument("save_path")
    p_save.add_argument("mods_path")

    p_thumb = sub.add_parser("thumbnail")
    p_thumb.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    emit = setup()
    try:
        commands.DISPATCH[args.command](args, emit)
        return 0
    except ValueError as exc:
        emit.error(str(exc), code="INVALID_INPUT")
        return 2
    except BrokenPipeError:
        return 0
    except Exception as exc:
        traceback.print_exc()
        emit.error(f"{type(exc).__name__}: {exc}", code="INTERNAL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
