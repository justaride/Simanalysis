"""Interactive Terminal User Interface using Textual."""

from pathlib import Path
from typing import List, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)
from textual.widgets.tree import TreeNode

from simanalysis.analyzers import ModAnalyzer
from simanalysis.models import AnalysisResult, Mod, ModConflict, Severity


class SummaryPane(Static):
    """Summary statistics pane."""

    def __init__(self, result: Optional[AnalysisResult] = None):
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        """Compose the summary pane."""
        if not self.result:
            yield Label("Loading...")
            return

        # Count conflicts by severity
        critical = len([c for c in self.result.conflicts if c.severity == Severity.CRITICAL])
        high = len([c for c in self.result.conflicts if c.severity == Severity.HIGH])
        medium = len([c for c in self.result.conflicts if c.severity == Severity.MEDIUM])
        low = len([c for c in self.result.conflicts if c.severity == Severity.LOW])

        yield Label(f"[bold cyan]📊 Analysis Summary[/bold cyan]\n")
        yield Label(f"Total Mods: [bold]{len(self.result.mods)}[/bold]")
        yield Label(f"Total Conflicts: [bold]{len(self.result.conflicts)}[/bold]")
        yield Label("")

        if critical > 0:
            yield Label(f"[bold red]🔴 Critical:[/bold red] {critical}")
        if high > 0:
            yield Label(f"[bold yellow]🟠 High:[/bold yellow] {high}")
        if medium > 0:
            yield Label(f"[yellow]🟡 Medium:[/yellow] {medium}")
        if low > 0:
            yield Label(f"[green]🟢 Low:[/green] {low}")

        # Performance metrics
        perf = self.result.performance
        yield Label(f"\n[bold cyan]📈 Performance[/bold cyan]")
        yield Label(f"Total Size: {perf.total_size_mb:.2f} MB")
        yield Label(f"Resources: {perf.total_resources:,}")
        yield Label(f"Est. Load Time: {perf.estimated_load_time_seconds:.1f}s")

        complexity_color = "red" if perf.complexity_score >= 80 else "yellow" if perf.complexity_score >= 60 else "green"
        yield Label(f"Complexity: [{complexity_color}]{perf.complexity_score:.1f}/100[/{complexity_color}]")


class ConflictsTable(Static):
    """Conflicts data table."""

    def __init__(self, conflicts: List[ModConflict]):
        super().__init__()
        self.conflicts = conflicts
        self.filtered_conflicts = conflicts
        self.filter_severity: Optional[Severity] = None

    def compose(self) -> ComposeResult:
        """Compose the conflicts table."""
        table = DataTable()
        table.add_columns("Severity", "Type", "Description", "Affected")
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Sort by severity
        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        sorted_conflicts = sorted(
            self.filtered_conflicts,
            key=lambda c: severity_order[c.severity]
        )

        for conflict in sorted_conflicts[:100]:  # Limit to 100 for performance
            severity_emoji = {
                Severity.CRITICAL: "🔴",
                Severity.HIGH: "🟠",
                Severity.MEDIUM: "🟡",
                Severity.LOW: "🟢",
            }[conflict.severity]

            desc = conflict.description
            if len(desc) > 60:
                desc = desc[:57] + "..."

            table.add_row(
                f"{severity_emoji} {conflict.severity.value}",
                conflict.type.value,
                desc,
                f"{len(conflict.affected_mods)} mods",
            )

        yield table

    def filter_by_severity(self, severity: Optional[Severity]) -> None:
        """Filter conflicts by severity."""
        self.filter_severity = severity
        if severity:
            self.filtered_conflicts = [c for c in self.conflicts if c.severity == severity]
        else:
            self.filtered_conflicts = self.conflicts
        self.refresh(recompose=True)


class ModsTable(Static):
    """Mods data table."""

    def __init__(self, mods: List[Mod]):
        super().__init__()
        self.mods = mods

    def compose(self) -> ComposeResult:
        """Compose the mods table."""
        table = DataTable()
        table.add_columns("Type", "Name", "Size (MB)", "Resources", "Tunings")
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Sort by size
        sorted_mods = sorted(self.mods, key=lambda m: m.size, reverse=True)

        for mod in sorted_mods[:100]:  # Limit to 100 for performance
            icon = "📦" if mod.type.value == "package" else "🐍"
            name = mod.name[:40] if len(mod.name) <= 40 else mod.name[:37] + "..."
            size_mb = mod.size / 1024 / 1024

            table.add_row(
                icon,
                name,
                f"{size_mb:.2f}",
                f"{len(mod.resources):,}",
                f"{len(mod.tunings):,}",
            )

        yield table


