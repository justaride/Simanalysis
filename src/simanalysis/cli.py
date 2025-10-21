"""Command line interface for Simanalysis."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from simanalysis import __version__
from simanalysis.analysis.conflicts import find_duplicate_keys, format_conflicts
from simanalysis.analysis.explain import explain_conflict
from simanalysis.analysis.inventory import scan_mods_dir
from simanalysis.analysis.tuning import extract_tuning_from_xml
from simanalysis.analysis.tuning_diff import diff_tuning
from simanalysis.model import PackageIndex, ResourceKey
from simanalysis.model.graph import DepGraph
from simanalysis.reporting.report import render_report
from simanalysis.utils import init_logger

APP_HELP = """Utilities for inspecting The Sims 4 mods.

Examples:
  simanalysis scan ~/Documents/EA/Mods --out index.json
  simanalysis conflicts --index index.json --report conflicts.txt
  simanalysis report --index index.json --conflicts conflicts.txt --deps deps.json --out report.html
"""

app = typer.Typer(help=APP_HELP, add_completion=False)


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _load_indexes(path: Path) -> list[PackageIndex]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid index JSON: {path}") from exc
    return [PackageIndex.model_validate(item) for item in data]


def _validate_log_level(value: str) -> str:
    level = value.lower()
    if level not in {"info", "debug"}:
        raise typer.BadParameter("log level must be 'info' or 'debug'")
    return level


def _friendly_exit(exc: Exception) -> None:
    typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1) from exc


MODS_DIR_ARGUMENT = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    resolve_path=True,
    help="Path to the Sims 4 Mods directory.",
)

DBPF_BACKEND_OPTION = typer.Option(
    "dummy",
    "--dbpf-backend",
    help="DBPF reader backend to use.",
)

CLI_PATH_OPTION = typer.Option(
    None,
    "--cli-path",
    help="Path to external DBPF CLI when using the external backend.",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
)

SCAN_OUT_OPTION = typer.Option(
    Path("index.json"),
    "--out",
    help="Destination JSON index file.",
)

INDEX_OPTION = typer.Option(
    ...,
    "--index",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to an inventory index JSON file.",
)

CONFLICT_REPORT_OPTION = typer.Option(
    Path("conflicts.txt"),
    "--report",
    help="Path to write the conflict summary.",
)

GRAPH_DEPS_OPTION = typer.Option(
    Path("deps.json"),
    "--deps",
    help="Destination for the dependency graph JSON.",
)

CONFLICTS_FILE_OPTION = typer.Option(
    ...,
    "--conflicts",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a conflicts text report.",
)

DEPS_INPUT_OPTION = typer.Option(
    ...,
    "--deps",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to a dependency graph JSON file.",
)

DIFF_OUT_OPTION = typer.Option(
    Path("diff.json"),
    "--out",
    help="Destination for the diff JSON.",
)

REPORT_OUT_OPTION = typer.Option(
    Path("report.html"),
    "--out",
    help="Destination HTML report.",
)

KEY_OPTION = typer.Option(
    ...,
    "--key",
    help="Resource key in TTTTTTTT:GGGGGGGG:IIIIIIII format.",
)

LOG_LEVEL_OPTION = typer.Option(
    "info",
    "--log-level",
    help="Logging verbosity (info or debug).",
    callback=_validate_log_level,
)

TUNING_A_OPTION = typer.Option(
    ...,
    "--a",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to the first tuning XML file.",
)

TUNING_B_OPTION = typer.Option(
    ...,
    "--b",
    exists=True,
    file_okay=True,
    dir_okay=False,
    resolve_path=True,
    help="Path to the second tuning XML file.",
)


@app.callback()
def _root_callback(
    version: bool = typer.Option(False, "--version", help="Show the simanalysis version and exit."),
) -> None:
    """Simanalysis command suite."""

    if version:
        typer.echo(f"simanalysis {__version__}")
        raise typer.Exit()


@app.command("scan")
def scan(
    mods_dir: Path = MODS_DIR_ARGUMENT,
    dbpf_backend: str = DBPF_BACKEND_OPTION,
    cli_path: Path | None = CLI_PATH_OPTION,
    out: Path = SCAN_OUT_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Scan a Mods directory and write a JSON inventory index."""

    init_logger(log_level)
    try:
        indexes = scan_mods_dir(mods_dir, dbpf_backend=dbpf_backend, cli_path=cli_path)
        data = [index.model_dump(mode="json") for index in indexes]
        _ensure_parent(out)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as exc:
        _friendly_exit(exc)
    typer.echo(f"Wrote {len(indexes)} package indexes to {out}")


