"""Command-line interface for Simanalysis."""

import sys
from pathlib import Path
from typing import Optional

import click

from simanalysis import __version__
from simanalysis.analyzers import ModAnalyzer
from simanalysis.models import Severity


@click.group()
@click.version_option(version=__version__, prog_name="simanalysis")
def cli():
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
    pass


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
    show_mods: bool,
):
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
    click.echo(f"\n📈 Performance Metrics:")
    click.echo(f"   Total Size: {perf.total_size_mb:.2f} MB")
    click.echo(f"   Resources: {perf.total_resources:,}")
    click.echo(f"   Tunings: {perf.total_tunings:,}")
    click.echo(f"   Scripts: {perf.total_scripts:,}")
    click.echo(f"   Est. Load Time: {perf.estimated_load_time_seconds:.1f}s")
    click.echo(f"   Est. Memory: {perf.estimated_memory_mb:.1f} MB")
    click.echo(f"   Complexity Score: {perf.complexity_score:.1f}/100")

    # Recommendations
    if result.recommendations:
        click.echo(f"\n💡 RECOMMENDATIONS:")
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
        click.echo(f"\n🔍 TOP CONFLICTS:")
        click.echo("-" * 70)
        for i, conflict in enumerate(result.conflicts[:10], 1):
            severity_color = {
                Severity.CRITICAL: "red",
                Severity.HIGH: "yellow",
                Severity.MEDIUM: "yellow",
                Severity.LOW: "green",
            }[conflict.severity]

            click.echo(f"\n{i}. [{click.style(conflict.severity.value, fg=severity_color)}] {conflict.type.value}")
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
def scan(mods_directory: str, recursive: bool, verbose: bool, tui: bool):
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
        click.echo(f"\n📋 MOD LIST:")
        click.echo("-" * 70)
        for mod in sorted(mods, key=lambda m: m.size, reverse=True):
            size_mb = mod.size / 1024 / 1024
            icon = "📦" if mod.type == ModType.PACKAGE else "🐍"
            click.echo(f"{icon} {mod.name:50} {size_mb:8.2f} MB")

    # Scan summary
    summary = scanner.get_scan_summary()
    if summary.get("errors_encountered", 0) > 0:
        click.echo(f"\n⚠️  Encountered {summary['errors_encountered']} errors during scan")

    click.echo(f"\n⏱️  Scan completed")


@cli.command()
@click.argument("report_file", type=click.Path(exists=True))
def view(report_file: str):
    """
    View a previously exported report.

    REPORT_FILE: Path to JSON report file
    """
    import json

    report_path = Path(report_file).expanduser().resolve()

    if not report_path.suffix == ".json":
        click.echo(click.style("❌ Error: Only JSON reports can be viewed", fg="red"))
        sys.exit(1)

    with open(report_path) as f:
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
        click.echo(f"\n💡 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            click.echo(f"  {rec}")

    # Top conflicts
    if report["conflicts"]:
        click.echo(f"\n🔍 TOP CONFLICTS:")
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
def info(version: bool):
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


def main():
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
