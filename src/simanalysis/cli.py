"""Command-line interface for Simanalysis."""

import sys
from pathlib import Path
from typing import Any, Optional

import click

from simanalysis import __version__
from simanalysis.analyzers import ModAnalyzer
from simanalysis.models import Severity


@click.group()
@click.version_option(version=__version__, prog_name="simanalysis")
def cli() -> None:
    """
    🔬 Simanalysis - Sims 4 Mod Conflict Analyzer

    Derrick, the PhD in Simology, surgically analyzes your Sims 4 mods
    for conflicts, duplicates, and compatibility issues BEFORE you launch the game.

    Examples:

        # Analyze your Mods folder
        simanalysis analyze ~/Documents/Electronic\\ Arts/The\\ Sims\\ 4/Mods

        # Quick scan (no hashing)
        simanalysis analyze ~/Mods --quick

        # Export detailed report
        simanalysis analyze ~/Mods --output report.json --format json

        # Show summary only
        simanalysis scan ~/Mods
    """


@cli.command()
@click.argument("mods_directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output report file path",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["txt", "json"], case_sensitive=False),
    default="txt",
    help="Report format (default: txt)",
)
@click.option(
    "--no-tunings",
    is_flag=True,
    help="Skip XML tuning parsing (faster but less accurate)",
)
@click.option(
    "--no-scripts",
    is_flag=True,
    help="Skip Python script analysis (faster but less accurate)",
)
@click.option(
    "--quick",
    "-q",
    is_flag=True,
    help="Quick scan mode (no hashing, faster)",
)
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Scan subdirectories (default: recursive)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose output with detailed progress",
)
@click.option(
    "--tui",
    is_flag=True,
    help="Use rich terminal interface (beautiful output)",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="Interactive mode with keyboard navigation (requires textual)",
)
@click.option(
    "--show-mods",
    is_flag=True,
    help="Show detailed mod list (TUI mode only)",
)
def analyze(
    mods_directory: str,
    output: Optional[str],
    format: str,
    no_tunings: bool,
    no_scripts: bool,
    quick: bool,
    recursive: bool,
    verbose: bool,
    tui: bool,
    interactive: bool,
    show_mods: bool,
) -> None:
    """
    Analyze Sims 4 mods directory for conflicts and issues.

    Performs complete analysis including:
    - Tuning conflict detection
    - Resource duplicate detection
    - Script injection conflicts
    - Performance metrics
    - Smart recommendations

    MODS_DIRECTORY: Path to your Sims 4 Mods folder
    """
    mods_path = Path(mods_directory).expanduser().resolve()

    # Use Interactive TUI if requested
    if interactive:
        from simanalysis.interactive_tui import run_interactive_tui

        run_interactive_tui(
            mods_path,
            parse_tunings=not no_tunings,
            parse_scripts=not no_scripts,
            calculate_hashes=not quick,
            recursive=recursive,
        )
        return

    # Use Rich TUI if requested
    if tui:
        from simanalysis.tui import tui as simanalysis_tui

        result = simanalysis_tui.display_with_progress(
            mods_path,
            parse_tunings=not no_tunings,
            parse_scripts=not no_scripts,
            calculate_hashes=not quick,
            recursive=recursive,
            show_mods=show_mods,
        )

        # Export if requested
        if output:
            output_path = Path(output).expanduser().resolve()
            analyzer = ModAnalyzer(
                parse_tunings=not no_tunings,
                parse_scripts=not no_scripts,
                calculate_hashes=not quick,
            )
            analyzer.export_report(result, output_path, format=format)
            click.echo(f"\n📄 Full report saved to: {output_path}")

        # Exit with error code if critical conflicts found
        critical_count = len([c for c in result.conflicts if c.severity == Severity.CRITICAL])
        if critical_count > 0:
            sys.exit(1)

        return

    # Standard CLI output
    if verbose:
        click.echo(f"🔬 Starting analysis of: {mods_path}")
        click.echo(f"   Parse tunings: {not no_tunings}")
        click.echo(f"   Parse scripts: {not no_scripts}")
        click.echo(f"   Calculate hashes: {not quick}")
        click.echo(f"   Recursive: {recursive}\n")
    else:
        click.echo(f"🔬 Analyzing {mods_path}...")

    # Create analyzer
    analyzer = ModAnalyzer(
        parse_tunings=not no_tunings,
        parse_scripts=not no_scripts,
        calculate_hashes=not quick,
    )

    # Run analysis with progress indication
    with click.progressbar(
        length=100,
        label="Scanning and analyzing",
        show_eta=True,
    ) as bar:
        result = analyzer.analyze_directory(mods_path, recursive=recursive)
        bar.update(100)

    # Display results
    click.echo("\n" + "=" * 70)
    click.echo("📊 ANALYSIS RESULTS")
    click.echo("=" * 70 + "\n")

    # Summary statistics
    click.echo(f"✅ Total Mods Found: {len(result.mods)}")
    click.echo(f"⚠️  Total Conflicts: {len(result.conflicts)}")

    # Conflicts by severity
    critical_count = len([c for c in result.conflicts if c.severity == Severity.CRITICAL])
    high_count = len([c for c in result.conflicts if c.severity == Severity.HIGH])
    medium_count = len([c for c in result.conflicts if c.severity == Severity.MEDIUM])
    low_count = len([c for c in result.conflicts if c.severity == Severity.LOW])

    if critical_count > 0:
        click.echo(click.style(f"   🔴 Critical: {critical_count}", fg="red", bold=True))
    if high_count > 0:
        click.echo(click.style(f"   🟠 High: {high_count}", fg="yellow", bold=True))
    if medium_count > 0:
        click.echo(click.style(f"   🟡 Medium: {medium_count}", fg="yellow"))
    if low_count > 0:
        click.echo(click.style(f"   🟢 Low: {low_count}", fg="green"))

    # Performance metrics
    perf = result.performance
    click.echo("\n📈 Performance Metrics:")
    click.echo(f"   Total Size: {perf.total_size_mb:.2f} MB")
    click.echo(f"   Resources: {perf.total_resources:,}")
    click.echo(f"   Tunings: {perf.total_tunings:,}")
    click.echo(f"   Scripts: {perf.total_scripts:,}")
    click.echo(f"   Est. Load Time: {perf.estimated_load_time_seconds:.1f}s")
    click.echo(f"   Est. Memory: {perf.estimated_memory_mb:.1f} MB")
    click.echo(f"   Complexity Score: {perf.complexity_score:.1f}/100")

    # Recommendations
    if result.recommendations:
        click.echo("\n💡 RECOMMENDATIONS:")
        click.echo("-" * 70)
        for rec in result.recommendations:
            # Color-code recommendations
            if "CRITICAL" in rec:
                click.echo(click.style(rec, fg="red", bold=True))
            elif "HIGH" in rec:
                click.echo(click.style(rec, fg="yellow", bold=True))
            else:
                click.echo(rec)

    # Show top conflicts if verbose
    if verbose and result.conflicts:
        click.echo("\n🔍 TOP CONFLICTS:")
        click.echo("-" * 70)
        for i, conflict in enumerate(result.conflicts[:10], 1):
            severity_color = {
                Severity.CRITICAL: "red",
                Severity.HIGH: "yellow",
                Severity.MEDIUM: "yellow",
                Severity.LOW: "green",
            }[conflict.severity]

            click.echo(
                f"\n{i}. [{click.style(conflict.severity.value, fg=severity_color)}] {conflict.type.value}"
            )
            click.echo(f"   {conflict.description}")
            click.echo(f"   Affected: {', '.join(conflict.affected_mods[:3])}")
            if len(conflict.affected_mods) > 3:
                click.echo(f"   ... and {len(conflict.affected_mods) - 3} more")

        if len(result.conflicts) > 10:
            click.echo(f"\n... and {len(result.conflicts) - 10} more conflicts")
            click.echo("(Use --output to export full report)")

    # Export report if requested
    if output:
        output_path = Path(output).expanduser().resolve()
        analyzer.export_report(result, output_path, format=format)
        click.echo(f"\n📄 Full report saved to: {output_path}")

    # Analysis duration
    click.echo(f"\n⏱️  Analysis completed in {result.metadata.analysis_duration_seconds:.2f}s")

    # Exit with error code if critical conflicts found
    if critical_count > 0:
        click.echo(click.style("\n⚠️  WARNING: Critical conflicts detected!", fg="red", bold=True))
        sys.exit(1)


