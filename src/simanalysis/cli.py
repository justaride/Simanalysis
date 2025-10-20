"""Typer-based command line entrypoint for Simanalysis."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import typer

from .analyzer import ModAnalyzer
from .main import (
    collect_exception_summaries,
    render_console_report,
    render_html_report,
)

PATH_ARGUMENT = typer.Argument(
    Path("."),
    exists=True,
    file_okay=False,
    dir_okay=True,
    resolve_path=True,
    help="Path to the Sims 4 Mods directory (defaults to current working directory).",
)

EXCEPTIONS_OPTION = typer.Option(
    False,
    "--exceptions/--no-exceptions",
    help="Include summaries from lastException.txt if available.",
)

EXCEPTIONS_PATH_OPTION = typer.Option(
    None,
    "--exceptions-path",
    help="Explicit path to a lastException log to include in the report.",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
)

OUTPUT_OPTION = typer.Option(
    None,
    "--output",
    help="Write an HTML report to the specified file.",
    exists=False,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
)

app = typer.Typer(
    help="Scan Sims 4 mods for conflicts and generate reports.",
    no_args_is_help=False,
)


@app.callback()
def run(
    path: Path = PATH_ARGUMENT,
    exceptions: bool = EXCEPTIONS_OPTION,
    exceptions_path: Path | None = EXCEPTIONS_PATH_OPTION,
    output: Path | None = OUTPUT_OPTION,
) -> None:
    """Run a Sims 4 mods scan and print a console summary."""
    analyzer = ModAnalyzer()

    try:
        result = analyzer.analyze_directory(str(path))
    except FileNotFoundError as exc:  # pragma: no cover - CLI level validation
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    scan_time = dt.datetime.now()

    exception_entries: list[dict[str, str]] = []
    if exceptions:
        explicit_path = None if exceptions_path is None else str(exceptions_path)
        exception_entries = collect_exception_summaries(path, explicit_path)

    render_console_report(
        result,
        path,
        scan_time,
        exception_entries,
        exceptions_requested=exceptions,
    )

    if output is not None:
        output.write_text(
            render_html_report(result, path, scan_time, exception_entries),
            encoding="utf-8",
        )
        typer.echo(f"\n📄 Report generated: {output}")


def main() -> None:  # pragma: no cover - passthrough for console_scripts
    """Entrypoint for console_scripts compatibility."""
    app()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
