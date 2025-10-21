"""Core analysis primitives for the Simanalysis toolkit."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModConflict:
    """Represents a detected mod conflict."""

    severity: str
    type: str
    affected_mods: list[str]
    description: str
    resolution: str | None = None


@dataclass
class AnalysisResult:
    """Analysis results for a mod collection."""

    total_mods: int
    conflicts: list[ModConflict]
    dependencies: dict[str, list[str]]
    performance_score: float
    recommendations: list[str]

    def has_conflicts(self) -> bool:
        """Return ``True`` if any conflicts were detected."""

        return bool(self.conflicts)


class ModAnalyzer:
    """Analyze Sims 4 mod directories.

    The current implementation focuses on basic directory statistics while the
    conflict detection and dependency mapping logic are placeholders for future
    work.
    """

    def __init__(self, mod_path: Path | None = None) -> None:
        self.mod_path = Path(mod_path) if mod_path is not None else None

    def analyze(self) -> AnalysisResult:
        """Analyze the directory supplied at construction time."""

        if self.mod_path is None:
            raise ValueError("A mod directory was not provided.")
        return self.analyze_directory(self.mod_path)

    def analyze_directory(self, path: Path | str) -> AnalysisResult:
        """Analyze all mods in ``path``.

        Parameters
        ----------
        path:
            Directory containing Sims 4 mods.
        """

        mod_dir = Path(path)
        if not mod_dir.exists():
            raise FileNotFoundError(f"Mod directory not found: {path}")
        if not mod_dir.is_dir():
            raise NotADirectoryError(f"Expected a directory: {path}")

        package_files = list(self._iter_mod_files(mod_dir, "*.package"))
        script_files = list(self._iter_mod_files(mod_dir, "*.ts4script"))

        total_mods = len(package_files) + len(script_files)

        conflicts = self._detect_conflicts(package_files, script_files)
        dependencies = self._map_dependencies(package_files)
        performance = self._calculate_performance(total_mods, conflicts)
        recommendations = self._generate_recommendations(conflicts)

        return AnalysisResult(
            total_mods=total_mods,
            conflicts=conflicts,
            dependencies=dependencies,
            performance_score=performance,
            recommendations=recommendations,
        )

    @staticmethod
    def _iter_mod_files(directory: Path, pattern: str) -> Iterable[Path]:
        yield from directory.glob(f"**/{pattern}")

    def _detect_conflicts(
        self, packages: Iterable[Path], scripts: Iterable[Path]
    ) -> list[ModConflict]:
        """Detect conflicts between mods.

        The function currently returns an empty list and acts as a placeholder
        for future conflict detection work.
        """

        _ = packages, scripts
        return []

    def _map_dependencies(self, packages: Iterable[Path]) -> dict[str, list[str]]:
        """Map mod dependencies.

        The function currently returns an empty mapping and acts as a placeholder
        for future dependency mapping features.
        """

        _ = packages
        return {}

    def _calculate_performance(
        self, mod_count: int, conflicts: Iterable[ModConflict]
    ) -> float:
        """Calculate performance impact score (0-100)."""

        base_score = 100.0 - (mod_count * 0.5)
        for conflict in conflicts:
            if conflict.severity == "CRITICAL":
                base_score -= 10
            elif conflict.severity == "HIGH":
                base_score -= 5
            elif conflict.severity == "MEDIUM":
                base_score -= 2

        return max(0.0, min(100.0, base_score))

    def _generate_recommendations(
        self, conflicts: Iterable[ModConflict]
    ) -> list[str]:
        """Generate actionable recommendations for the user."""

        conflicts_list = list(conflicts)
        recommendations: list[str] = []

        if len(conflicts_list) > 10:
            recommendations.append(
                "Consider reducing mod count to improve stability."
            )

        critical_conflicts = [c for c in conflicts_list if c.severity == "CRITICAL"]
        if critical_conflicts:
            recommendations.append(
                f"Resolve {len(critical_conflicts)} critical conflicts immediately."
            )

        return recommendations
