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
    bar: Any
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


def _ledger_db_path(db: Optional[str]) -> Path:
    from simanalysis.inventory import default_inventory_db_path

    return Path(db).expanduser().resolve() if db else default_inventory_db_path()


def _echo_json(payload: dict[str, Any]) -> None:
    import json

    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def _optional_resolved_path(path: Optional[str]) -> Optional[Path]:
    return Path(path).expanduser().resolve() if path else None


@cli.group("patch-day")
def patch_day() -> None:
    """Read-only Patch Day Shield commands."""


@patch_day.command("status")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--state", type=click.Path(dir_okay=False), default=None, help="Patch Day state JSON path"
)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def patch_day_status(sims4_dir: str, state: Optional[str], fmt: str) -> None:
    """Compare GameVersion.txt with the recorded Patch Day baseline."""
    from simanalysis.patch_day import build_patch_day_status, format_patch_day_text

    root = Path(sims4_dir).expanduser().resolve()
    status = build_patch_day_status(root, state_path=_optional_resolved_path(state))
    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_patch_day_text(status))


@patch_day.command("record")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--state", type=click.Path(dir_okay=False), default=None, help="Patch Day state JSON path"
)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def patch_day_record(sims4_dir: str, state: Optional[str], fmt: str) -> None:
    """Record the current GameVersion.txt value as the Patch Day baseline."""
    from simanalysis.patch_day import format_patch_day_text, record_patch_baseline

    root = Path(sims4_dir).expanduser().resolve()
    try:
        status = record_patch_baseline(root, state_path=_optional_resolved_path(state))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_patch_day_text(status))


@cli.group("cache")
def cache() -> None:
    """Read-only Cache Doctor commands."""


@cache.command("status")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def cache_status(sims4_dir: str, fmt: str) -> None:
    """Inspect known Sims 4 cache targets without changing files."""
    from simanalysis.cache_doctor import build_cache_status, format_cache_status_text

    status = build_cache_status(sims4_dir)
    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_cache_status_text(status))


@cli.group("save-protector")
def save_protector() -> None:
    """Read-only Save Protector commands."""


@save_protector.command("status")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def save_protector_status(sims4_dir: str, fmt: str) -> None:
    """Inspect Sims 4 saves and backup signals without changing files."""
    from simanalysis.save_protector import (
        build_save_protector_status,
        format_save_protector_text,
    )

    status = build_save_protector_status(sims4_dir)
    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_save_protector_text(status))


@cli.group("tray")
def tray() -> None:
    """Read-only Tray dependency commands."""


@tray.command("status")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def tray_status(sims4_dir: str, fmt: str) -> None:
    """Inspect Sims 4 Tray dependency signals without changing files."""
    from simanalysis.tray_protector import (
        build_tray_status,
        format_tray_status_text,
    )

    status = build_tray_status(sims4_dir)
    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_tray_status_text(status))


@cli.group("updates")
def updates() -> None:
    """Read-only Update Desk staging commands."""