@app.command("conflicts")
def conflicts(
    index: Path = INDEX_OPTION,
    report: Path = CONFLICT_REPORT_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Analyze an inventory index and report duplicate resources."""

    init_logger(log_level)
    try:
        indexes = _load_indexes(index)
        duplicates = find_duplicate_keys(indexes)
        report_text = format_conflicts(duplicates)
        _ensure_parent(report)
        report.write_text(report_text, encoding="utf-8")
    except (ValueError, OSError) as exc:
        _friendly_exit(exc)
    typer.echo(f"Wrote conflict report with {len(duplicates)} duplicates to {report}")


@app.command("graph")
def graph(
    index: Path = INDEX_OPTION,
    deps: Path = GRAPH_DEPS_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Build a tuning dependency graph from an inventory index."""

    init_logger(log_level)
    try:
        indexes = _load_indexes(index)
    except ValueError as exc:
        _friendly_exit(exc)
    graph_model = DepGraph()
    processed_paths: set[Path] = set()
    for package in indexes:
        package_path = package.package_path
        if package_path in processed_paths or not package_path.exists():
            continue
        processed_paths.add(package_path)
        for entry in package.entries:
            if entry.resource_type != "xml":
                continue
            node = extract_tuning_from_xml(package_path)
            if node is None:
                continue
            graph_model.add_node(node)
            for reference in node.references:
                graph_model.add_edge(node.tuning_id, reference)
            break

    graph_json = graph_model.to_json()
    try:
        _ensure_parent(deps)
        deps.write_text(json.dumps(graph_json, indent=2), encoding="utf-8")
    except OSError as exc:
        _friendly_exit(exc)
    typer.echo(f"Wrote dependency graph with {len(graph_json['nodes'])} nodes to {deps}")


@app.command("tuning-diff")
def tuning_diff(
    a: Path = TUNING_A_OPTION,
    b: Path = TUNING_B_OPTION,
    out: Path = DIFF_OUT_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Compare two tuning XML files and emit a JSON diff."""

    init_logger(log_level)
    try:
        a_xml = a.read_text(encoding="utf-8")
        b_xml = b.read_text(encoding="utf-8")
        diff = diff_tuning(a_xml, b_xml)
        _ensure_parent(out)
        out.write_text(json.dumps(diff, indent=2), encoding="utf-8")
    except OSError as exc:
        _friendly_exit(exc)
    typer.echo(f"Wrote tuning diff to {out}")


@app.command("report")
def report(
    index: Path = INDEX_OPTION,
    conflicts: Path = CONFLICTS_FILE_OPTION,
    deps: Path = DEPS_INPUT_OPTION,
    out: Path = REPORT_OUT_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Render an HTML report combining inventory, conflicts, and dependency data."""

    init_logger(log_level)
    try:
        indexes = _load_indexes(index)
        conflict_text = conflicts.read_text(encoding="utf-8")
        conflict_map = find_duplicate_keys(indexes)
        deps_json = json.loads(deps.read_text(encoding="utf-8"))
        html = render_report(indexes, conflict_map, deps_json, conflict_text=conflict_text)
        _ensure_parent(out)
        out.write_text(html, encoding="utf-8")
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        _friendly_exit(exc)
    typer.echo(f"Wrote HTML report to {out}")


@app.command("explain")
def explain(
    index: Path = INDEX_OPTION,
    key: str = KEY_OPTION,
    log_level: str = LOG_LEVEL_OPTION,
) -> None:
    """Explain why a particular resource key conflicts across packages."""

    init_logger(log_level)
    try:
        resource_key = ResourceKey.from_hex(key)
        indexes = _load_indexes(index)
    except ValueError as exc:
        _friendly_exit(exc)

    explanation = explain_conflict(indexes, resource_key)
    typer.echo(explanation)


def main() -> None:  # pragma: no cover - console script entrypoint
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