class RecommendationsPane(Static):
    """Recommendations display pane."""

    def __init__(self, recommendations: List[str]):
        super().__init__()
        self.recommendations = recommendations

    def compose(self) -> ComposeResult:
        """Compose the recommendations pane."""
        yield Label("[bold cyan]💡 Recommendations[/bold cyan]\n")

        if not self.recommendations:
            yield Label("[green]✅ No recommendations - everything looks good![/green]")
            return

        for rec in self.recommendations:
            # Color code based on content
            if "CRITICAL" in rec:
                yield Label(f"[bold red]{rec}[/bold red]")
            elif "HIGH" in rec:
                yield Label(f"[bold yellow]{rec}[/bold yellow]")
            else:
                yield Label(rec)


class AnalysisScreen(Screen):
    """Main analysis results screen."""

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh"),
        Binding("e", "export", "Export Report"),
        Binding("f", "filter", "Filter"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self, result: AnalysisResult):
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        """Compose the analysis screen."""
        yield Header()

        with Container(id="app-grid"):
            # Left sidebar with summary
            with Vertical(id="sidebar"):
                yield SummaryPane(self.result)
                yield RecommendationsPane(self.result.recommendations)

            # Main content area with tabs
            with VerticalScroll(id="content"):
                with TabbedContent(initial="conflicts"):
                    with TabPane("Conflicts", id="conflicts"):
                        if self.result.conflicts:
                            yield Label(f"[bold]Showing {len(self.result.conflicts)} conflicts[/bold]")
                            yield ConflictsTable(self.result.conflicts)
                        else:
                            yield Label("[green]✅ No conflicts detected![/green]")

                    with TabPane("Mods", id="mods"):
                        yield Label(f"[bold]Showing {len(self.result.mods)} mods[/bold]")
                        yield ModsTable(self.result.mods)

                    with TabPane("Details", id="details"):
                        yield Label("[bold cyan]📋 Analysis Details[/bold cyan]\n")
                        yield Label(f"Directory: {self.result.metadata.mod_directory}")
                        yield Label(f"Duration: {self.result.metadata.analysis_duration_seconds:.2f}s")
                        yield Label(f"Version: {self.result.metadata.version}")

        yield Footer()

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()

    def action_refresh(self) -> None:
        """Refresh the display."""
        self.refresh()

    def action_export(self) -> None:
        """Export report."""
        self.app.push_screen(ExportScreen(self.result))

    def action_filter(self) -> None:
        """Open filter dialog."""
        self.app.push_screen(FilterScreen())

    def action_help(self) -> None:
        """Show help."""
        self.app.push_screen(HelpScreen())


class LoadingScreen(Screen):
    """Loading screen shown during analysis."""

    def compose(self) -> ComposeResult:
        """Compose the loading screen."""
        yield Header()
        with Container(id="loading-container"):
            yield LoadingIndicator()
            yield Label("[bold cyan]🔬 Analyzing mods...[/bold cyan]")
            yield Label("This may take a moment depending on your mod collection.")
        yield Footer()


class ExportScreen(Screen):
    """Export report screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, result: AnalysisResult):
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        """Compose the export screen."""
        yield Header()
        with Container(id="export-container"):
            yield Label("[bold cyan]📄 Export Report[/bold cyan]\n")
            yield Label("Enter output path:")
            yield Input(placeholder="~/Desktop/report.json", id="export-path")
            with Horizontal():
                yield Button("Export TXT", id="export-txt", variant="primary")
                yield Button("Export JSON", id="export-json", variant="primary")
                yield Button("Cancel", id="cancel")
        yield Footer()

    @on(Button.Pressed, "#export-txt")
    def export_txt(self) -> None:
        """Export as TXT."""
        path_input = self.query_one("#export-path", Input)
        path = Path(path_input.value).expanduser() if path_input.value else Path("~/Desktop/report.txt").expanduser()

        analyzer = ModAnalyzer()
        analyzer.export_report(self.result, path, format="txt")
        self.app.pop_screen()

    @on(Button.Pressed, "#export-json")
    def export_json(self) -> None:
        """Export as JSON."""
        path_input = self.query_one("#export-path", Input)
        path = Path(path_input.value).expanduser() if path_input.value else Path("~/Desktop/report.json").expanduser()

        analyzer = ModAnalyzer()
        analyzer.export_report(self.result, path, format="json")
        self.app.pop_screen()

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel export."""
        self.app.pop_screen()