@updates.command("status")
@click.argument("staging_dir", type=click.Path(file_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def updates_status(staging_dir: str, fmt: str) -> None:
    """Inspect staged external downloads without changing files."""
    from simanalysis.update_desk import (
        build_update_staging_status,
        format_update_staging_text,
    )

    status = build_update_staging_status(staging_dir)
    if fmt == "json":
        _echo_json(status)
    else:
        click.echo(format_update_staging_text(status))


@updates.command("plan")
@click.argument("staging_dir", type=click.Path(file_okay=False))
@click.option("--mods", "mods_dir", type=click.Path(file_okay=False), required=True)
@click.option("--output", "-o", type=click.Path(dir_okay=False), default=None)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def updates_plan(
    staging_dir: str,
    mods_dir: str,
    output: Optional[str],
    fmt: str,
) -> None:
    """Build a read-only staged update install plan without changing Mods."""
    from simanalysis.update_desk import (
        build_update_install_plan,
        format_update_install_plan_text,
        write_update_install_plan,
    )

    plan = build_update_install_plan(staging_dir, mods_dir)
    if output:
        plan = write_update_install_plan(plan, output)

    if fmt == "json":
        _echo_json(plan)
    else:
        click.echo(format_update_install_plan_text(plan))


def _echo_update_result(label: str, manifest: dict[str, Any]) -> None:
    click.echo(f"Update Desk {label} complete")
    click.echo(f"Status: {manifest['status']}")
    click.echo(f"Manifest: {manifest['manifest_path']}")
    click.echo(f"Actions: {len(manifest['actions'])}")
    for action in manifest["actions"]:
        click.echo(f"  {action['action_id']}: {action['status']}")


@updates.command("commit")
@click.argument("plan_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--action",
    "actions",
    multiple=True,
    help="Update action ID to commit; may be passed multiple times",
)
@click.option("--all-actions", is_flag=True, help="Commit every copy action in the plan")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def updates_commit(
    plan_file: str,
    actions: tuple[str, ...],
    all_actions: bool,
    fmt: str,
) -> None:
    """Commit selected staged update copy actions through an update manifest."""
    from simanalysis.update_desk import UpdateInstaller

    try:
        applied = UpdateInstaller().commit_plan_file(
            plan_file,
            selected_action_ids=list(actions),
            all_actions=all_actions,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if fmt == "json":
        _echo_json(applied)
    else:
        _echo_update_result("commit", applied)


@updates.command("undo")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def updates_undo(manifest_file: str, fmt: str) -> None:
    """Undo a committed staged update from its manifest."""
    from simanalysis.update_desk import UpdateInstaller

    try:
        restored = UpdateInstaller().undo(manifest_file)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if fmt == "json":
        _echo_json(restored)
    else:
        _echo_update_result("undo", restored)


def _echo_ledger_scan_summary(payload: dict[str, Any]) -> None:
    click.echo("Ledger scan complete")
    click.echo(f"Root: {payload['root_path']}")
    click.echo(f"DB: {payload['db_path']}")
    click.echo(f"Files: {payload['files_total']}")
    click.echo(
        "Changes: "
        f"added {payload['added']}, removed {payload['removed']}, moved {payload['moved']}, "
        f"modified {payload['modified']}, unchanged {payload['unchanged']}"
    )
    click.echo(
        "Packages: "
        f"{payload['packages_total']} | Resources: {payload['resources_total']} | "
        f"Package parse errors: {payload['package_parse_errors']}"
    )
    for warning in payload.get("warnings", []):
        click.echo(click.style(f"Warning: {warning}", fg="yellow"))


def _echo_ledger_history(payload: dict[str, Any]) -> None:
    click.echo(f"Ledger history for {payload['root_path']}")
    click.echo(f"DB: {payload['db_path']}")
    scans = payload["scans"]
    if not scans:
        click.echo("No scans recorded")
        return
    for scan_row in scans:
        click.echo(
            f"#{scan_row['scan_id']} {scan_row['started_at']} "
            f"files={scan_row['files_total']} "
            f"added={scan_row['added']} removed={scan_row['removed']} "
            f"moved={scan_row['moved']} modified={scan_row['modified']} "
            f"unchanged={scan_row['unchanged']}"
        )


def _echo_ledger_events(payload: dict[str, Any]) -> None:
    click.echo(f"Ledger events for {payload['root_path']}")
    click.echo(f"DB: {payload['db_path']}")
    summary = payload["summary"]
    click.echo(
        "Changes: "
        f"added {summary['added']}, removed {summary['removed']}, moved {summary['moved']}, "
        f"modified {summary['modified']}, unchanged {summary['unchanged']}"
    )
    events = payload["events"]
    if not events:
        click.echo("No file events to show")
        return
    for event in events:
        previous = event.get("previous_relative_path")
        suffix = f" <- {previous}" if previous else ""
        click.echo(f"{event['change_status']}: {event['relative_path']}{suffix}")


@cli.group()
def ledger() -> None:
    """Read-only Sims 4 library ledger commands."""


@ledger.command("scan")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--db", type=click.Path(), default=None, help="Inventory database path")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option(
    "--export-snapshot",
    is_flag=True,
    help="Include the latest snapshot in JSON output",
)
def ledger_scan(sims4_dir: str, db: Optional[str], fmt: str, export_snapshot: bool) -> None:
    """Record a read-only inventory snapshot of a Sims 4 folder."""
    from simanalysis.inventory import InventoryScanner

    root = Path(sims4_dir).expanduser().resolve()
    db_path = _ledger_db_path(db)
    scanner = InventoryScanner(db_path)
    summary = scanner.scan(root)
    payload = summary.to_dict()
    payload["db_path"] = str(db_path)
    if export_snapshot and fmt == "json":
        payload["snapshot"] = scanner.export_latest_snapshot(root)

    if fmt == "json":
        _echo_json(payload)
    else:
        _echo_ledger_scan_summary(payload)


@ledger.command("history")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--db", type=click.Path(), default=None, help="Inventory database path")
@click.option("--limit", type=int, default=20, help="Maximum scans to return")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ledger_history(sims4_dir: str, db: Optional[str], limit: int, fmt: str) -> None:
    """Show recent read-only ledger scans for a Sims 4 folder."""
    from simanalysis.inventory import InventoryScanner

    root = Path(sims4_dir).expanduser().resolve()
    db_path = _ledger_db_path(db)
    scanner = InventoryScanner(db_path)
    payload = {
        "root_path": str(root),
        "db_path": str(db_path),
        "scans": scanner.list_scan_history(root, limit=limit),
    }
    if fmt == "json":
        _echo_json(payload)
    else:
        _echo_ledger_history(payload)


@ledger.command("events")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--db", type=click.Path(), default=None, help="Inventory database path")
@click.option(
    "--include-unchanged",
    is_flag=True,
    help="Include unchanged files in the latest scan events",
)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ledger_events(sims4_dir: str, db: Optional[str], include_unchanged: bool, fmt: str) -> None:
    """Show per-file changes from the latest ledger scan."""
    from simanalysis.inventory import InventoryScanner

    root = Path(sims4_dir).expanduser().resolve()
    db_path = _ledger_db_path(db)
    scanner = InventoryScanner(db_path)
    payload = scanner.latest_file_events(root, include_unchanged=include_unchanged)
    payload["db_path"] = str(db_path)
    if fmt == "json":
        _echo_json(payload)
    else:
        _echo_ledger_events(payload)


def _echo_ops_plan(plan: dict[str, Any], output: Optional[str]) -> None:
    click.echo("Ops plan ready")
    click.echo(f"Root: {plan['root_path']}")
    if output:
        click.echo(f"Wrote plan: {Path(output).expanduser().resolve()}")
    summary = plan["summary"]
    click.echo(
        f"Findings: {summary['finding_count']} | Actions: {summary['action_count']} | "
        f"Duplicate groups: {summary['duplicate_groups']}"
    )
    for finding in plan["findings"]:
        click.echo(f"{finding['category']}: {finding['title']}")
        for action in finding["actions"]:
            click.echo(f"  {action['action_id']}: {action['source_relative_path']}")


def _echo_ops_result(label: str, manifest: dict[str, Any]) -> None:
    click.echo(f"Ops {label} complete")
    click.echo(f"Status: {manifest['status']}")
    click.echo(f"Manifest: {manifest['manifest_path']}")
    click.echo(f"Actions: {len(manifest['actions'])}")
    for action in manifest["actions"]:
        click.echo(f"  {action['action_id']}: {action['status']}")


@cli.group()
def ops() -> None:
    """Manifest-first cleanup operation commands."""


@ops.command("plan")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--db", type=click.Path(), default=None, help="Inventory database path")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write plan JSON to file")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ops_plan(sims4_dir: str, db: Optional[str], output: Optional[str], fmt: str) -> None:
    """Create a read-only cleanup operation plan from the latest ledger scan."""
    from simanalysis.cleanup import CleanupPlanner

    root = Path(sims4_dir).expanduser().resolve()
    db_path = _ledger_db_path(db)
    planner = CleanupPlanner(db_path)
    plan = planner.export_plan(root, output) if output else planner.plan(root)

    if fmt == "json":
        _echo_json(plan)
    else:
        _echo_ops_plan(plan, output)


@ops.command("commit")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("plan_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--action",
    "actions",
    multiple=True,
    help="Cleanup action ID to commit; may be passed multiple times",
)
@click.option("--all-actions", is_flag=True, help="Commit every action in the plan")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ops_commit(
    sims4_dir: str,
    plan_file: str,
    actions: tuple[str, ...],
    all_actions: bool,
    fmt: str,
) -> None:
    """Stage and apply selected cleanup actions through an operation manifest."""
    from simanalysis.operating_table import OperatingTable

    root = Path(sims4_dir).expanduser().resolve()
    table = OperatingTable()
    staged = table.stage_cleanup_plan_file(
        root,
        plan_file,
        selected_action_ids=list(actions),
        all_actions=all_actions,
    )
    applied = table.apply(staged["manifest_path"])
    if fmt == "json":
        _echo_json(applied)
    else:
        _echo_ops_result("commit", applied)


@ops.command("restore")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ops_restore(manifest_file: str, fmt: str) -> None:
    """Restore a committed cleanup operation from its manifest."""
    from simanalysis.operating_table import OperatingTable

    restored = OperatingTable().restore(manifest_file)
    if fmt == "json":
        _echo_json(restored)
    else:
        _echo_ops_result("restore", restored)


@ops.command("undo")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def ops_undo(manifest_file: str, fmt: str) -> None:
    """Undo a committed cleanup operation from its manifest."""
    from simanalysis.operating_table import OperatingTable

    restored = OperatingTable().restore(manifest_file)
    if fmt == "json":
        _echo_json(restored)
    else:
        _echo_ops_result("undo", restored)


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


@cli.command("doctor")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--mods", type=click.Path(), default=None, help="Mods dir (default: <sims4_dir>/Mods)"
)
@click.option("--recursive", is_flag=True, help="Also scan subfolders for exception logs")
@click.option(
    "--inventory-db",
    type=click.Path(dir_okay=False),
    default=None,
    help="Read inventory scan history from this SQLite ledger",
)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
@click.option("--output", "-o", type=click.Path(), default=None, help="Write report to file")
@click.option("--limit", type=int, default=20, help="Top-N findings to show per status group")
def doctor(
    sims4_dir: str,
    mods: Optional[str],
    recursive: bool,
    inventory_db: Optional[str],
    fmt: str,
    output: Optional[str],
    limit: int,
) -> None:
    """Run the combined read-only Sims Doctor over crash and UI exception logs."""
    import json

    from simanalysis.doctor import build_doctor_payload, format_doctor_text

    base = Path(sims4_dir).expanduser().resolve()
    mods_dir = Path(mods).expanduser().resolve() if mods else base / "Mods"
    if mods and (not mods_dir.exists() or not mods_dir.is_dir()):
        raise click.ClickException(f"Invalid Mods directory path: {mods}")

    if inventory_db:
        payload = build_doctor_payload(
            base,
            mods_dir,
            recursive,
            inventory_db=Path(inventory_db).expanduser().resolve(),
        )
    else:
        payload = build_doctor_payload(base, mods_dir, recursive)
    text = json.dumps(payload, indent=2) if fmt == "json" else format_doctor_text(payload, limit)

    if output:
        Path(output).expanduser().write_text(text, encoding="utf-8")
        click.echo(f"Wrote report to {output}")
    else:
        click.echo(text)


