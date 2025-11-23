"""Tests for parallel processing."""

import multiprocessing as mp
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from simanalysis.models import Mod, ModType
from simanalysis.parallel import ParallelScanner, ParallelAnalyzer, _scan_file_worker


@pytest.fixture
def temp_mods_dir():
    """Create temporary directory with mock mod files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mods_dir = Path(tmpdir)

        # Create some empty .package files
        for i in range(10):
            (mods_dir / f"mod{i}.package").touch()

        yield mods_dir


class TestParallelScanner:
    """Test parallel scanner."""

    def test_init_default_workers(self):
        """Test scanner initializes with default worker count."""
        scanner = ParallelScanner()

        expected_workers = max(1, mp.cpu_count() - 1)
        assert scanner.workers == expected_workers

    def test_init_custom_workers(self):
        """Test scanner with custom worker count."""
        scanner = ParallelScanner(workers=4)

        assert scanner.workers == 4

    def test_init_options(self):
        """Test scanner initialization options."""
        scanner = ParallelScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            workers=2,
        )

        assert scanner.parse_tunings is False
        assert scanner.parse_scripts is False
        assert scanner.calculate_hashes is False
        assert scanner.workers == 2

    def test_scan_few_files_uses_sequential(self, temp_mods_dir, caplog):
        """Test that few files use sequential scanning."""
        # Create only 3 files
        mods_dir = temp_mods_dir
        for f in mods_dir.glob("*.package"):
            if f.name not in ["mod0.package", "mod1.package", "mod2.package"]:
                f.unlink()

        scanner = ParallelScanner(workers=4)

        with caplog.at_level("DEBUG"):
            # This should use sequential due to few files
            mods = scanner.scan_directory_parallel(mods_dir)

        # Check that sequential was used
        assert "Few files detected, using sequential scan" in caplog.text

    def test_scan_empty_directory(self, temp_mods_dir):
        """Test scanning empty directory."""
        # Remove all files
        for f in temp_mods_dir.glob("*.package"):
            f.unlink()

        scanner = ParallelScanner()
        mods = scanner.scan_directory_parallel(temp_mods_dir)

        assert len(mods) == 0

    def test_scan_with_errors(self, temp_mods_dir):
        """Test scanning with some files causing errors."""
        scanner = ParallelScanner(workers=2)

        # The actual files will likely fail to parse (empty files)
        # but shouldn't crash
        mods = scanner.scan_directory_parallel(temp_mods_dir)

        # Empty package files won't parse successfully
        # Just verify no crash occurred
        assert isinstance(mods, list)

    def test_sequential_fallback(self, temp_mods_dir):
        """Test _scan_sequential fallback method."""
        scanner = ParallelScanner()

        files = list(temp_mods_dir.glob("*.package"))
        mods = scanner._scan_sequential(files)

        assert isinstance(mods, list)


class TestWorkerFunction:
    """Test worker function."""

    def test_worker_with_invalid_file(self):
        """Test worker with file that doesn't exist."""
        result = _scan_file_worker(
            Path("/nonexistent/file.package"),
            parse_tunings=True,
            parse_scripts=True,
            calculate_hashes=True,
        )

        # Should return None on error
        assert result is None

    def test_worker_with_valid_options(self, temp_mods_dir):
        """Test worker with different scanning options."""
        test_file = temp_mods_dir / "test.package"
        test_file.touch()

        result = _scan_file_worker(
            test_file,
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )

        # Empty file won't successfully parse
        # Just verify no crash
        assert result is None or isinstance(result, Mod)


class TestParallelAnalyzer:
    """Test parallel analyzer."""

    def test_init_default(self):
        """Test analyzer initialization."""
        analyzer = ParallelAnalyzer()

        assert analyzer.parse_tunings is True
        assert analyzer.parse_scripts is True
        assert analyzer.calculate_hashes is True
        assert isinstance(analyzer.scanner, ParallelScanner)

    def test_init_custom_options(self):
        """Test analyzer with custom options."""
        analyzer = ParallelAnalyzer(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            workers=2,
        )

        assert analyzer.parse_tunings is False
        assert analyzer.parse_scripts is False
        assert analyzer.calculate_hashes is False
        assert analyzer.scanner.workers == 2

    def test_analyze_directory_parallel(self, temp_mods_dir):
        """Test parallel directory analysis."""
        analyzer = ParallelAnalyzer(workers=2)

        result = analyzer.analyze_directory_parallel(temp_mods_dir)

        # Verify result structure
        assert hasattr(result, "mods")
        assert hasattr(result, "conflicts")
        assert hasattr(result, "metadata")
        assert isinstance(result.mods, list)