@cli.command()
@click.argument("mods_directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Scan subdirectories (default: recursive)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed mod information",
)
@click.option(
    "--tui",
    is_flag=True,
    help="Use rich terminal interface (beautiful output)",
)
def scan(mods_directory: str, recursive: bool, verbose: bool, tui: bool) -> None:
    """
    Quick scan of mods directory (no conflict detection).

    Useful for getting a quick overview of your mods without
    performing full analysis.

    MODS_DIRECTORY: Path to your Sims 4 Mods folder
    """
    mods_path = Path(mods_directory).expanduser().resolve()

    # Use Rich TUI if requested
    if tui:
        from simanalysis.tui import tui as simanalysis_tui

        simanalysis_tui.display_scan_result(mods_path, recursive=recursive, verbose=verbose)
        return

    # Standard CLI output
    click.echo(f"📂 Scanning {mods_path}...")

    # Create analyzer (quick mode)
    from simanalysis.scanners import ModScanner

    scanner = ModScanner(
        parse_tunings=False,
        parse_scripts=False,
        calculate_hashes=False,
    )

    # Scan directory
    mods = scanner.scan_directory(mods_path, recursive=recursive)

    # Display results
    click.echo(f"\n✅ Found {len(mods)} mod files")

    # Count by type
    from simanalysis.models import ModType

    packages = len([m for m in mods if m.type == ModType.PACKAGE])
    scripts = len([m for m in mods if m.type == ModType.SCRIPT])

    click.echo(f"   📦 Package files (.package): {packages}")
    click.echo(f"   🐍 Script files (.ts4script): {scripts}")

    # Total size
    total_size = sum(m.size for m in mods)
    click.echo(f"   💾 Total size: {total_size / 1024 / 1024:.2f} MB")

    # Show individual mods if verbose
    if verbose:
        click.echo("\n📋 MOD LIST:")
        click.echo("-" * 70)
        for mod in sorted(mods, key=lambda m: m.size, reverse=True):
            size_mb = mod.size / 1024 / 1024
            icon = "📦" if mod.type == ModType.PACKAGE else "🐍"
            click.echo(f"{icon} {mod.name:50} {size_mb:8.2f} MB")

    # Scan summary
    summary = scanner.get_scan_summary()
    if summary.get("errors_encountered", 0) > 0:
        click.echo(f"\n⚠️  Encountered {summary['errors_encountered']} errors during scan")

    click.echo("\n⏱️  Scan completed")


