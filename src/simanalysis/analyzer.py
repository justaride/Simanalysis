"""
Simanalysis - Core Mod Analysis Engine
Author: Derrick (AI-Powered)
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .dbpf_parser import DBPFPackage, DBPFParsingError, DBPFResourceEntry, load_package
from .script_metadata import ScriptModMetadata, analyze_script_mod

DLC_CODE_MAP = {
    "EP01": "Get to Work",
    "EP02": "Get Together",
    "EP03": "City Living",
    "EP04": "Cats & Dogs",
    "EP05": "Seasons",
    "EP06": "Get Famous",
    "EP07": "Island Living",
    "EP08": "Discover University",
    "EP09": "Eco Lifestyle",
    "EP10": "Snowy Escape",
    "EP11": "Cottage Living",
    "EP12": "High School Years",
    "EP13": "Growing Together",
    "GP01": "Outdoor Retreat",
    "GP02": "Spa Day",
    "GP03": "Dine Out",
    "GP04": "Vampires",
    "GP05": "Parenthood",
    "GP06": "Jungle Adventure",
    "GP07": "StrangerVille",
    "GP08": "Realm of Magic",
    "GP09": "Star Wars: Journey to Batuu",
    "GP10": "Dream Home Decorator",
    "GP11": "My Wedding Stories",
    "GP12": "Werewolves",
    "SP01": "Luxury Party",
    "SP02": "Perfect Patio",
    "SP03": "Cool Kitchen",
    "SP04": "Spooky",
    "SP05": "Movie Hangout",
    "SP06": "Romantic Garden",
    "SP07": "Kids Room",
    "SP08": "Backyard",
    "SP09": "Vintage Glamour",
    "SP10": "Bowling Night",
    "SP11": "Fitness",
    "SP12": "Toddler",
    "SP13": "Laundry Day",
    "SP14": "My First Pet",
    "SP15": "Moschino",
    "SP16": "Tiny Living",
    "SP17": "Nifty Knitting",
    "SP18": "Paranormal",
}

DLC_PATTERN = re.compile(r"(EP\d{2}|GP\d{2}|SP\d{2})", re.IGNORECASE)


@dataclass
class ModConflict:
    """Represents a detected mod conflict"""

    severity: str
    type: str
    affected_mods: List[str]
    description: str
    resolution: Optional[str] = None


@dataclass
class AnalysisResult:
    """Analysis results for a mod collection"""

    total_mods: int
    conflicts: List[ModConflict]
    dependencies: Dict[str, List[str]]
    performance_score: float
    recommendations: List[str]
    packages: List[DBPFPackage] = field(default_factory=list)
    scripts: List[ScriptModMetadata] = field(default_factory=list)
    package_errors: List[Tuple[Path, str]] = field(default_factory=list)
    script_errors: List[Tuple[Path, str]] = field(default_factory=list)


class ModAnalyzer:
    """
    Core analyzer for Sims 4 mods
    AI-enhanced conflict detection and performance analysis
    """

    def __init__(self, mod_path: Optional[str] = None):
        self.mod_path: Optional[Path] = Path(mod_path) if mod_path else None
        self.conflicts: List[ModConflict] = []
        self.dependencies: Dict[str, List[str]] = {}

    def analyze_directory(self, path: str) -> AnalysisResult:
        """
        Analyze all mods in a directory

        Args:
            path: Directory containing Sims 4 mods

        Returns:
            AnalysisResult with complete analysis
        """
        mod_dir = Path(path)

        if not mod_dir.exists():
            raise FileNotFoundError(f"Mod directory not found: {path}")

        # Find all package and script files
        package_files = list(mod_dir.glob("**/*.package"))
        script_files = list(mod_dir.glob("**/*.ts4script"))

        parsed_packages, package_errors = self._load_packages(package_files)
        script_metadata, script_errors = self._load_scripts(script_files)

        total_mods = len(package_files) + len(script_files)

        # Analyze conflicts
        conflicts = self._detect_conflicts(parsed_packages, script_metadata)
        conflicts.extend(
            ModConflict(
                severity="CRITICAL",
                type="PACKAGE_PARSE_ERROR",
                affected_mods=[path.name],
                description=str(error),
            )
            for path, error in package_errors
        )
        conflicts.extend(
            ModConflict(
                severity="CRITICAL",
                type="SCRIPT_PARSE_ERROR",
                affected_mods=[path.name],
                description=str(error),
            )
            for path, error in script_errors
        )
        self.conflicts = conflicts

        # Map dependencies
        dependencies = self._map_dependencies(parsed_packages, script_metadata)
        self.dependencies = dependencies

        # Calculate performance score
        performance = self._calculate_performance(total_mods, conflicts)

        # Generate recommendations
        recommendations = self._generate_recommendations(conflicts, dependencies)

        return AnalysisResult(
            total_mods=total_mods,
            conflicts=conflicts,
            dependencies=dependencies,
            performance_score=performance,
            recommendations=recommendations,
            packages=parsed_packages,
            scripts=script_metadata,
            package_errors=package_errors,
            script_errors=script_errors,
        )

    def _load_packages(
        self, package_files: List[Path]
    ) -> Tuple[List[DBPFPackage], List[Tuple[Path, str]]]:
        packages: List[DBPFPackage] = []
        errors: List[Tuple[Path, str]] = []
        for path in package_files:
            try:
                packages.append(load_package(path))
            except DBPFParsingError as exc:
                errors.append((path, str(exc)))
        return packages, errors

    def _load_scripts(
        self, script_files: List[Path]
    ) -> Tuple[List[ScriptModMetadata], List[Tuple[Path, str]]]:
        scripts: List[ScriptModMetadata] = []
        errors: List[Tuple[Path, str]] = []
        for path in script_files:
            try:
                scripts.append(analyze_script_mod(path))
            except Exception as exc:  # pragma: no cover - best effort parsing
                errors.append((path, str(exc)))
        return scripts, errors

    def _detect_conflicts(
        self, packages: List[DBPFPackage], script_metadata: List[ScriptModMetadata]
    ) -> List[ModConflict]:
        """Detect conflicts between mods"""
        conflicts: List[ModConflict] = []

        resource_index: Dict[tuple[int, int, int], List[DBPFResourceEntry]] = defaultdict(list)
        resource_sources: Dict[tuple[int, int, int], List[str]] = defaultdict(list)
        for package in packages:
            for resource in package.resources:
                key = (resource.type_id, resource.group_id, resource.instance_id)
                resource_index[key].append(resource)
                resource_sources[key].append(package.path.name)

        for key, mods in resource_sources.items():
            if len(mods) <= 1:
                continue
            type_id, group_id, instance_id = key
            resource = resource_index[key][0]
            description = (
                "Duplicate resource {type_name} (Type 0x{type_id:08X}, Group 0x{group_id:08X}, "
                "Instance 0x{instance_id:016X}) detected in {mods}."
            ).format(
                type_name=resource.type_name,
                type_id=type_id,
                group_id=group_id,
                instance_id=instance_id,
                mods=", ".join(sorted(set(mods))),
            )
            conflicts.append(
                ModConflict(
                    severity="HIGH",
                    type="RESOURCE_DUPLICATE",
                    affected_mods=sorted(set(mods)),
                    description=description,
                    resolution="Review load order or merge the conflicting packages.",
                )
            )

        module_index: Dict[str, List[str]] = defaultdict(list)
        for metadata in script_metadata:
            for module in metadata.module_names:
                module_index[module].append(metadata.path.name)

        for module, mods in module_index.items():
            unique_mods = sorted(set(mods))
            if len(unique_mods) <= 1 or module == "":
                continue
            conflicts.append(
                ModConflict(
                    severity="CRITICAL",
                    type="SCRIPT_MODULE_COLLISION",
                    affected_mods=unique_mods,
                    description=(
                        "Multiple script mods provide the module "
                        f"'{module}', which can lead to injection conflicts."
                    ),
                    resolution=(
                        "Load only one version of the module or verify injector compatibility."
                    ),
                )
            )

        return conflicts

    def _map_dependencies(
        self, packages: List[DBPFPackage], script_metadata: List[ScriptModMetadata]
    ) -> Dict[str, List[str]]:
        """Map mod dependencies derived from package metadata and script analysis."""

        dependencies: Dict[str, List[str]] = {}

        for package in packages:
            inferred = sorted(set(self._infer_dlc_requirements(package.path)))
            if inferred:
                dependencies[package.path.name] = inferred

        for metadata in script_metadata:
            inferred = sorted(metadata.detected_frameworks)
            if inferred:
                dependencies.setdefault(metadata.path.name, []).extend(inferred)
            if metadata.python_versions:
                dependencies.setdefault(metadata.path.name, []).append(
                    f"python_{'/'.join(sorted(metadata.python_versions))}"
                )

        # Deduplicate dependency entries
        for key, values in dependencies.items():
            deduped = []
            seen = set()
            for value in values:
                if value not in seen:
                    deduped.append(value)
                    seen.add(value)
            dependencies[key] = deduped

        return dependencies

    def _infer_dlc_requirements(self, path: Path) -> List[str]:
        matches = DLC_PATTERN.findall(path.name)
        resolved = []
        for match in matches:
            code = match.upper()
            friendly = DLC_CODE_MAP.get(code)
            if friendly:
                resolved.append(friendly)
            else:
                resolved.append(code)
        return resolved

    def _calculate_performance(self, mod_count: int, conflicts: List[ModConflict]) -> float:
        """Calculate performance impact score (0-100)"""
        base_score = 100.0

        # Reduce score based on mod count
        base_score -= mod_count * 0.5

        # Reduce based on conflicts
        for conflict in conflicts:
            if conflict.severity == "CRITICAL":
                base_score -= 10
            elif conflict.severity == "HIGH":
                base_score -= 5
            elif conflict.severity == "MEDIUM":
                base_score -= 2

        return max(0.0, min(100.0, base_score))

    def _generate_recommendations(
        self, conflicts: List[ModConflict], dependencies: Dict[str, List[str]]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        if len(conflicts) > 10:
            recommendations.append("Consider reducing mod count to improve stability")

        critical_conflicts = [c for c in conflicts if c.severity == "CRITICAL"]
        if critical_conflicts:
            recommendations.append(
                f"Resolve {len(critical_conflicts)} critical conflicts immediately"
            )

        duplicate_resources = [c for c in conflicts if c.type == "RESOURCE_DUPLICATE"]
        if duplicate_resources:
            recommendations.append(
                "Review duplicate tuning resources and consolidate packages to prevent overrides."
            )

        for mod_name, deps in dependencies.items():
            if any(dep.startswith("python_") for dep in deps):
                recommendations.append(
                    "Verify that {mod_name} targets the latest supported Python runtime "
                    "before the next game update.".format(mod_name=mod_name)
                )
            if "xml_injector" in deps:
                recommendations.append(
                    "Ensure XML Injector is installed and up to date for mods that depend on it."
                )
                break

        return recommendations


if __name__ == "__main__":
    # Example usage
    analyzer = ModAnalyzer()
    print("Simanalysis - Derrick is ready to analyze your mods!")
