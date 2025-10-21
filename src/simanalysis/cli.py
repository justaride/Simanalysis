"""Command line interface for Simanalysis."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .analyzer import AnalysisResult, ModAnalyzer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simanalysis",
        description="Analyze The Sims 4 mods for common issues and statistics.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the installed version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze the mods stored at the given path."
    )
    analyze_parser.add_argument(
        "path", type=Path, help="Directory that contains Sims 4 mods."
    )
    return parser


def _echo_result(result: AnalysisResult) -> None:
    print(f"Total mods discovered: {result.total_mods}")
    print(f"Performance score: {result.performance_score:.1f}")
    if result.recommendations:
        print("Recommendations:")
        for recommendation in result.recommendations:
            print(f"- {recommendation}")
    else:
        print("No recommendations at this time.")


def _run_analyze(path: Path) -> int:
    analyzer = ModAnalyzer(mod_path=path)
    result = analyzer.analyze()
    _echo_result(result)
    return 0


def app(argv: Sequence[str] | None = None) -> int:
    """Simanalysis command line entry point."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if getattr(args, "version", False):
        print(__version__)
        return 0

    if getattr(args, "command", None) == "analyze":
        return _run_analyze(args.path)

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(app())