@cli.command()
@click.argument("report_file", type=click.Path(exists=True))
def view(report_file: str) -> None:
    """
    View a previously exported report.

    REPORT_FILE: Path to JSON report file
    """
    import json

    report_path = Path(report_file).expanduser().resolve()

    if report_path.suffix != ".json":
        click.echo(click.style("❌ Error: Only JSON reports can be viewed", fg="red"))
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    # Display summary
    summary = report["summary"]
    click.echo("\n" + "=" * 70)
    click.echo("📊 REPORT SUMMARY")
    click.echo("=" * 70 + "\n")

    click.echo(f"Total Mods: {summary['total_mods']}")
    click.echo(f"Total Conflicts: {summary['total_conflicts']}")
    click.echo(f"   🔴 Critical: {summary['critical_conflicts']}")
    click.echo(f"   🟠 High: {summary['high_conflicts']}")
    click.echo(f"   🟡 Medium: {summary['medium_conflicts']}")
    click.echo(f"   🟢 Low: {summary['low_conflicts']}")

    # Recommendations
    if report["recommendations"]:
        click.echo("\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            click.echo(f"  {rec}")

    # Top conflicts
    if report["conflicts"]:
        click.echo("\n🔍 TOP CONFLICTS:")
        for i, conflict in enumerate(report["conflicts"][:10], 1):
            click.echo(f"\n{i}. [{conflict['severity']}] {conflict['type']}")
            click.echo(f"   {conflict['description']}")


@cli.command()
@click.option(
    "--version",
    "-v",
    is_flag=True,
    help="Show version information",
)
def info(version: bool) -> None:
    """
    Show information about Simanalysis.
    """
    if version:
        click.echo(f"Simanalysis version {__version__}")
        return

    click.echo("\n" + "=" * 70)
    click.echo("🔬 SIMANALYSIS - Derrick, the PhD in Simology")
    click.echo("=" * 70 + "\n")

    click.echo(f"Version: {__version__}")
    click.echo("License: MIT")
    click.echo("Repository: https://github.com/justaride/Simanalysis")
    click.echo("\nDescription:")
    click.echo("  Surgical analysis of Sims 4 mods and CC.")
    click.echo("  Proactive conflict detection BEFORE game launch.")
    click.echo("\nFeatures:")
    click.echo("  ✓ Deep conflict detection (tuning, resource, script)")
    click.echo("  ✓ Performance metrics and load time estimation")
    click.echo("  ✓ Smart recommendations")
    click.echo("  ✓ Report export (TXT, JSON)")
    click.echo("\nUsage:")
    click.echo("  simanalysis analyze /path/to/Mods")
    click.echo("  simanalysis scan /path/to/Mods")
    click.echo("\nFor help:")
    click.echo("  simanalysis --help")
    click.echo("  simanalysis analyze --help")
    click.echo("")


@cli.command()
@click.option(
    "--port",
    "-p",
    default=8000,
    help="Port to run the server on",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the server to",
)
def web(port: int, host: str) -> None:
    """
    Launch the Web GUI.

    Starts the FastAPI backend and serves the React frontend.
    """
    from simanalysis.web.run import run_web_gui

    run_web_gui(host=host, port=port)


def _format_ui_key(key: int) -> str:
    return f"0x{key:016X} ({key})"


def _ui_findings_for_status(result: Any, status: str) -> list[Any]:
    return [finding for finding in result.findings if finding.status == status]


def _format_ui_txt(log_count: int, result: Any, limit: int = 20) -> str:
    summary = result.summary
    findings = result.findings
    unique_findings = summary.get("unique_findings", len(findings))
    occurrences = summary.get(
        "occurrences",
        sum(finding.report.occurrences for finding in findings),
    )

    lines = [
        (
            f"UI Crash Autopsy - {log_count} log file(s), "
            f"{unique_findings} unique UI finding(s), {occurrences} occurrence(s)"
        ),
        (
            "status counts: "
            f"active: {summary.get('active_findings', 0)}  |  "
            f"disabled: {summary.get('disabled_findings', 0)}  |  "
            f"not-found: {summary.get('not_found_findings', 0)}  |  "
            f"no-key: {summary.get('no_key_findings', 0)}"
        ),
    ]
    if result.parse_errors:
        lines.append(f"parse errors: {len(result.parse_errors)}")
    if result.index_errors:
        lines.append(f"index errors: {len(result.index_errors)}")
    lines.append("")

    if not findings:
        lines.append("(no UI exception reports found)")
        return "\n".join(lines).rstrip()

    groups = [
        ("active", "[ACTIVE]"),
        ("disabled", "[DISABLED]"),
        ("not_found", "[NOT FOUND]"),
        ("no_key", "[NO KEY]"),
    ]
    shown_any = False
    safe_limit = max(limit, 0)
    for status, header in groups:
        entries = _ui_findings_for_status(result, status)
        if not entries:
            continue

        shown_any = True
        lines.append(f"{header}:")
        for finding in entries[:safe_limit]:
            if finding.keys:
                if len(finding.keys) == 1:
                    lines.append(f"  key: {_format_ui_key(finding.keys[0])}")
                else:
                    keys = ", ".join(_format_ui_key(key) for key in finding.keys)
                    lines.append(f"  keys: {keys}")
            lines.append(f"  message: {finding.report.message}")
            if finding.report.category_id:
                lines.append(f"  category: {finding.report.category_id}")
            lines.append(f"  occurrences: {finding.report.occurrences}")
            if finding.hits:
                packages = ", ".join(dict.fromkeys(hit.package_name for hit in finding.hits))
                lines.append(f"  packages: {packages}")
            lines.append("")

        hidden = len(entries) - safe_limit
        if hidden > 0:
            lines.append(f"  ... {hidden} more hidden by --limit")
            lines.append("")

    if not shown_any:
        lines.append("(no UI exception reports found)")

    return "\n".join(lines).rstrip()


@cli.command("ui-crash")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--mods", type=click.Path(), default=None, help="Mods dir (default: <sims4_dir>/Mods)"
)
@click.option("--recursive", is_flag=True, help="Also scan subfolders for UI exception logs")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
@click.option("--limit", type=int, default=20, help="Top-N findings to show per status group (txt)")
def ui_crash(
    sims4_dir: str,
    mods: Optional[str],
    recursive: bool,
    fmt: str,
    output: Optional[str],
    limit: int,
) -> None:
    """Autopsy lastUIException UI logs: map missing UI resources to packages."""
    import json

    from simanalysis import serialization
    from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
    from simanalysis.parsers.ui_exception_log import parse_ui_exception_file

    base = Path(sims4_dir).expanduser()
    mods_dir = Path(mods).expanduser() if mods else base / "Mods"
    pattern = "**/lastUIException*.txt" if recursive else "lastUIException*.txt"
    log_files = sorted(base.glob(pattern))

    reports = []
    parse_errors = []
    for log_file in log_files:
        try:
            reports.extend(parse_ui_exception_file(log_file))
        except Exception as exc:
            parse_errors.append(f"{log_file.name}: {exc}")

    analyzer = UICrashAnalyzer()
    target_keys = {key for report in reports for key in report.keys}
    if target_keys:
        extra_roots = discover_disabled_roots(base)
        index = analyzer.build_resource_index(
            mods_dir,
            extra_roots=extra_roots,
            target_keys=target_keys,
        )
    else:
        index = {}

    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors

    if fmt == "json":
        text = json.dumps(serialization.ui_result_to_dict(result), indent=2)
    else:
        text = _format_ui_txt(len(log_files), result, limit=limit)

    if output:
        output_path = Path(output).expanduser()
        output_path.write_text(text, encoding="utf-8")
        click.echo(f"Wrote report to {output}")
    else:
        click.echo(text)


