"""Parallel processing for faster mod analysis using multiprocessing."""

import logging
import multiprocessing as mp
from functools import partial
from pathlib import Path
from typing import List, Optional

from simanalysis.models import Mod
from simanalysis.scanners import ModScanner

logger = logging.getLogger(__name__)


def _scan_file_worker(
    file_path: Path,
    parse_tunings: bool,
    parse_scripts: bool,
    calculate_hashes: bool,
) -> Optional[Mod]:
    """
    Worker function to scan a single mod file.

    This function runs in a separate process.

    Args:
        file_path: Path to mod file
        parse_tunings: Whether to parse XML tunings
        parse_scripts: Whether to analyze scripts
        calculate_hashes: Whether to calculate file hashes

    Returns:
        Mod object or None if scan failed
    """
    try:
        # Create scanner in worker process
        scanner = ModScanner(
            parse_tunings=parse_tunings,
            parse_scripts=parse_scripts,
            calculate_hashes=calculate_hashes,
        )

        return scanner.scan_file(file_path)

    except Exception as e:
        # Return None on error (main process will handle)
        logger.debug(f"Worker error scanning {file_path.name}: {e}")
        return None


class ParallelScanner:
    """Scanner that uses multiprocessing for faster mod scanning."""

    def __init__(
        self,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        workers: Optional[int] = None,
    ):
        """
        Initialize parallel scanner.

        Args:
            parse_tunings: Whether to parse XML tunings from packages
            parse_scripts: Whether to analyze script files
            calculate_hashes: Whether to calculate file hashes
            workers: Number of worker processes (default: CPU count - 1)
        """
        self.parse_tunings = parse_tunings
        self.parse_scripts = parse_scripts
        self.calculate_hashes = calculate_hashes

        # Use CPU count - 1, minimum 1
        if workers is None:
            workers = max(1, mp.cpu_count() - 1)

        self.workers = workers
        logger.info(f"ParallelScanner initialized with {self.workers} workers")

    def scan_directory_parallel(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[set] = None,
    ) -> List[Mod]:
        """
        Scan directory for mods in parallel.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan (default: .package, .ts4script)

        Returns:
            List of mods found
        """
        from simanalysis.scanners.mod_scanner import ModScanner

        # Use regular scanner to find files
        scanner = ModScanner(
            parse_tunings=False,  # Don't parse yet
            parse_scripts=False,
            calculate_hashes=False,
        )

        # Default extensions
        if extensions is None:
            extensions = {".package", ".ts4script"}

        # Find all mod files (fast, no parsing)
        files = scanner._find_mod_files(directory, recursive, extensions)
        logger.info(f"Found {len(files)} files, scanning with {self.workers} workers...")

        if len(files) == 0:
            return []

        # If only a few files, don't use multiprocessing (overhead not worth it)
        if len(files) < 5:
            logger.debug("Few files detected, using sequential scan")
            return self._scan_sequential(files)

        # Create worker function with fixed parameters
        worker_fn = partial(
            _scan_file_worker,
            parse_tunings=self.parse_tunings,
            parse_scripts=self.parse_scripts,
            calculate_hashes=self.calculate_hashes,
        )

        # Scan files in parallel
        mods = []
        errors = 0

        try:
            with mp.Pool(processes=self.workers) as pool:
                # Use imap_unordered for better performance and progress tracking
                results = pool.imap_unordered(worker_fn, files, chunksize=max(1, len(files) // (self.workers * 4)))

                # Collect results
                for result in results:
                    if result is not None:
                        mods.append(result)
                    else:
                        errors += 1

        except Exception as e:
            logger.error(f"Parallel scanning failed: {e}")
            logger.info("Falling back to sequential scanning...")
            return self._scan_sequential(files)

        logger.info(f"Parallel scan complete: {len(mods)} mods, {errors} errors")
        return mods

    def _scan_sequential(self, files: List[Path]) -> List[Mod]:
        """
        Fall back to sequential scanning.

        Args:
            files: List of files to scan

        Returns:
            List of mods
        """
        from simanalysis.scanners.mod_scanner import ModScanner

        scanner = ModScanner(
            parse_tunings=self.parse_tunings,
            parse_scripts=self.parse_scripts,
            calculate_hashes=self.calculate_hashes,
        )

        mods = []
        for file_path in files:
            try:
                mod = scanner.scan_file(file_path)
                if mod:
                    mods.append(mod)
            except Exception as e:
                logger.warning(f"Failed to scan {file_path.name}: {e}")

        return mods


class ParallelAnalyzer:
    """
    Analyzer with parallel processing support.

    Example:
        >>> analyzer = ParallelAnalyzer(workers=4)
        >>> result = analyzer.analyze_directory_parallel(Path("./Mods"))
        >>> print(f"Scanned {len(result.mods)} mods with 4 workers")
    """

    def __init__(
        self,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        workers: Optional[int] = None,
    ):
        """
        Initialize parallel analyzer.

        Args:
            parse_tunings: Whether to parse XML tunings
            parse_scripts: Whether to analyze scripts
            calculate_hashes: Whether to calculate hashes
            workers: Number of workers (default: CPU count - 1)
        """
        self.parse_tunings = parse_tunings
        self.parse_scripts = parse_scripts
        self.calculate_hashes = calculate_hashes

        self.scanner = ParallelScanner(
            parse_tunings=parse_tunings,
            parse_scripts=parse_scripts,
            calculate_hashes=calculate_hashes,
            workers=workers,
        )

    def analyze_directory_parallel(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[set] = None,
    ):
        """
        Analyze directory with parallel processing.

        Args:
            directory: Directory to analyze
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan

        Returns:
            AnalysisResult with mods and conflicts
        """
        from simanalysis.analyzers.mod_analyzer import ModAnalyzer

        # Scan in parallel
        mods = self.scanner.scan_directory_parallel(directory, recursive, extensions)

        # Use regular analyzer for conflict detection
        # (conflict detection is already fast enough, parallelizing it adds complexity)
        analyzer = ModAnalyzer(
            parse_tunings=self.parse_tunings,
            parse_scripts=self.parse_scripts,
            calculate_hashes=self.calculate_hashes,
        )

        return analyzer.analyze_mods(mods)