def _load_bisect_doctor_json(path: str) -> dict[str, Any]:
    import json

    source = Path(path).expanduser()
    try:
        parsed = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Doctor JSON is not valid JSON: {path}") from exc
    if not isinstance(parsed, dict):
        raise click.ClickException("Doctor JSON must be a JSON object")
    if "script_crashes" not in parsed or "ui_crashes" not in parsed:
        raise click.ClickException("Doctor JSON must contain script_crashes and ui_crashes")
    return parsed


def _echo_bisect_session(session: dict[str, Any]) -> None:
    click.echo("Bisect session")
    click.echo(f"Status: {session['status']}")
    click.echo(f"Session: {session['session_id']}")
    click.echo(f"Manifest: {session.get('manifest_path') or '(not saved)'}")
    click.echo(f"Candidates: {len(session.get('active_candidates', []))}")
    click.echo(f"Remaining: {len(session.get('remaining_candidates', []))}")
    click.echo(f"Current removed: {len(session.get('current_removed', []))}")
    next_batch = session.get("next_batch", [])
    if next_batch:
        click.echo("Next batch:")
        for path in next_batch:
            click.echo(f"  {path}")
    for warning in session.get("warnings", []):
        click.echo(f"Warning: {warning}")
    for blocker in session.get("blockers", []):
        click.echo(f"Blocker: {blocker}")


