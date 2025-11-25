"""Analyzer for Sims 4 Tray items."""

import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from simanalysis import __version__
from simanalysis.scanners.tray_scanner import TrayScanner, TrayItem


class TrayAnalysisResult:
    """Result of a tray analysis."""
    
    def __init__(
        self,
        items: List[TrayItem],
        scan_duration: float,
        directory: str,
    ):
        self.items = items
        self.scan_duration = scan_duration
        self.directory = directory
        self.timestamp = datetime.now()
        self.version = __version__


class TrayAnalyzer:
    """
    Analyzer for Sims 4 Tray files.
    """

    def __init__(self) -> None:
        self.scanner = TrayScanner()

    def analyze_directory(
        self,
        directory: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> TrayAnalysisResult:
        """
        Analyze a tray directory.

        Args:
            directory: Directory to analyze
            progress_callback: Optional callback(current, total, filename)

        Returns:
            TrayAnalysisResult
        """
        start_time = time.time()
        
        items = self.scanner.scan_directory(directory, progress_callback=progress_callback)
        
        # Sort by creation time (newest first)
        items.sort(key=lambda x: x.creation_time or 0, reverse=True)
        
        duration = time.time() - start_time
        
        return TrayAnalysisResult(
            items=items,
            scan_duration=duration,
            directory=str(directory)
        )

    def get_summary(self, result: TrayAnalysisResult) -> Dict:
        """Get summary of tray analysis."""
        total_items = len(result.items)
        households = len([i for i in result.items if i.type == "Household"])
        lots = len([i for i in result.items if "Lot" in i.type or "Room" in i.type])
        
        total_size = sum(i.size for i in result.items)
        
        return {
            "total_items": total_items,
            "households": households,
            "lots_rooms": lots,
            "total_size_mb": total_size / 1024 / 1024,
            "scan_duration": result.scan_duration,
        }
