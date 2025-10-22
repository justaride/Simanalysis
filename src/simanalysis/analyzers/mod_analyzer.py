"""Complete mod analysis pipeline integrating scanning and conflict detection."""

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from simanalysis import __version__
from simanalysis.detectors.base import ConflictDetector
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.models import (
    AnalysisMetadata,
    AnalysisResult,
    Mod,
    ModConflict,
    PerformanceMetrics,
    Severity,
)
from simanalysis.scanners import ModScanner


class ModAnalyzer:
    """
    Complete mod analysis pipeline.

    Combines scanning, parsing, and conflict detection into a single
    easy-to-use interface.

    Example:
        >>> analyzer = ModAnalyzer()
        >>> result = analyzer.analyze_directory(Path("/Mods"))
        >>> print(f"Found {len(result.mods)} mods")
        >>> print(f"Detected {len(result.conflicts)} conflicts")
        >>> print(f"Critical issues: {len(result.critical_conflicts)}")
    """

    def __init__(
        self,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
        detectors: Optional[List[ConflictDetector]] = None,
    ) -> None:
        """
        Initialize mod analyzer.

        Args:
            parse_tunings: Whether to parse XML tunings from packages
            parse_scripts: Whether to analyze script files
            calculate_hashes: Whether to calculate file hashes
            detectors: Custom list of conflict detectors (uses defaults if None)
        """
        self.scanner = ModScanner(
            parse_tunings=parse_tunings,
            parse_scripts=parse_scripts,
            calculate_hashes=calculate_hashes,
        )

        # Use default detectors if none provided
        if detectors is None:
            self.detectors = [
                TuningConflictDetector(),
                ResourceConflictDetector(),
            ]
        else:
            self.detectors = detectors

    def analyze_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[Set[str]] = None,
    ) -> AnalysisResult:
        """
        Analyze all mods in a directory.

        Args:
            directory: Directory to analyze
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan (default: .package, .ts4script)

        Returns:
            Complete analysis result with mods and conflicts
        """
        start_time = time.time()

        # Scan directory for mods
        mods = self.scanner.scan_directory(directory, recursive, extensions)

        # Run conflict detection
        conflicts = self.detect_conflicts(mods)

        # Calculate performance metrics
        performance = self._calculate_performance(mods)

        # Build dependency map
        dependencies = self._build_dependencies(mods)

        # Generate recommendations
        recommendations = self.get_recommendations_list(mods, conflicts)

        # Create metadata
        metadata = AnalysisMetadata(
            timestamp=datetime.now(),
            version=__version__,
            mod_directory=str(directory),
            analysis_duration_seconds=time.time() - start_time,
            total_mods_analyzed=len(mods),
        )

        # Create analysis result
        result = AnalysisResult(
            metadata=metadata,
            mods=mods,
            conflicts=conflicts,
            dependencies=dependencies,
            performance=performance,
            recommendations=recommendations,
        )

        return result

    def analyze_mods(self, mods: List[Mod]) -> AnalysisResult:
        """
        Analyze a pre-scanned list of mods.

        Args:
            mods: List of mods to analyze

        Returns:
            Analysis result with conflicts
        """
        start_time = time.time()

        conflicts = self.detect_conflicts(mods)
        performance = self._calculate_performance(mods)
        dependencies = self._build_dependencies(mods)
        recommendations = self.get_recommendations_list(mods, conflicts)

        metadata = AnalysisMetadata(
            timestamp=datetime.now(),
            version=__version__,
            mod_directory="pre-scanned",
            analysis_duration_seconds=time.time() - start_time,
            total_mods_analyzed=len(mods),
        )

        return AnalysisResult(
            metadata=metadata,
            mods=mods,
            conflicts=conflicts,
            dependencies=dependencies,
            performance=performance,
            recommendations=recommendations,
        )

    def detect_conflicts(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Run all conflict detectors on mods.

        Args:
            mods: List of mods to check

        Returns:
            Combined list of all detected conflicts
        """
        all_conflicts: List[ModConflict] = []

        for detector in self.detectors:
            conflicts = detector.run(mods)
            all_conflicts.extend(conflicts)

        return all_conflicts

    def get_summary(self, result: AnalysisResult) -> dict:
        """
        Get summary statistics for analysis result.

        Args:
            result: Analysis result to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_mods": len(result.mods),
            "total_conflicts": len(result.conflicts),
            "critical_conflicts": len([c for c in result.conflicts if c.severity == Severity.CRITICAL]),
            "high_conflicts": len([c for c in result.conflicts if c.severity == Severity.HIGH]),
            "medium_conflicts": len([c for c in result.conflicts if c.severity == Severity.MEDIUM]),
            "low_conflicts": len([c for c in result.conflicts if c.severity == Severity.LOW]),
            "scan_summary": self.scanner.get_scan_summary(),
        }

        # Add detector-specific summaries
        for detector in self.detectors:
            detector_name = detector.__class__.__name__
            summary[f"{detector_name}_conflicts"] = detector.conflicts_found

        return summary

    def _calculate_performance(self, mods: List[Mod]) -> PerformanceMetrics:
        """Calculate performance metrics for mods."""
        total_size = sum(mod.size for mod in mods)
        total_resources = sum(len(mod.resources) for mod in mods)
        total_tunings = sum(len(mod.tunings) for mod in mods)
        total_scripts = sum(len(mod.scripts) for mod in mods)

        # Simple estimates
        estimated_load_time = (total_size / 1024 / 1024) * 0.1  # ~0.1s per MB
        estimated_memory = (total_size / 1024 / 1024) * 1.5  # ~1.5x size in memory
        complexity = min(100.0, (len(mods) / 10.0) + (total_resources / 100.0))

        return PerformanceMetrics(
            total_mods=len(mods),
            total_size_mb=total_size / 1024 / 1024,
            total_resources=total_resources,
            total_tunings=total_tunings,
            total_scripts=total_scripts,
            estimated_load_time_seconds=estimated_load_time,
            estimated_memory_mb=estimated_memory,
            complexity_score=complexity,
        )

    def _build_dependencies(self, mods: List[Mod]) -> Dict[str, List[str]]:
        """Build dependency map from mods."""
        dependencies: Dict[str, List[str]] = {}

        for mod in mods:
            if mod.requires:
                dependencies[mod.name] = mod.requires

        return dependencies

    def get_recommendations_list(self, mods: List[Mod], conflicts: List[ModConflict]) -> List[str]:
        """Generate recommendations for a list of mods and conflicts."""
        # Create a minimal AnalysisResult-like object for compatibility
        class TempResult:
            def __init__(self):
                self.mods = mods
                self.conflicts = conflicts
                self.critical_conflicts = [c for c in conflicts if c.severity == Severity.CRITICAL]

            def get_conflicts_by_severity(self, severity):
                return [c for c in conflicts if c.severity == severity]

        return self.get_recommendations(TempResult())

    def get_recommendations(self, result: AnalysisResult) -> List[str]:
        """
        Generate recommendations based on analysis result.

        Args:
            result: Analysis result

        Returns:
            List of recommendation strings
        """
        recommendations: List[str] = []

        # Critical conflicts
        critical = result.critical_conflicts
        if len(critical) > 0:
            recommendations.append(
                f"⚠️  CRITICAL: {len(critical)} critical conflicts detected. "
                f"These may cause game crashes or severe instability."
            )

            # List critical conflicts
            for conflict in critical[:5]:  # Show first 5
                recommendations.append(f"  - {conflict.description[:100]}...")

            if len(critical) > 5:
                recommendations.append(f"  ... and {len(critical) - 5} more")

        # High severity
        high = [c for c in result.conflicts if c.severity == Severity.HIGH]
        if len(high) > 0:
            recommendations.append(
                f"⚠️  HIGH: {len(high)} high-severity conflicts detected. "
                f"These may cause significant issues."
            )

        # Duplicate files (hash collisions)
        hash_conflicts = [
            c for c in result.conflicts if "file_hash" in c.details
        ]
        if len(hash_conflicts) > 0:
            recommendations.append(
                f"💡 TIP: {len(hash_conflicts)} duplicate mods found. "
                f"Remove duplicates to save space and reduce conflicts."
            )

        # No conflicts
        if len(result.conflicts) == 0:
            recommendations.append(
                "✅ No conflicts detected! Your mod setup looks good."
            )

        # General recommendations
        if len(result.mods) > 100:
            recommendations.append(
                f"💡 TIP: You have {len(result.mods)} mods installed. "
                f"Consider organizing them into subfolders for easier management."
            )

        return recommendations

    def export_report(
        self, result: AnalysisResult, output_path: Path, format: str = "txt"
    ) -> None:
        """
        Export analysis report to file.

        Args:
            result: Analysis result to export
            output_path: Path to output file
            format: Report format (txt, json, html)
        """
        if format == "txt":
            self._export_text_report(result, output_path)
        elif format == "json":
            self._export_json_report(result, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _export_text_report(self, result: AnalysisResult, output_path: Path) -> None:
        """Export plain text report."""
        lines: List[str] = []

        # Header
        lines.append("=" * 80)
        lines.append("SIMS 4 MOD ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary
        summary = self.get_summary(result)
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Mods: {summary['total_mods']}")
        lines.append(f"Total Conflicts: {summary['total_conflicts']}")
        lines.append(f"  - Critical: {summary['critical_conflicts']}")
        lines.append(f"  - High: {summary['high_conflicts']}")
        lines.append(f"  - Medium: {summary['medium_conflicts']}")
        lines.append(f"  - Low: {summary['low_conflicts']}")
        lines.append("")

        # Recommendations
        recommendations = self.get_recommendations(result)
        if recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("-" * 80)
            for rec in recommendations:
                lines.append(rec)
            lines.append("")

        # Conflicts
        if result.conflicts:
            lines.append("CONFLICTS")
            lines.append("-" * 80)

            # Group by severity
            for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                conflicts = [c for c in result.conflicts if c.severity == severity]
                if conflicts:
                    lines.append(f"\n{severity.value} SEVERITY ({len(conflicts)}):")
                    lines.append("-" * 40)

                    for conflict in conflicts:
                        lines.append(f"\n  ID: {conflict.id}")
                        lines.append(f"  Type: {conflict.type.value}")
                        lines.append(f"  Description: {conflict.description}")
                        lines.append(f"  Affected Mods: {', '.join(conflict.affected_mods)}")
                        if conflict.resolution:
                            lines.append(f"  Resolution: {conflict.resolution}")

        # Write file
        output_path.write_text("\n".join(lines))

    def _export_json_report(self, result: AnalysisResult, output_path: Path) -> None:
        """Export JSON report."""
        import json

        # Build JSON structure
        report = {
            "summary": self.get_summary(result),
            "recommendations": self.get_recommendations(result),
            "mods": [
                {
                    "name": mod.name,
                    "path": str(mod.path),
                    "type": mod.type.value,
                    "size": mod.size,
                    "hash": mod.hash,
                    "resource_count": len(mod.resources),
                    "tuning_count": len(mod.tunings),
                    "script_count": len(mod.scripts),
                }
                for mod in result.mods
            ],
            "conflicts": [
                {
                    "id": conflict.id,
                    "severity": conflict.severity.value,
                    "type": conflict.type.value,
                    "description": conflict.description,
                    "affected_mods": conflict.affected_mods,
                    "resolution": conflict.resolution,
                    "details": conflict.details,
                }
                for conflict in result.conflicts
            ],
        }

        # Write file
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