@cli.group()
def bisect() -> None:
    """Manifest-based Doctor bisection commands."""


@bisect.command("start")
@click.argument("sims4_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--mods", type=click.Path(), default=None, help="Mods dir (default: <sims4_dir>/Mods)"
)
@click.option("--doctor-json", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--recursive", is_flag=True, help="Also scan subfolders when building Doctor input")
@click.option("--save/--no-save", default=True, help="Write a persistent session manifest")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def bisect_start(
    sims4_dir: str,
    mods: Optional[str],
    doctor_json: Optional[str],
    recursive: bool,
    save: bool,
    fmt: str,
) -> None:
    """Create a Doctor-backed bisection session without moving mod files."""
    from simanalysis.doctor import build_doctor_payload
    from simanalysis.treatment import create_plan

    base = Path(sims4_dir).expanduser().resolve()
    mods_dir = Path(mods).expanduser().resolve() if mods else base / "Mods"
    if mods and (not mods_dir.exists() or not mods_dir.is_dir()):
        raise click.ClickException(f"Invalid Mods directory path: {mods}")

    payload = (
        _load_bisect_doctor_json(doctor_json)
        if doctor_json
        else build_doctor_payload(base, mods_dir, recursive)
    )
    session = create_plan(base, mods_dir, payload, save=save)
    if fmt == "json":
        _echo_json(session)
    else:
        _echo_bisect_session(session)


@bisect.command("status")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def bisect_status(manifest_file: str, fmt: str) -> None:
    """Show a bisection session manifest."""
    from simanalysis.treatment import load_session

    session = load_session(manifest_file)
    if fmt == "json":
        _echo_json(session)
    else:
        _echo_bisect_session(session)


@bisect.command("next")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def bisect_next(manifest_file: str, fmt: str) -> None:
    """Apply the next guarded bisection step from a session manifest."""
    from simanalysis.treatment import apply_next_step

    session = apply_next_step(manifest_file)
    if fmt == "json":
        _echo_json(session)
    else:
        _echo_bisect_session(session)


@bisect.command("record-verdict")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--verdict",
    type=click.Choice(["same_issue", "issue_gone", "different_issue"]),
    required=True,
)
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def bisect_record_verdict(manifest_file: str, verdict: str, fmt: str) -> None:
    """Record the user's game-test verdict for the latest applied bisection step."""
    from simanalysis.treatment import record_outcome

    session = record_outcome(manifest_file, verdict)
    if fmt == "json":
        _echo_json(session)
    else:
        _echo_bisect_session(session)


@bisect.command("restore")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--step", type=click.Choice(["latest", "all"]), default="latest")
@click.option("--format", "fmt", type=click.Choice(["txt", "json"]), default="txt")
def bisect_restore(manifest_file: str, step: str, fmt: str) -> None:
    """Restore bisection-moved files from a session manifest."""
    from simanalysis.treatment import restore_session

    session = restore_session(manifest_file, step=step)
    if fmt == "json":
        _echo_json(session)
    else:
        _echo_bisect_session(session)


@bisect.command("handoff")
@click.argument("manifest_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--output", "-o", type=click.Path(), default=None, help="Write Markdown to file")
def bisect_handoff(manifest_file: str, output: Optional[str]) -> None:
    """Render a read-only Markdown field handoff from a bisection manifest."""
    from simanalysis.treatment import load_session, render_handoff

    session = load_session(manifest_file)
    handoff = render_handoff(session)
    if output:
        Path(output).expanduser().write_text(handoff, encoding="utf-8")
        click.echo(f"Wrote handoff to {output}")
    else:
        click.echo(handoff)


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
