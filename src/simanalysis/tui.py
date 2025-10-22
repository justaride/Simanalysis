"""Rich Terminal User Interface for Simanalysis."""

from pathlib import Path
from typing import List, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from simanalysis.analyzers import ModAnalyzer
from simanalysis.models import AnalysisResult, ModConflict, Severity

console = Console()


class SimanalysisTUI:
    """
    Rich Terminal User Interface for Simanalysis.

    Provides beautiful, interactive displays for mod analysis results.
    """

    def __init__(self):
        """Initialize TUI."""
        self.console = console

    def create_header(self) -> Panel:
        """Create header panel."""
        header_text = Text()
        header_text.append("🔬 ", style="bold cyan")
        header_text.append("SIMANALYSIS", style="bold cyan")
        header_text.append(" - Derrick, the PhD in Simology", style="cyan")

        return Panel(
            header_text,
            style="bold cyan",
            border_style="cyan",
        )

    def create_summary_panel(self, result: AnalysisResult) -> Panel:
        """Create summary statistics panel."""
        # Count conflicts by severity
        critical = len([c for c in result.conflicts if c.severity == Severity.CRITICAL])
        high = len([c for c in result.conflicts if c.severity == Severity.HIGH])
        medium = len([c for c in result.conflicts if c.severity == Severity.MEDIUM])
        low = len([c for c in result.conflicts if c.severity == Severity.LOW])

        # Create grid
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="right")
        table.add_column(style="bold")

        table.add_row("Total Mods:", f"{len(result.mods):,}")
        table.add_row("Total Conflicts:", f"{len(result.conflicts):,}")
        table.add_row("")

        if critical > 0:
            table.add_row("🔴 Critical:", f"[bold red]{critical:,}[/bold red]")
        if high > 0:
            table.add_row("🟠 High:", f"[bold yellow]{high:,}[/bold yellow]")
        if medium > 0:
            table.add_row("🟡 Medium:", f"[yellow]{medium:,}[/yellow]")
        if low > 0:
            table.add_row("🟢 Low:", f"[green]{low:,}[/green]")

        return Panel(
            table,
            title="[bold]Summary[/bold]",
            border_style="cyan",
        )

    def create_performance_panel(self, result: AnalysisResult) -> Panel:
        """Create performance metrics panel."""
        perf = result.performance

        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="right")
        table.add_column(style="bold")

        table.add_row("Total Size:", f"{perf.total_size_mb:.2f} MB")
        table.add_row("Resources:", f"{perf.total_resources:,}")
        table.add_row("Tunings:", f"{perf.total_tunings:,}")
        table.add_row("Scripts:", f"{perf.total_scripts:,}")
        table.add_row("")
        table.add_row("Est. Load Time:", f"{perf.estimated_load_time_seconds:.1f}s")
        table.add_row("Est. Memory:", f"{perf.estimated_memory_mb:.1f} MB")

        # Color code complexity
        if perf.complexity_score >= 80:
            complexity_style = "bold red"
        elif perf.complexity_score >= 60:
            complexity_style = "yellow"
        else:
            complexity_style = "green"

        table.add_row(
            "Complexity:",
            f"[{complexity_style}]{perf.complexity_score:.1f}/100[/{complexity_style}]"
        )

        return Panel(
            table,
            title="[bold]Performance Metrics[/bold]",
            border_style="cyan",
        )

    def create_conflicts_table(
        self, conflicts: List[ModConflict], limit: int = 20
    ) -> Table:
        """Create detailed conflicts table."""
        table = Table(
            title=f"[bold]Conflicts[/bold] (showing {min(len(conflicts), limit)} of {len(conflicts)})",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            expand=True,
        )

        table.add_column("Severity", width=10)
        table.add_column("Type", width=20)
        table.add_column("Description", ratio=2)
        table.add_column("Mods", width=15)

        # Sort by severity (critical first)
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }
        sorted_conflicts = sorted(
            conflicts, key=lambda c: severity_order[c.severity]
        )

        for conflict in sorted_conflicts[:limit]:
            # Color code severity
            severity_colors = {
                Severity.CRITICAL: "bold red",
                Severity.HIGH: "bold yellow",
                Severity.MEDIUM: "yellow",
                Severity.LOW: "green",
            }
            severity_style = severity_colors[conflict.severity]

            # Truncate description
            desc = conflict.description
            if len(desc) > 80:
                desc = desc[:77] + "..."

            # Count affected mods
            mod_count = len(conflict.affected_mods)
            mod_text = f"{mod_count} mod" + ("s" if mod_count != 1 else "")

            table.add_row(
                f"[{severity_style}]{conflict.severity.value}[/{severity_style}]",
                conflict.type.value,
                desc,
                mod_text,
            )

        return table

    def create_conflicts_tree(self, conflicts: List[ModConflict]) -> Tree:
        """Create hierarchical conflicts tree view."""
        tree = Tree("📊 [bold cyan]Conflicts by Severity[/bold cyan]")

        # Group by severity
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
            severity_conflicts = [c for c in conflicts if c.severity == severity]

            if not severity_conflicts:
                continue

            # Color code severity branch
            severity_colors = {
                Severity.CRITICAL: "bold red",
                Severity.HIGH: "bold yellow",
                Severity.MEDIUM: "yellow",
                Severity.LOW: "green",
            }
            style = severity_colors[severity]

            branch = tree.add(
                f"[{style}]{severity.value.upper()} ({len(severity_conflicts)})[/{style}]"
            )

            # Show first 10 conflicts in this severity
            for conflict in severity_conflicts[:10]:
                desc = conflict.description
                if len(desc) > 60:
                    desc = desc[:57] + "..."

                conflict_node = branch.add(f"• {desc}")

                # Add affected mods as sub-items
                if len(conflict.affected_mods) <= 3:
                    for mod in conflict.affected_mods:
                        conflict_node.add(f"[dim]└─ {mod}[/dim]")
                else:
                    conflict_node.add(
                        f"[dim]└─ {', '.join(conflict.affected_mods[:2])} "
                        f"and {len(conflict.affected_mods) - 2} more[/dim]"
                    )

            if len(severity_conflicts) > 10:
                branch.add(f"[dim]... and {len(severity_conflicts) - 10} more[/dim]")

        return tree

    def create_recommendations_panel(self, recommendations: List[str]) -> Panel:
        """Create recommendations panel."""
        if not recommendations:
            content = Text("✅ No recommendations - everything looks good!", style="green")
        else:
            lines = []
            for rec in recommendations[:10]:
                # Color code based on content
                if "CRITICAL" in rec:
                    lines.append(Text(rec, style="bold red"))
                elif "HIGH" in rec:
                    lines.append(Text(rec, style="bold yellow"))
                elif "TIP" in rec or "💡" in rec:
                    lines.append(Text(rec, style="cyan"))
                else:
                    lines.append(Text(rec))

            if len(recommendations) > 10:
                lines.append(Text(f"... and {len(recommendations) - 10} more", style="dim"))

            content = Group(*lines)

        return Panel(
            content,
            title="[bold]💡 Recommendations[/bold]",
            border_style="cyan",
        )

    def create_mods_table(self, result: AnalysisResult, limit: int = 20) -> Table:
        """Create mods listing table."""
        table = Table(
            title=f"[bold]Mods[/bold] (showing {min(len(result.mods), limit)} of {len(result.mods)})",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            expand=True,
        )

        table.add_column("Type", width=6)
        table.add_column("Name", ratio=2)
        table.add_column("Size", justify="right", width=12)
        table.add_column("Resources", justify="right", width=10)
        table.add_column("Tunings", justify="right", width=10)

        # Sort by size (largest first)
        sorted_mods = sorted(result.mods, key=lambda m: m.size, reverse=True)

        for mod in sorted_mods[:limit]:
            # Icon based on type
            icon = "📦" if mod.type.value == "package" else "🐍"

            # Format size
            size_mb = mod.size / 1024 / 1024
            if size_mb >= 100:
                size_str = f"[bold]{size_mb:.1f} MB[/bold]"
            else:
                size_str = f"{size_mb:.1f} MB"

            table.add_row(
                icon,
                mod.name[:50] if len(mod.name) <= 50 else mod.name[:47] + "...",
                size_str,
                f"{len(mod.resources):,}",
                f"{len(mod.tunings):,}",
            )

        return table

    def display_analysis_result(
        self, result: AnalysisResult, show_mods: bool = False
    ) -> None:
        """
        Display complete analysis result with rich formatting.

        Args:
            result: Analysis result to display
            show_mods: Whether to show detailed mod list
        """
        # Clear screen
        self.console.clear()

        # Display header
        self.console.print(self.create_header())
        self.console.print()

        # Create two-column layout for summary and performance
        summary_perf_table = Table.grid(padding=(0, 2), expand=True)
        summary_perf_table.add_column(ratio=1)
        summary_perf_table.add_column(ratio=1)
        summary_perf_table.add_row(
            self.create_summary_panel(result),
            self.create_performance_panel(result),
        )
        self.console.print(summary_perf_table)
        self.console.print()

        # Display recommendations
        self.console.print(self.create_recommendations_panel(result.recommendations))
        self.console.print()

        # Display conflicts
        if result.conflicts:
            # Show tree view for overview
            self.console.print(self.create_conflicts_tree(result.conflicts))
            self.console.print()

            # Show detailed table
            self.console.print(self.create_conflicts_table(result.conflicts))
            self.console.print()

        # Display mod list if requested
        if show_mods:
            self.console.print(self.create_mods_table(result))
            self.console.print()

        # Display analysis metadata
        meta_text = Text()
        meta_text.append(f"⏱️  Analysis completed in {result.metadata.analysis_duration_seconds:.2f}s", style="dim")
        meta_text.append(" | ", style="dim")
        meta_text.append(f"Analyzed: {result.metadata.mod_directory}", style="dim")
        self.console.print(Panel(meta_text, border_style="dim"))

    def display_with_progress(
        self,
        mods_directory: Path,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        recursive: bool = True,
        show_mods: bool = False,
    ) -> AnalysisResult:
        """
        Run analysis with live progress display.

        Args:
            mods_directory: Directory to analyze
            parse_tunings: Whether to parse XML tunings
            parse_scripts: Whether to analyze scripts
            calculate_hashes: Whether to calculate file hashes
            recursive: Whether to scan recursively
            show_mods: Whether to show detailed mod list at end

        Returns:
            Analysis result
        """
        # Create analyzer
        analyzer = ModAnalyzer(
            parse_tunings=parse_tunings,
            parse_scripts=parse_scripts,
            calculate_hashes=calculate_hashes,
        )

        # Create progress display
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(complete_style="cyan", finished_style="green"),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )

        # Run analysis with progress
        with progress:
            # Create tasks
            scan_task = progress.add_task("[cyan]Scanning mods...", total=100)
            analyze_task = progress.add_task("[cyan]Analyzing conflicts...", total=100)

            # Scan phase
            progress.update(scan_task, advance=50)
            result = analyzer.analyze_directory(mods_directory, recursive=recursive)
            progress.update(scan_task, completed=100)

            # Analyze phase
            progress.update(analyze_task, advance=100)

        # Display results
        self.console.print()
        self.display_analysis_result(result, show_mods=show_mods)

        return result

    def display_scan_result(
        self, mods_directory: Path, recursive: bool = True, verbose: bool = False
    ) -> None:
        """
        Display quick scan results.

        Args:
            mods_directory: Directory to scan
            recursive: Whether to scan recursively
            verbose: Whether to show detailed mod list
        """
        from simanalysis.models import ModType
        from simanalysis.scanners import ModScanner

        # Create scanner
        scanner = ModScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )

        # Scan with progress
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            TimeElapsedColumn(),
            console=self.console,
        )

        with progress:
            task = progress.add_task("[cyan]Scanning directory...", total=None)
            mods = scanner.scan_directory(mods_directory, recursive=recursive)
            progress.update(task, completed=True)

        # Display results
        self.console.print()
        self.console.print(self.create_header())
        self.console.print()

        # Count by type
        packages = len([m for m in mods if m.type == ModType.PACKAGE])
        scripts = len([m for m in mods if m.type == ModType.SCRIPT])
        total_size = sum(m.size for m in mods)

        # Create summary
        table = Table.grid(padding=(0, 2))
        table.add_column(style="cyan", justify="right")
        table.add_column(style="bold")

        table.add_row("Total Mods:", f"{len(mods):,}")
        table.add_row("📦 Packages:", f"{packages:,}")
        table.add_row("🐍 Scripts:", f"{scripts:,}")
        table.add_row("💾 Total Size:", f"{total_size / 1024 / 1024:.2f} MB")

        self.console.print(Panel(table, title="[bold]Scan Results[/bold]", border_style="cyan"))
        self.console.print()

        # Show detailed list if verbose
        if verbose and mods:
            from simanalysis.models import AnalysisResult, AnalysisMetadata, PerformanceMetrics
            from datetime import datetime

            # Create minimal result for display
            result = type('obj', (), {
                'mods': mods,
                'performance': PerformanceMetrics(
                    total_mods=len(mods),
                    total_size_mb=total_size / 1024 / 1024,
                    total_resources=0,
                    total_tunings=0,
                    total_scripts=0,
                    estimated_load_time_seconds=0,
                    estimated_memory_mb=0,
                    complexity_score=0,
                ),
            })()

            self.console.print(self.create_mods_table(result, limit=50))


# Singleton instance
tui = SimanalysisTUI()