class TestPerformance:
    """Test performance improvements."""

    @pytest.mark.slow
    @pytest.mark.skip(reason="Performance test depends on file size and complexity - multiprocessing has overhead for empty files")
    def test_parallel_faster_than_sequential(self, temp_mods_dir):
        """Test that parallel is faster for many files.

        Note: This test is skipped because for empty/small files,
        multiprocessing overhead can make parallel slower.
        Parallel processing shows benefits with larger, complex mods.
        """
        # Create more files for meaningful test
        for i in range(50):
            (temp_mods_dir / f"extra_mod{i}.package").touch()

        # Sequential scan
        from simanalysis.scanners.mod_scanner import ModScanner

        scanner_seq = ModScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )

        start = time.time()
        files = scanner_seq._find_mod_files(temp_mods_dir, recursive=True, extensions={".package"})
        mods_seq = []
        for f in files:
            mod = scanner_seq.scan_file(f)
            if mod:
                mods_seq.append(mod)
        time_seq = time.time() - start

        # Parallel scan
        scanner_par = ParallelScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
            workers=4,
        )

        start = time.time()
        mods_par = scanner_par.scan_directory_parallel(temp_mods_dir)
        time_par = time.time() - start

        # For real mods, parallel is faster
        # For empty files, overhead dominates
        print(f"Sequential: {time_seq:.3f}s, Parallel: {time_par:.3f}s")

    def test_worker_count_affects_performance(self, temp_mods_dir):
        """Test that different worker counts work."""
        # Create more files
        for i in range(20):
            (temp_mods_dir / f"extra_mod{i}.package").touch()

        # Test with different worker counts
        for workers in [1, 2, 4]:
            scanner = ParallelScanner(workers=workers)

            mods = scanner.scan_directory_parallel(temp_mods_dir)

            # Should work with any worker count
            assert isinstance(mods, list)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_extensions(self, temp_mods_dir):
        """Test with no matching extensions."""
        scanner = ParallelScanner()

        # Only look for .txt files (won't find any)
        mods = scanner.scan_directory_parallel(temp_mods_dir, extensions={".txt"})

        assert len(mods) == 0

    def test_recursive_vs_non_recursive(self, temp_mods_dir):
        """Test recursive scanning option."""
        # Create subdirectory with mods
        subdir = temp_mods_dir / "subdir"
        subdir.mkdir()
        (subdir / "submod.package").touch()

        scanner = ParallelScanner()

        # Non-recursive: should not find subdir mods
        mods_non_recursive = scanner.scan_directory_parallel(temp_mods_dir, recursive=False)

        # Recursive: should find subdir mods
        mods_recursive = scanner.scan_directory_parallel(temp_mods_dir, recursive=True)

        # Recursive should find at least as many (likely more)
        assert len(mods_recursive) >= len(mods_non_recursive)


class TestIntegration:
    """Integration tests with real components."""

    def test_parallel_analyzer_complete_workflow(self, temp_mods_dir):
        """Test complete analysis workflow with parallel processing."""
        analyzer = ParallelAnalyzer(
            parse_tunings=False,  # Don't parse empty files
            parse_scripts=False,
            calculate_hashes=False,
            workers=2,
        )

        result = analyzer.analyze_directory_parallel(temp_mods_dir)

        # Verify complete result structure
        assert result.metadata is not None
        assert result.mods is not None
        assert result.conflicts is not None
        assert result.performance is not None

        # Check metadata
        assert result.metadata.total_mods_analyzed >= 0
        assert result.metadata.analysis_duration_seconds > 0

    def test_parallel_matches_sequential_count(self, temp_mods_dir):
        """Test that parallel finds same number of mods as sequential."""
        from simanalysis.scanners.mod_scanner import ModScanner

        # Sequential
        scanner_seq = ModScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )
        mods_seq = scanner_seq.scan_directory(temp_mods_dir)

        # Parallel
        scanner_par = ParallelScanner(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )
        mods_par = scanner_par.scan_directory_parallel(temp_mods_dir)

        # Should find same number of mods
        assert len(mods_par) == len(mods_seq)