@cli.command()
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--mods", type=click.Path(), default=None, help="Mods dir (default: <sims4_dir>/Mods)"
)
@click.option("--recursive", is_flag=True, help="Also scan subfolders for crash logs")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
@click.option("--limit", type=int, default=20, help="Top-N mods to show per status group (txt)")
def crash(
    sims4_dir: str,
    mods: Optional[str],
    recursive: bool,
    fmt: str,
    output: Optional[str],
    limit: int,
) -> None:
    """Autopsy lastException crash logs: rank the mods most likely behind your crashes."""
    import json

    from simanalysis import serialization
    from simanalysis.analyzers.crash_analyzer import CrashAnalyzer, _is_disabled_name
    from simanalysis.parsers.exception_log import parse_exception_file

    base = Path(sims4_dir)
    mods_dir = Path(mods) if mods else base / "Mods"
    pattern = "**/lastException*.txt" if recursive else "lastException*.txt"
    log_files = sorted(base.glob(pattern))

    reports = []
    parse_errors = []
    seen = set()
    for lf in log_files:
        try:
            for rep in parse_exception_file(lf):
                if rep.signature in seen:
                    continue
                seen.add(rep.signature)
                reports.append(rep)
        except Exception as exc:
            parse_errors.append(f"{lf.name}: {exc}")

    analyzer = CrashAnalyzer()
    # Auto-discover deliberately set-aside folders (at any depth, e.g. Archive/.../_DISABLED_*)
    # so disabled/quarantined culprits are named instead of mislabeled active.
    extra_roots = [d for d in base.glob("**/_*") if d.is_dir() and _is_disabled_name(d.name)]
    index = analyzer.build_module_index(mods_dir, extra_roots=extra_roots)
    result = analyzer.analyze(reports, index)
    result.parse_errors = parse_errors

    if fmt == "json":
        text = json.dumps(serialization.crash_result_to_dict(result), indent=2)
    else:
        s = result.summary
        lines = [
            f"🔬 Crash Autopsy — {len(log_files)} log file(s), {s['reports']} crash(es)",
            f"   active: {s['active_culprits']}  |  already-disabled: {s['disabled_culprits']}"
            f"  |  not-installed: {s['not_installed_culprits']}  |  base-game-only: {s['base_game_only']}",
            "",
        ]
        groups = [
            ("active", "[ACTIVE] mods still implicated — fix these"),
            ("disabled", "[DISABLED] already set aside — likely handled"),
            ("not_installed", "[NOT INSTALLED] referenced but not on disk — best guess"),
        ]
        any_shown = False
        for status_key, header in groups:
            entries = [e for e in result.ranked_mods if e.get("status") == status_key]
            if not entries:
                continue
            any_shown = True
            lines.append(f"{header}:")
            for entry in entries[:limit]:
                line = (
                    f"  - {entry['mod']}  — top suspect in {entry['top_suspect_count']} crash(es)"
                )
                if status_key != "not_installed":  # not_installed has no on-disk 'seen in' count
                    line += f", seen in {entry['crash_count']}"
                lines.append(line)
            lines.append("")
        if not any_shown:
            lines.append("  (no mod-attributable crashes found)")
        text = "\n".join(lines).rstrip()

    if output:
        Path(output).write_text(text, encoding="utf-8")
        click.echo(f"Wrote report to {output}")
    else:
        click.echo(text)


def main() -> None:
    """Entry point for CLI."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n\n⚠️  Analysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(click.style(f"\n❌ Error: {e}", fg="red", bold=True))
        sys.exit(1)


if __name__ == "__main__":
    main()
