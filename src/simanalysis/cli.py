"""Command-line interface for Simanalysis."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from simanalysis import __version__
from simanalysis.analyzers import ModAnalyzer
from simanalysis.models import Severity
from simanalysis.utils.logging import setup_logging, get_default_log_file


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
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set logging level (default: INFO)",
)
@click.option(
    "--log-file",
    type=click.Path(),
    help="Write logs to file (default: ~/.simanalysis/logs/simanalysis.log)",
)
@click.option(
    "--quiet",
    is_flag=True,
    help="Suppress console logging (still writes to log file if --log-file specified)",
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
    log_level: str,
    log_file: Optional[str],
    quiet: bool,
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
    # Setup logging first
    log_file_path = Path(log_file).expanduser().resolve() if log_file else get_default_log_file()

    # Override log level if verbose flag is set
    if verbose and log_level == "INFO":
        log_level = "DEBUG"

    setup_logging(
        level=log_level,
        log_file=log_file_path if (log_file or not quiet) else None,
        console=not quiet,
        colored=True,
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Simanalysis v{__version__}")
    logger.debug(f"Analyzing directory: {mods_directory}")

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
@click.argument("mods_directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Export dependency graph to DOT file",
)
@click.option(
    "--show-load-order",
    is_flag=True,
    help="Display recommended load order",
)
@click.option(
    "--show-missing",
    is_flag=True,
    help="Show missing dependencies",
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
    help="Verbose output",
)
def dependencies(
    mods_directory: str,
    output: Optional[str],
    show_load_order: bool,
    show_missing: bool,
    recursive: bool,
    verbose: bool,
):
    """
    Analyze mod dependencies and load order.

    Shows dependency relationships, load order issues, and missing dependencies.

    MODS_DIRECTORY: Path to your Sims 4 Mods folder
    """
    from simanalysis.analyzers.mod_analyzer import ModAnalyzer
    from simanalysis.analyzers.dependency_detector import DependencyDetector
    from simanalysis.analyzers.dependency_graph import DependencyGraph

    mods_path = Path(mods_directory).expanduser().resolve()

    click.echo(f"🔍 Analyzing dependencies in: {mods_path}\n")

    # Step 1: Scan mods
    if verbose:
        click.echo("Step 1/3: Scanning mods...")

    analyzer = ModAnalyzer(
        parse_tunings=True,
        parse_scripts=True,
        calculate_hashes=False,  # Not needed for dependencies
    )

    result = analyzer.analyze_directory(mods_path, recursive=recursive)

    if len(result.mods) == 0:
        click.echo("❌ No mods found in directory")
        return

    if verbose:
        click.echo(f"   Found {len(result.mods)} mods\n")

    # Step 2: Detect dependencies
    if verbose:
        click.echo("Step 2/3: Detecting dependencies...")

    detector = DependencyDetector()
    all_deps = detector.detect_all_dependencies(result.mods)

    if verbose:
        click.echo(f"   Found {len(all_deps)} mods with dependencies\n")

    # Step 3: Build dependency graph
    if verbose:
        click.echo("Step 3/3: Building dependency graph...")

    graph = DependencyGraph()

    # Add all mods to graph
    for mod in result.mods:
        deps = all_deps.get(mod.name, [])
        graph.add_mod(mod, dependencies=deps)

    if verbose:
        click.echo(f"   Graph built with {graph.graph.number_of_nodes()} nodes\n")

    # Display results
    click.echo("=" * 70)
    click.echo("📊 DEPENDENCY ANALYSIS RESULTS")
    click.echo("=" * 70 + "\n")

    # Statistics
    stats = graph.get_statistics()
    click.echo(f"✅ Total Mods: {stats['total_mods']}")
    click.echo(f"🔗 Dependency Relationships: {stats['total_dependencies']}")
    click.echo(f"🔄 Circular Dependencies: {'Yes' if stats['has_cycles'] else 'No'}")

    if stats['has_cycles']:
        click.echo(click.style(f"   ⚠️  {stats['cycle_count']} cycle(s) detected!", fg="red", bold=True))
        cycles = graph.detect_cycles()
        for i, cycle in enumerate(cycles[:3], 1):
            click.echo(f"      Cycle {i}: {' → '.join(cycle)}")
        if len(cycles) > 3:
            click.echo(f"      ... and {len(cycles) - 3} more cycles")

    # Most depended on mod
    if 'most_depended_on' in stats and stats['most_depended_on']:
        most_dep = stats['most_depended_on']
        click.echo(f"\n🌟 Most Depended On: {most_dep['mod']} ({most_dep['dependent_count']} mods depend on it)")

    # Show mods with dependencies
    if all_deps and verbose:
        click.echo(f"\n📦 MODS WITH DEPENDENCIES:")
        click.echo("-" * 70)
        for mod_name, deps in sorted(all_deps.items())[:15]:
            click.echo(f"\n{mod_name}")
            for dep in deps:
                click.echo(f"   → {dep}")
        if len(all_deps) > 15:
            click.echo(f"\n... and {len(all_deps) - 15} more mods with dependencies")

    # Load order analysis
    if show_load_order or verbose:
        click.echo(f"\n📋 LOAD ORDER ANALYSIS:")
        click.echo("-" * 70)

        optimal_order = graph.topological_sort()

        if optimal_order is None:
            click.echo(click.style("⚠️  Cannot determine optimal load order due to circular dependencies!", fg="red"))
        else:
            click.echo(f"✅ Optimal load order determined ({len(optimal_order)} mods)")

            if show_load_order:
                click.echo("\nRecommended load order (first to last):")
                for i, mod_name in enumerate(optimal_order[:20], 1):
                    click.echo(f"  {i:2d}. {mod_name}")
                if len(optimal_order) > 20:
                    click.echo(f"  ... and {len(optimal_order) - 20} more mods")

            # Check current load order issues
            current_order = [mod.name for mod in result.mods]
            issues = graph.get_load_order_issues(current_order)

            if issues:
                click.echo(f"\n⚠️  {len(issues)} load order issues detected:")
                for issue in issues[:10]:
                    severity_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
                    color = severity_color.get(issue["severity"], "white")
                    click.echo(click.style(
                        f"\n  [{issue['severity']}] {issue['mod']}",
                        fg=color,
                        bold=(issue['severity'] == 'HIGH')
                    ))
                    click.echo(f"    {issue['reason']}")
                    click.echo(f"    Current position: {issue['current_position']}, Should be: {issue['should_be_at']}")

                if len(issues) > 10:
                    click.echo(f"\n  ... and {len(issues) - 10} more issues")
            else:
                click.echo("\n✅ No load order issues detected")

    # Missing dependencies
    if show_missing or verbose:
        click.echo(f"\n🔍 MISSING DEPENDENCIES:")
        click.echo("-" * 70)

        installed = {mod.name for mod in result.mods}
        missing = graph.find_missing_dependencies(installed)

        if missing:
            click.echo(click.style(f"⚠️  {len(missing)} missing dependencies detected:", fg="yellow"))
            for mod_name, dep_name in missing[:15]:
                click.echo(f"   {mod_name} → {click.style(dep_name, fg='red', bold=True)} (missing)")
            if len(missing) > 15:
                click.echo(f"   ... and {len(missing) - 15} more missing dependencies")
        else:
            click.echo("✅ No missing dependencies detected")

    # Export DOT file
    if output:
        output_path = Path(output).expanduser().resolve()
        graph.export_dot(output_path)
        click.echo(f"\n📄 Dependency graph exported to: {output_path}")
        click.echo("   (Use Graphviz to visualize: dot -Tpng graph.dot -o graph.png)")

    # ASCII visualization
    if verbose:
        click.echo("\n" + graph.to_ascii())

    click.echo("")


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
    click.echo("  ✓ Dependency analysis and load order optimization")
    click.echo("  ✓ Performance metrics and load time estimation")
    click.echo("  ✓ Smart recommendations")
    click.echo("  ✓ Report export (TXT, JSON)")
    click.echo("\nUsage:")
    click.echo("  simanalysis analyze /path/to/Mods")
    click.echo("  simanalysis scan /path/to/Mods")
    click.echo("  simanalysis dependencies /path/to/Mods --verbose")
    click.echo("\nFor help:")
    click.echo("  simanalysis --help")
    click.echo("  simanalysis analyze --help")
    click.echo("  simanalysis dependencies --help")
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