class FilterScreen(Screen):
    """Filter conflicts screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the filter screen."""
        yield Header()
        with Container(id="filter-container"):
            yield Label("[bold cyan]🔍 Filter Conflicts[/bold cyan]\n")
            yield Button("All Conflicts", id="filter-all", variant="primary")
            yield Button("🔴 Critical Only", id="filter-critical", variant="error")
            yield Button("🟠 High Only", id="filter-high", variant="warning")
            yield Button("🟡 Medium Only", id="filter-medium")
            yield Button("🟢 Low Only", id="filter-low", variant="success")
            yield Button("Cancel", id="cancel")
        yield Footer()

    @on(Button.Pressed, "#filter-all")
    def filter_all(self) -> None:
        """Show all conflicts."""
        # TODO: Implement filtering
        self.app.pop_screen()

    @on(Button.Pressed, "#filter-critical")
    def filter_critical(self) -> None:
        """Show critical only."""
        # TODO: Implement filtering
        self.app.pop_screen()

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        """Cancel filter."""
        self.app.pop_screen()


class HelpScreen(Screen):
    """Help screen."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen."""
        yield Header()
        with VerticalScroll(id="help-container"):
            yield Label("[bold cyan]❓ Simanalysis Interactive TUI - Help[/bold cyan]\n")

            yield Label("[bold]Keyboard Shortcuts:[/bold]")
            yield Label("  q - Quit application")
            yield Label("  r - Refresh display")
            yield Label("  e - Export report")
            yield Label("  f - Filter conflicts")
            yield Label("  ? - Show this help")
            yield Label("  Tab - Navigate between tabs")
            yield Label("  ↑↓ - Navigate table rows")
            yield Label("  Escape - Close dialog/popup\n")

            yield Label("[bold]Navigation:[/bold]")
            yield Label("  Use Tab to switch between Conflicts, Mods, and Details tabs")
            yield Label("  Use arrow keys to navigate within tables")
            yield Label("  Click on rows to view details\n")

            yield Label("[bold]Features:[/bold]")
            yield Label("  • View all conflicts with severity indicators")
            yield Label("  • Browse mod collection with details")
            yield Label("  • Export reports to TXT or JSON")
            yield Label("  • Filter conflicts by severity level")
            yield Label("  • Real-time analysis updates\n")

            yield Button("Close", id="close", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#close")
    def close_help(self) -> None:
        """Close help screen."""
        self.app.pop_screen()


class SimanalysisApp(App):
    """Interactive Simanalysis TUI application."""

    CSS = """
    Screen {
        background: $surface;
    }

    #app-grid {
        layout: horizontal;
        height: 100%;
    }

    #sidebar {
        width: 35;
        height: 100%;
        background: $panel;
        padding: 1;
        border-right: solid $primary;
    }

    #content {
        width: 1fr;
        height: 100%;
        padding: 1;
    }

    #loading-container {
        align: center middle;
        height: 100%;
    }

    #export-container, #filter-container, #help-container {
        align: center middle;
        width: 60;
        height: auto;
        padding: 2;
        background: $panel;
        border: solid $primary;
    }

    DataTable {
        height: 1fr;
    }

    Input {
        margin: 1 0;
    }

    Button {
        margin: 1 1;
    }

    LoadingIndicator {
        height: 5;
    }
    """

    TITLE = "🔬 Simanalysis - Interactive Mod Analyzer"
    BINDINGS = [
        Binding("q", "quit", "Quit", key_display="Q"),
        Binding("?", "help", "Help", key_display="?"),
    ]

    def __init__(
        self,
        mods_directory: Path,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        recursive: bool = True,
    ):
        super().__init__()
        self.mods_directory = mods_directory
        self.parse_tunings = parse_tunings
        self.parse_scripts = parse_scripts
        self.calculate_hashes = calculate_hashes
        self.recursive = recursive
        self.result: Optional[AnalysisResult] = None

    def on_mount(self) -> None:
        """Start analysis when app mounts."""
        self.push_screen(LoadingScreen())
        self.run_analysis()

    @work(exclusive=True)
    async def run_analysis(self) -> None:
        """Run analysis in background."""
        analyzer = ModAnalyzer(
            parse_tunings=self.parse_tunings,
            parse_scripts=self.parse_scripts,
            calculate_hashes=self.calculate_hashes,
        )

        self.result = analyzer.analyze_directory(
            self.mods_directory,
            recursive=self.recursive,
        )

        # Switch to results screen
        self.pop_screen()
        self.push_screen(AnalysisScreen(self.result))

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())


def run_interactive_tui(
    mods_directory: Path,
    parse_tunings: bool = True,
    parse_scripts: bool = True,
    calculate_hashes: bool = True,
    recursive: bool = True,
) -> None:
    """
    Run the interactive TUI application.

    Args:
        mods_directory: Directory to analyze
        parse_tunings: Whether to parse XML tunings
        parse_scripts: Whether to analyze scripts
        calculate_hashes: Whether to calculate file hashes
        recursive: Whether to scan recursively
    """
    app = SimanalysisApp(
        mods_directory=mods_directory,
        parse_tunings=parse_tunings,
        parse_scripts=parse_scripts,
        calculate_hashes=calculate_hashes,
        recursive=recursive,
    )
    app.run()
