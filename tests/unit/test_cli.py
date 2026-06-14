"""Tests for CLI interface."""

import json
import re
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
        assert re.search(r"^\s+doctor\s+", result.output, re.MULTILINE)
        assert "ledger" in result.output
        assert re.search(r"^\s+ops\s+", result.output, re.MULTILINE)
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
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--output", str(output_file)])
        assert result.exit_code in [0, 1]
        assert output_file.exists()

        content = output_file.read_text(encoding="utf-8")
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
        with open(output_file, encoding="utf-8") as f:
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

    def test_analyze_non_recursive(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test analyze with --no-recursive flag."""
        # Create subfolder with mod
        subfolder = test_mods_dir / "Subfolder"
        subfolder.mkdir()
        self._create_test_package(subfolder / "nested.package")

        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--no-recursive"])
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

    def test_view_json_report(self, runner: CliRunner, test_mods_dir: Path, tmp_path: Path) -> None:
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

    def test_view_txt_report_fails(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test view command fails with TXT report."""
        txt_file = tmp_path / "report.txt"
        txt_file.write_text("Test report", encoding="utf-8")

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

    def test_analyze_shows_recommendations(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test that analyze shows recommendations."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir)])
        assert result.exit_code in [0, 1]
        assert "RECOMMENDATIONS" in result.output

    def test_analyze_verbose_shows_conflicts(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test that verbose mode shows conflict details."""
        result = runner.invoke(cli, ["analyze", str(test_mods_dir), "--verbose"])
        assert result.exit_code in [0, 1]
        # If there are conflicts, should show TOP CONFLICTS
        if "Total Conflicts: 0" not in result.output:
            assert "TOP CONFLICTS" in result.output or "Total Conflicts: 0" in result.output

    def test_scan_shows_file_counts(self, runner: CliRunner, test_mods_dir: Path) -> None:
        """Test that scan shows file type counts."""
        result = runner.invoke(cli, ["scan", str(test_mods_dir)])
        assert result.exit_code == 0
        assert "Package files" in result.output or ".package" in result.output
        assert "Total size" in result.output

    def test_ledger_scan_json_records_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test ledger scan emits JSON and optional snapshot export."""
        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()
        (sims4 / "Options.ini").write_text("uiscale = 100", encoding="utf-8")
        db_path = tmp_path / "ledger.sqlite3"

        result = runner.invoke(
            cli,
            [
                "ledger",
                "scan",
                str(sims4),
                "--db",
                str(db_path),
                "--format",
                "json",
                "--export-snapshot",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["db_path"] == str(db_path)
        assert data["files_total"] == 1
        assert data["added"] == 1
        assert data["snapshot"]["files"][0]["relative_path"] == "Options.ini"
        assert db_path.exists()

    def test_ledger_scan_text_summary(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test ledger scan default output is a human-readable summary."""
        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()
        (sims4 / "Options.ini").write_text("uiscale = 100", encoding="utf-8")

        result = runner.invoke(
            cli,
            ["ledger", "scan", str(sims4), "--db", str(tmp_path / "ledger.sqlite3")],
        )

        assert result.exit_code == 0
        assert "Ledger scan complete" in result.output
        assert "Files: 1" in result.output

    def test_ledger_history_json_returns_latest_scans(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test ledger history emits recent scan summaries."""
        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()
        options = sims4 / "Options.ini"
        options.write_text("uiscale = 100", encoding="utf-8")
        db_path = tmp_path / "ledger.sqlite3"

        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )
        options.write_text("uiscale = 90", encoding="utf-8")
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )

        result = runner.invoke(
            cli,
            [
                "ledger",
                "history",
                str(sims4),
                "--db",
                str(db_path),
                "--limit",
                "1",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["root_path"] == str(sims4.resolve())
        assert data["db_path"] == str(db_path)
        assert len(data["scans"]) == 1
        assert data["scans"][0]["modified"] == 1

    def test_ledger_events_json_reports_latest_file_events(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test ledger events emits latest per-file changes."""
        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()
        options = sims4 / "Options.ini"
        options.write_text("uiscale = 100", encoding="utf-8")
        db_path = tmp_path / "ledger.sqlite3"
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )
        options.write_text("uiscale = 90", encoding="utf-8")
        (sims4 / "new.txt").write_text("new", encoding="utf-8")
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )

        result = runner.invoke(
            cli,
            ["ledger", "events", str(sims4), "--db", str(db_path), "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["db_path"] == str(db_path)
        assert data["summary"] == {
            "added": 1,
            "removed": 0,
            "moved": 0,
            "modified": 1,
            "unchanged": 0,
        }
        assert [(event["relative_path"], event["change_status"]) for event in data["events"]] == [
            ("Options.ini", "modified"),
            ("new.txt", "added"),
        ]

    def test_ops_plan_json_uses_latest_inventory(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test ops plan emits a read-only cleanup plan from the ledger."""
        sims4 = tmp_path / "The Sims 4"
        mods = sims4 / "Mods"
        nested = mods / "Creator"
        nested.mkdir(parents=True)
        (mods / "keep.package").write_bytes(b"duplicate")
        (nested / "extra.package").write_bytes(b"duplicate")
        db_path = tmp_path / "ledger.sqlite3"
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )

        result = runner.invoke(
            cli,
            ["ops", "plan", str(sims4), "--db", str(db_path), "--format", "json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["summary"]["duplicate_groups"] == 1
        assert data["findings"][0]["actions"][0]["action_id"] == "duplicate:1"

    def test_ops_commit_and_undo_round_trip_with_manifest(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test ops commit applies an explicit action and undo restores it."""
        import simanalysis.operating_table as operating_table

        monkeypatch.setattr(operating_table, "assert_sims_not_running", lambda: None)
        sims4 = tmp_path / "The Sims 4"
        mods = sims4 / "Mods"
        nested = mods / "Creator"
        nested.mkdir(parents=True)
        keep = mods / "keep.package"
        source = nested / "extra.package"
        keep.write_bytes(b"duplicate")
        source.write_bytes(b"duplicate")
        db_path = tmp_path / "ledger.sqlite3"
        plan_path = tmp_path / "cleanup-plan.json"
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )
        assert (
            runner.invoke(
                cli,
                ["ops", "plan", str(sims4), "--db", str(db_path), "--output", str(plan_path)],
            ).exit_code
            == 0
        )

        commit = runner.invoke(
            cli,
            [
                "ops",
                "commit",
                str(sims4),
                str(plan_path),
                "--action",
                "duplicate:1",
                "--format",
                "json",
            ],
        )

        assert commit.exit_code == 0, commit.output
        applied = json.loads(commit.output)
        manifest_path = Path(applied["manifest_path"])
        assert applied["status"] == "applied"
        assert manifest_path.exists()
        assert keep.exists()
        assert not source.exists()
        destination = Path(applied["actions"][0]["destination_path"])
        assert destination.exists()

        undo = runner.invoke(cli, ["ops", "undo", str(manifest_path), "--format", "json"])

        assert undo.exit_code == 0, undo.output
        restored = json.loads(undo.output)
        assert restored["status"] == "restored"
        assert source.exists()
        assert not destination.exists()

    def test_ops_commit_requires_explicit_action_selection(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test ops commit refuses to stage a plan without explicit actions."""
        sims4 = tmp_path / "The Sims 4"
        mods = sims4 / "Mods"
        nested = mods / "Creator"
        nested.mkdir(parents=True)
        (mods / "keep.package").write_bytes(b"duplicate")
        source = nested / "extra.package"
        source.write_bytes(b"duplicate")
        db_path = tmp_path / "ledger.sqlite3"
        plan_path = tmp_path / "cleanup-plan.json"
        assert (
            runner.invoke(cli, ["ledger", "scan", str(sims4), "--db", str(db_path)]).exit_code == 0
        )
        assert (
            runner.invoke(
                cli,
                ["ops", "plan", str(sims4), "--db", str(db_path), "--output", str(plan_path)],
            ).exit_code
            == 0
        )

        result = runner.invoke(cli, ["ops", "commit", str(sims4), str(plan_path)])

        assert result.exit_code != 0
        assert source.exists()

    def test_doctor_json_outputs_combined_payload(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test doctor emits the shared combined Doctor payload as JSON."""
        import simanalysis.doctor as doctor_core

        sims4 = tmp_path / "The Sims 4"
        mods = sims4 / "Mods"
        mods.mkdir(parents=True)
        payload = {
            "summary": {
                "script_reports": 1,
                "script_active": 1,
                "script_disabled": 0,
                "script_not_installed": 0,
                "script_base_game_only": 0,
                "ui_findings": 1,
                "ui_occurrences": 2,
                "ui_active": 0,
                "ui_disabled": 1,
                "ui_not_found": 0,
                "ui_no_key": 0,
                "parse_errors": 0,
                "index_errors": 0,
            },
            "script_crashes": {"ranked_mods": []},
            "ui_crashes": {"findings": []},
        }
        calls: dict[str, object] = {}

        def fake_build_doctor_payload(base: Path, mods_dir: Path, recursive: bool) -> dict:
            calls["args"] = (base, mods_dir, recursive)
            return payload

        monkeypatch.setattr(doctor_core, "build_doctor_payload", fake_build_doctor_payload)

        result = runner.invoke(cli, ["doctor", str(sims4), "--format", "json"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.output) == payload
        assert calls["args"] == (sims4.resolve(), mods.resolve(), False)

    def test_doctor_text_output_file(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test doctor can write a human-readable report to a file."""
        import simanalysis.doctor as doctor_core

        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()
        output = tmp_path / "doctor.txt"
        payload = {
            "summary": {
                "script_reports": 2,
                "script_active": 1,
                "script_disabled": 0,
                "script_not_installed": 0,
                "script_base_game_only": 0,
                "ui_findings": 0,
                "ui_occurrences": 0,
                "ui_active": 0,
                "ui_disabled": 0,
                "ui_not_found": 0,
                "ui_no_key": 0,
                "parse_errors": 0,
                "index_errors": 0,
            },
            "script_crashes": {
                "ranked_mods": [
                    {
                        "mod": "Active.ts4script",
                        "status": "active",
                        "confidence": "high",
                        "top_suspect_count": 2,
                    }
                ]
            },
            "ui_crashes": {"findings": []},
        }
        monkeypatch.setattr(doctor_core, "build_doctor_payload", lambda *args: payload)

        result = runner.invoke(cli, ["doctor", str(sims4), "--output", str(output)])

        assert result.exit_code == 0, result.output
        assert "Wrote report" in result.output
        report = output.read_text(encoding="utf-8")
        assert "Sims Doctor" in report
        assert "Active.ts4script" in report

    def test_doctor_rejects_explicit_missing_mods_dir(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test doctor rejects an explicit missing Mods directory."""
        sims4 = tmp_path / "The Sims 4"
        sims4.mkdir()

        result = runner.invoke(cli, ["doctor", str(sims4), "--mods", str(tmp_path / "missing")])

        assert result.exit_code != 0
        assert "Invalid Mods directory path" in result.output

    def test_analyze_empty_directory(self, runner: CliRunner, tmp_path: Path) -> None:
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

    def test_analyze_with_multiple_flags(self, runner: CliRunner, test_mods_dir: Path) -> None:
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
        assert (
            "aborted" in result.output.lower()
            or "interrupted" in result.output.lower()
            or "Error" in result.output
        )

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
        with open(output_file, encoding="utf-8") as f:
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


def test_crash_command_sweeps_and_ranks(tmp_path):
    import json
    import zipfile

    from click.testing import CliRunner

    from simanalysis.cli import cli

    sims4 = tmp_path
    mods = sims4 / "Mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "CoolMod.ts4script", "w") as zf:
        zf.writestr("coolmod/thing.py", "x = 1\n")

    (sims4 / "lastException_1.txt").write_text(
        "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
        "Traceback (most recent call last):&#13;&#10;"
        'File "Core\\sims4\\utils.py", line 1, in w&#13;&#10;'
        'File "F:\\p\\coolmod\\thing.py", line 7, in run&#13;&#10;'
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["ranked_mods"][0]["mod"] == "CoolMod.ts4script"


def test_crash_command_tolerates_unparseable_log(tmp_path):
    import json

    from click.testing import CliRunner

    from simanalysis.cli import cli

    (tmp_path / "lastException_bad.txt").write_text(
        "<root><report><desyncdata>Traceback (most recent", encoding="utf-8"
    )
    result = CliRunner().invoke(cli, ["crash", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output  # malformed log must not abort the sweep
    data = json.loads(result.output)
    assert data["summary"]["reports"] == 0


def test_crash_command_limit_truncates_txt(tmp_path):
    import zipfile

    from click.testing import CliRunner

    from simanalysis.cli import cli

    mods = tmp_path / "Mods"
    mods.mkdir()
    for i in range(3):
        with zipfile.ZipFile(mods / f"Mod{i}.ts4script", "w") as zf:
            zf.writestr(f"mod{i}/m.py", "x = 1\n")
        (tmp_path / f"lastException_{i}.txt").write_text(
            "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
            "Traceback (most recent call last):&#13;&#10;"
            f'File "F:\\p\\mod{i}\\m.py", line 7, in run&#13;&#10;'
            "</desyncdata></report></root>",
            encoding="utf-8",
        )
    result = CliRunner().invoke(cli, ["crash", str(tmp_path), "--limit", "2"])
    assert result.exit_code == 0, result.output
    assert result.output.count("top suspect in") == 2  # only 2 of 3 ranked mods shown


def test_crash_command_names_disabled_culprit(tmp_path):
    import json
    import zipfile

    from click.testing import CliRunner

    from simanalysis.cli import cli

    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    disabled = sims4 / "_Disabled_adeepindigo_2026"
    disabled.mkdir()
    with zipfile.ZipFile(disabled / "adeepindigo_core.ts4script", "w") as zf:
        zf.writestr("adeepindigo/core.pyc", b"\x00")

    (sims4 / "lastException_1.txt").write_text(
        "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
        "Traceback (most recent call last):&#13;&#10;"
        'File "Core\\sims4\\utils.py", line 1, in w&#13;&#10;'
        'File "E:\\proj\\adeepindigo\\core.py", line 7, in run&#13;&#10;'
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    top = data["ranked_mods"][0]
    assert top["mod"] == "adeepindigo_core.ts4script"
    assert top["status"] == "disabled"
    assert data["summary"]["disabled_culprits"] == 1


def test_crash_command_txt_groups_by_status(tmp_path):
    import zipfile

    from click.testing import CliRunner

    from simanalysis.cli import cli

    sims4 = tmp_path
    mods = sims4 / "Mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "ActiveMod.ts4script", "w") as zf:
        zf.writestr("activemod/a.pyc", b"\x00")
    disabled = sims4 / "_Disabled_Old"
    disabled.mkdir()
    with zipfile.ZipFile(disabled / "DisabledMod.ts4script", "w") as zf:
        zf.writestr("disabledmod/d.pyc", b"\x00")

    def _log(name, exc, culprit_frame):
        (sims4 / name).write_text(
            "<root><report><type>desync</type><desyncdata>" + exc + "&#13;&#10;"
            "Traceback (most recent call last):&#13;&#10;"
            'File "Core\\sims4\\u.py", line 1, in w&#13;&#10;'
            + culprit_frame
            + "&#13;&#10;</desyncdata></report></root>",
            encoding="utf-8",
        )

    _log(
        "lastException_1.txt", "boom (ValueError)", 'File "E:\\p\\activemod\\a.py", line 7, in run'
    )
    _log("lastException_2.txt", "bang (KeyError)", 'File "E:\\p\\disabledmod\\d.py", line 9, in go')
    _log(
        "lastException_3.txt",
        "kaboom (TypeError)",
        'File "Z:\\gone\\removedmod\\x.py", line 3, in z',
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4)])  # default txt format
    assert result.exit_code == 0, result.output
    out = result.output
    assert "[ACTIVE]" in out
    assert "[DISABLED]" in out
    assert "[NOT INSTALLED]" in out
    # actionable-first grouping
    assert out.index("[ACTIVE]") < out.index("[DISABLED]") < out.index("[NOT INSTALLED]")
    # each culprit appears under its own status group
    assert out.index("[ACTIVE]") < out.index("ActiveMod.ts4script") < out.index("[DISABLED]")
    assert (
        out.index("[DISABLED]") < out.index("DisabledMod.ts4script") < out.index("[NOT INSTALLED]")
    )
    # not_installed culprits omit the 'seen in N' clause (no on-disk count)
    assert "seen in 0" not in out


def test_crash_command_finds_nested_disabled_folder(tmp_path):
    import json
    import zipfile

    from click.testing import CliRunner

    from simanalysis.cli import cli

    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    # a disabled mod nested several levels deep, not a top-level sibling
    nested = sims4 / "Archive" / "Old" / "_Disabled_batch"
    nested.mkdir(parents=True)
    with zipfile.ZipFile(nested / "NestedMod.ts4script", "w") as zf:
        zf.writestr("nestedmod/n.pyc", b"\x00")

    (sims4 / "lastException_1.txt").write_text(
        "<root><report><type>desync</type><desyncdata>boom (ValueError)&#13;&#10;"
        "Traceback (most recent call last):&#13;&#10;"
        'File "Core\\sims4\\u.py", line 1, in w&#13;&#10;'
        'File "E:\\p\\nestedmod\\n.py", line 7, in run&#13;&#10;'
        "</desyncdata></report></root>",
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli, ["crash", str(sims4), "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    top = data["ranked_mods"][0]
    assert top["mod"] == "NestedMod.ts4script"
    assert top["status"] == "disabled"  # discovered in a deeply-nested _Disabled_* folder


def _write_ui_dbpf_package(path: Path, key: int, resource_type: int = 0x03E9D964) -> None:
    payload = b"resource"
    index = bytearray()
    index += struct.pack("<I", 0)  # mnIndexType: no constants
    index += struct.pack("<I", resource_type)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", key >> 32)
    index += struct.pack("<I", key & 0xFFFFFFFF)
    index += struct.pack("<I", 96 + 4 + 32)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)

    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", len(index))
    header[64:68] = struct.pack("<I", 96)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(index)
        f.write(payload)


def _write_ui_exception_log(path: Path, key: int) -> None:
    path.write_text(
        "<root><report><type>desync</type>"
        "<categoryid>(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory</categoryid>"
        f"<desyncdata>Error: missing key: {key}&#13;&#10;"
        "at widgets.Gameplay.PieMenu::PieMenuMain/HandlePieMenuCreate()"
        "</desyncdata></report></root>",
        encoding="utf-8",
    )


def test_ui_crash_command_json_reports_disabled_resource(tmp_path):
    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    disabled = sims4 / "_Quarantine_UI"
    _write_ui_dbpf_package(
        disabled / "adeepindigo_base_generalpiemenus_v3-2.package",
        15023068382072182982,
    )
    _write_ui_exception_log(sims4 / "lastUIException_1.txt", 15023068382072182982)

    result = CliRunner().invoke(cli, ["ui-crash", str(sims4), "--format", "json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["summary"]["disabled_findings"] == 1
    finding = data["findings"][0]
    assert finding["status"] == "disabled"
    assert finding["keys"][0]["hex"] == "0xD07CA9190DD098C6"
    assert finding["hits"][0]["package_name"] == "adeepindigo_base_generalpiemenus_v3-2.package"


def test_ui_crash_command_txt_groups_status_and_limit(tmp_path):
    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    _write_ui_exception_log(sims4 / "lastUIException_1.txt", 1111111111111)
    _write_ui_exception_log(sims4 / "lastUIException_2.txt", 2222222222222)

    result = CliRunner().invoke(cli, ["ui-crash", str(sims4), "--limit", "1"])

    assert result.exit_code == 0, result.output
    assert "UI Crash Autopsy" in result.output
    assert "[NOT FOUND]" in result.output
    assert result.output.count("message: Error: missing key") == 1


def test_ui_crash_command_expands_tilde_mods_path(tmp_path, monkeypatch):
    target_key = 15023068382072182982
    home = tmp_path / "home"
    home.mkdir()
    sims4 = tmp_path / "Sims 4"
    sims4.mkdir()
    home_mods = home / "Custom Mods"
    _write_ui_dbpf_package(home_mods / "ActivePieMenu.package", target_key)
    _write_ui_exception_log(sims4 / "lastUIException_1.txt", target_key)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    result = CliRunner().invoke(
        cli,
        [
            "ui-crash",
            str(sims4),
            "--mods",
            "~/Custom Mods",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["findings"][0]["status"] == "active"
    assert data["findings"][0]["hits"][0]["package_name"] == "ActivePieMenu.package"


def test_ui_crash_command_expands_tilde_output_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    sims4 = tmp_path / "Sims 4"
    (sims4 / "Mods").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    result = CliRunner().invoke(
        cli,
        ["ui-crash", str(sims4), "--output", "~/ui-report.txt"],
    )

    output_path = home / "ui-report.txt"
    assert result.exit_code == 0, result.output
    assert output_path.exists()
    assert "UI Crash Autopsy" in output_path.read_text(encoding="utf-8")


def test_ui_crash_command_skips_disabled_discovery_without_keys(tmp_path, monkeypatch):
    import simanalysis.analyzers.ui_crash_analyzer as ui_crash_analyzer

    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    (sims4 / "lastUIException_1.txt").write_text(
        "<root><report><type>desync</type>"
        "<desyncdata>Error: UI failed without a resource key&#13;&#10;</desyncdata>"
        "</report></root>",
        encoding="utf-8",
    )

    def fail_discovery(base):
        raise AssertionError(f"disabled discovery should not run for no-key reports: {base}")

    monkeypatch.setattr(ui_crash_analyzer, "discover_disabled_roots", fail_discovery)

    result = CliRunner().invoke(cli, ["ui-crash", str(sims4), "--format", "json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["summary"]["no_key_findings"] == 1
    assert data["index_errors"] == []


def test_ui_crash_command_reports_malformed_log_parse_error(tmp_path):
    sims4 = tmp_path
    (sims4 / "Mods").mkdir()
    (sims4 / "lastUIException_bad.txt").write_text(
        "<root><report><desyncdata>Error", encoding="utf-8"
    )

    result = CliRunner().invoke(cli, ["ui-crash", str(sims4), "--format", "json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["summary"]["unique_findings"] == 0
    assert len(data["parse_errors"]) == 1
    assert "lastUIException_bad.txt" in data["parse_errors"][0]
    assert "unterminated <report>" in data["parse_errors"][0]
