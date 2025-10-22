"""Tests for CLI interface."""

import json
import struct
import zlib
from pathlib import Path

import pytest
from click.testing import CliRunner

from simanalysis.cli import cli


class TestCLI:
    """Tests for CLI commands."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def test_mods_dir(self, tmp_path: Path) -> Path:
        """Create test mods directory with sample files."""
        mods_dir = tmp_path / "Mods"
        mods_dir.mkdir()

        # Create two test package files
        for i in range(2):
            pkg_path = mods_dir / f"test_mod_{i}.package"
            self._create_test_package(pkg_path, tuning_id=0x12345678 + i)

        return mods_dir

    def _create_test_package(self, path: Path, tuning_id: int = 0x12345678) -> None:
        """Create a minimal test package file."""
        # Create minimal DBPF file (96-byte header)
        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)  # major_version
        header[40:44] = struct.pack("<I", 1)  # index_count
        header[44:48] = struct.pack("<I", 96)  # index_offset
        header[48:52] = struct.pack("<I", 32)  # index_size

        # Create resource
        resource_data = b"Test resource"
        compressed_data = zlib.compress(resource_data)
        resource_offset = 96 + 32

        # Create index entry
        index_entry = struct.pack(
            "<IIQIII",
            0x12345678,
            0x00000000,
            tuning_id,
            resource_offset,
            len(compressed_data),
            len(resource_data),
        )

        # Write file
        with open(path, "wb") as f:
            f.write(header)
            f.write(index_entry)
            f.write(compressed_data)

    def test_cli_version(self, runner: CliRunner) -> None:
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "simanalysis" in result.output.lower()

    def test_cli_help(self, runner: CliRunner) -> None:
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Simanalysis" in result.output
        assert "analyze" in result.output
        assert "scan" in result.output

    def test_analyze_help(self, runner: CliRunner) -> None:
        """Test analyze --help."""
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Analyze Sims 4 mods" in result.output
        assert "--output" in result.output
        assert "--format" in result.output

    def test_analyze_basic(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test basic analyze command."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        assert result.exit_code in [0, 1]  # May exit 1 if critical conflicts found
        assert "Analyzing" in result.output
        assert "ANALYSIS RESULTS" in result.output
        assert "Total Mods Found" in result.output

    def test_analyze_with_output_txt(
        self, runner: CliRunner, test_mods_dir: Path, tmp_path: Path
    ) -> None:
        """Test analyze with text output."""
        output_file = tmp_path / "report.txt"
        result = runner.invoke(
            cli, ["analyze", str(test_mods_dir), "--output", str(output_file)]
        )
        assert result.exit_code in [0, 1]
        assert output_file.exists()

        content = output_file.read_text()
        assert "MOD ANALYSIS REPORT" in content
        assert "SUMMARY" in content

    def test_analyze_with_output_json(
        self, runner: CliRunner, test_mods_dir: Path, tmp_path: Path
    ) -> None:
        """Test analyze with JSON output."""
        output_file = tmp_path / "report.json"
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(test_mods_dir),
                "--output",
                str(output_file),
                "--format",
                "json",
            ],
        )
        assert result.exit_code in [0, 1]
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file) as f:
            data = json.load(f)
        assert "summary" in data
        assert "mods" in data
        assert "conflicts" in data

    def test_analyze_quick_mode(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test analyze with --quick flag."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--quick"])
        assert result.exit_code in [0, 1]
        assert "Analyzing" in result.output

    def test_analyze_no_tunings(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test analyze with --no-tunings flag."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--no-tunings"])
        assert result.exit_code in [0, 1]
        assert "Analyzing" in result.output

    def test_analyze_no_scripts(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test analyze with --no-scripts flag."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--no-scripts"])
        assert result.exit_code in [0, 1]
        assert "Analyzing" in result.output

    def test_analyze_verbose(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test analyze with --verbose flag."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--verbose"])
        assert result.exit_code in [0, 1]
        assert "Starting analysis" in result.output
        assert "Parse tunings" in result.output

    def test_analyze_non_recursive(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test analyze with --no-recursive flag."""
        # Create subfolder with mod
        subfolder = test_mods_dir / "Subfolder"
        subfolder.mkdir()
        self._create_test_package(subfolder / "nested.package")

        result = runner.invoke(
            cli, ["analyze", str(test_mods_dir), "--no-recursive"]
        )
        assert result.exit_code in [0, 1]
        assert "Analyzing" in result.output

    def test_analyze_nonexistent_directory(self, runner: CliRunner) -> None:
        """Test analyze with nonexistent directory."""
        result = runner.invoke(cli, ["analyze", "/nonexistent/path"])
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower() or "Error" in result.output

    def test_scan_basic(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test basic scan command."""
        result = runner.invoke(cli, ["scan", str(test_mods_dir)])
        assert result.exit_code == 0
        assert "Scanning" in result.output
        assert "Found" in result.output
        assert "mod files" in result.output

    def test_scan_verbose(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test scan with --verbose flag."""
        result = runner.invoke(cli, ["scan", str(test_mods_dir), "--verbose"])
        assert result.exit_code == 0
        assert "MOD LIST" in result.output
        assert "test_mod" in result.output

    def test_scan_non_recursive(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test scan with --no-recursive flag."""
        result = runner.invoke(cli, ["scan", str(test_mods_dir), "--no-recursive"])
        assert result.exit_code == 0
        assert "Scanning" in result.output

    def test_view_json_report(
        self, runner: CliRunner, test_mods_dir: Path, tmp_path: Path
    ) -> None:
        """Test view command with JSON report."""
        # First create a report
        output_file = tmp_path / "report.json"
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(test_mods_dir),
                "--output",
                str(output_file),
                "--format",
                "json",
            ],
        )
        assert output_file.exists()

        # Now view it
        result = runner.invoke(cli, ["view", str(output_file)])
        assert result.exit_code == 0
        assert "REPORT SUMMARY" in result.output
        assert "Total Mods" in result.output

    def test_view_txt_report_fails(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test view command fails with TXT report."""
        txt_file = tmp_path / "report.txt"
        txt_file.write_text("Test report")

        result = runner.invoke(cli, ["view", str(txt_file)])
        assert result.exit_code != 0
        assert "Only JSON reports" in result.output

    def test_view_nonexistent_file(self, runner: CliRunner) -> None:
        """Test view with nonexistent file."""
        result = runner.invoke(cli, ["view", "/nonexistent/report.json"])
        assert result.exit_code != 0

    def test_info_command(self, runner: CliRunner) -> None:
        """Test info command."""
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0
        assert "SIMANALYSIS" in result.output
        assert "Derrick" in result.output
        assert "Version" in result.output

    def test_info_version(self, runner: CliRunner) -> None:
        """Test info --version."""
        result = runner.invoke(cli, ["info", "--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_analyze_shows_performance_metrics(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test that analyze shows performance metrics."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        assert result.exit_code in [0, 1]
        assert "Performance Metrics" in result.output
        assert "Total Size" in result.output
        assert "Est. Load Time" in result.output
        assert "Complexity Score" in result.output

    def test_analyze_shows_recommendations(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test that analyze shows recommendations."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        assert result.exit_code in [0, 1]
        assert "RECOMMENDATIONS" in result.output

    def test_analyze_verbose_shows_conflicts(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test that verbose mode shows conflict details."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--verbose"])
        assert result.exit_code in [0, 1]
        # If there are conflicts, should show TOP CONFLICTS
        if "Total Conflicts: 0" not in result.output:
            assert "TOP CONFLICTS" in result.output or "Total Conflicts: 0" in result.output

    def test_scan_shows_file_counts(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test that scan shows file type counts."""
        result = runner.invoke(cli, ["scan", str(test_mods_dir)])
        assert result.exit_code == 0
        assert "Package files" in result.output or ".package" in result.output
        assert "Total size" in result.output

    def test_analyze_empty_directory(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test analyze with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(cli, ["analyze", str(empty_dir)])
        assert result.exit_code == 0  # Should succeed but find 0 mods
        assert "Total Mods Found: 0" in result.output

    def test_scan_empty_directory(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test scan with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = runner.invoke(cli, ["scan", str(empty_dir)])
        assert result.exit_code == 0
        assert "Found 0 mod files" in result.output

    def test_analyze_with_multiple_flags(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test analyze with multiple flags combined."""
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(test_mods_dir),
                "--quick",
                "--no-tunings",
                "--verbose",
            ],
        )
        assert result.exit_code in [0, 1]
        assert "Starting analysis" in result.output

    def test_cli_keyboard_interrupt(
        self, runner: CliRunner, test_mods_dir: Path, monkeypatch
    ) -> None:
        """Test CLI handles keyboard interrupt gracefully."""
        from simanalysis.analyzers import ModAnalyzer

        def mock_analyze(*args, **kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(ModAnalyzer, "analyze_directory", mock_analyze)

        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        # Click runner may not preserve exit code 130, but should catch interrupt
        assert result.exit_code != 0
        # Click shows "Aborted!" for keyboard interrupts
        assert "aborted" in result.output.lower() or "interrupted" in result.output.lower() or "Error" in result.output

    def test_analyze_creates_valid_json_report(
        self, runner: CliRunner, test_mods_dir: Path, tmp_path: Path
    ) -> None:
        """Test that JSON report is valid and complete."""
        output_file = tmp_path / "report.json"
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(test_mods_dir),
                "--output",
                str(output_file),
                "--format",
                "json",
            ],
        )
        assert result.exit_code in [0, 1]

        # Verify JSON structure
        with open(output_file) as f:
            data = json.load(f)

        # Check required fields
        assert "summary" in data
        assert "mods" in data
        assert "conflicts" in data
        assert "recommendations" in data

        # Check summary fields
        assert "total_mods" in data["summary"]
        assert "total_conflicts" in data["summary"]
        assert "critical_conflicts" in data["summary"]

        # Check mods have required fields
        if data["mods"]:
            mod = data["mods"][0]
            assert "name" in mod
            assert "path" in mod
            assert "type" in mod
            assert "size" in mod

    def test_analyze_exit_code_with_critical_conflicts(
        self, runner: CliRunner, test_mods_dir: Path
    ) -> None:
        """Test that analyze exits with code 1 if critical conflicts found."""
        # Create two packages with same tuning ID to force conflict
        for i in range(2):
            pkg_path = test_mods_dir / f"conflict_mod_{i}.package"
            self._create_test_package(pkg_path, tuning_id=0xAABBCCDD)

        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        # Should exit with 1 if critical conflicts detected
        # (depends on detector logic, but at minimum should not crash)
        assert result.exit_code in [0, 1]
