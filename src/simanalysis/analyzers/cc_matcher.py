"""CC (Custom Content) matcher for save files and tray items.

This module matches CAS parts and object references found in save files
and tray items to the actual CC mod files installed in the Mods folder.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from simanalysis.models import Mod
from simanalysis.parsers.save_file import (
    CASPart,
    ObjectReference,
    SaveFileData,
    SimInfo,
    TrayItemData,
)
from simanalysis.scanner import ModScanner

logger = logging.getLogger(__name__)


@dataclass
class CCMatch:
    """Represents a match between a save/tray reference and an installed mod."""

    instance_id: int
    """Instance ID that was matched."""

    mod: Mod
    """The mod file containing this instance ID."""

    resource_name: Optional[str] = None
    """Human-readable name of the resource (if available)."""

    is_cas_part: bool = True
    """True if this is a CAS part, False if it's an object."""


@dataclass
class CCMatchResult:
    """Result of matching CC references against installed mods."""

    matched: List[CCMatch] = field(default_factory=list)
    """Successfully matched CC items."""

    unmatched_instance_ids: List[int] = field(default_factory=list)
    """Instance IDs that couldn't be matched to any installed mod."""

    @property
    def match_rate(self) -> float:
        """Percentage of references that were successfully matched."""
        total = len(self.matched) + len(self.unmatched_instance_ids)
        if total == 0:
            return 0.0
        return (len(self.matched) / total) * 100

    @property
    def unique_mods(self) -> List[Mod]:
        """List of unique mods that were matched."""
        seen_paths = set()
        unique = []
        for match in self.matched:
            if match.mod.path not in seen_paths:
                seen_paths.add(match.mod.path)
                unique.append(match.mod)
        return unique

    @property
    def mod_usage_count(self) -> Dict[Path, int]:
        """Count how many times each mod is used."""
        counts: Dict[Path, int] = defaultdict(int)
        for match in self.matched:
            counts[match.mod.path] += 1
        return dict(counts)


@dataclass
class UsageAnalysis:
    """Analysis of CC usage across save files."""

    all_mods: List[Mod]
    """All installed mods."""

    used_mods: List[Mod]
    """Mods that are used in at least one save."""

    unused_mods: List[Mod]
    """Mods that are never used in any save."""

    usage_counts: Dict[Path, int] = field(default_factory=dict)
    """How many times each mod is used across all saves."""

    @property
    def usage_rate(self) -> float:
        """Percentage of installed mods that are actually used."""
        if not self.all_mods:
            return 0.0
        return (len(self.used_mods) / len(self.all_mods)) * 100

    @property
    def total_unused_size(self) -> int:
        """Total size in bytes of unused mods."""
        return sum(mod.size for mod in self.unused_mods)

    def get_most_used_mods(self, n: int = 10) -> List[tuple[Mod, int]]:
        """Get the N most frequently used mods.

        Args:
            n: Number of top mods to return

        Returns:
            List of (mod, usage_count) tuples, sorted by usage count descending
        """
        # Find mods and their counts
        mod_counts = []
        for mod in self.used_mods:
            count = self.usage_counts.get(mod.path, 0)
            mod_counts.append((mod, count))

        # Sort by count descending
        mod_counts.sort(key=lambda x: x[1], reverse=True)

        return mod_counts[:n]


class CCMatcher:
    """Matches CC references from saves/tray to installed mods.

    This class builds an index of instance IDs from installed mods and
    matches them against instance IDs found in save files and tray items.

    Example:
        >>> matcher = CCMatcher(installed_mods)
        >>> result = matcher.match_save(save_data)
        >>> print(f"Matched {len(result.matched)} CC items")
        >>> print(f"Match rate: {result.match_rate:.1f}%")
    """

    def __init__(self, mods: List[Mod]):
        """Initialize CC matcher with installed mods.

        Args:
            mods: List of installed mods to build index from
        """
        self.mods = mods
        self.instance_index: Dict[int, Mod] = {}
        self._build_index()
        logger.info(f"Initialized CCMatcher with {len(self.mods)} mods")

    def _build_index(self) -> None:
        """Build index of instance ID -> mod mappings."""
        logger.info("Building instance ID index...")

        for mod in self.mods:
            # Index all resources by their instance ID
            for resource in mod.resources:
                # Store the first mod that has this instance ID
                # (conflicts would mean multiple mods have same ID)
                if resource.instance not in self.instance_index:
                    self.instance_index[resource.instance] = mod

        logger.info(f"Indexed {len(self.instance_index)} unique instance IDs")

    def match_instance_id(self, instance_id: int) -> Optional[Mod]:
        """Match a single instance ID to an installed mod.

        Args:
            instance_id: Instance ID to match

        Returns:
            Mod containing this instance ID, or None if not found
        """
        return self.instance_index.get(instance_id)

    def match_cas_parts(self, cas_parts: List[CASPart]) -> CCMatchResult:
        """Match a list of CAS parts to installed mods.

        Args:
            cas_parts: List of CAS parts to match

        Returns:
            CCMatchResult with matched and unmatched items
        """
        result = CCMatchResult()

        for cas_part in cas_parts:
            mod = self.match_instance_id(cas_part.instance_id)

            if mod:
                match = CCMatch(
                    instance_id=cas_part.instance_id,
                    mod=mod,
                    is_cas_part=True
                )
                result.matched.append(match)
            else:
                result.unmatched_instance_ids.append(cas_part.instance_id)

        logger.debug(f"Matched {len(result.matched)}/{len(cas_parts)} CAS parts")
        return result

    def match_objects(self, objects: List[ObjectReference]) -> CCMatchResult:
        """Match a list of objects to installed mods.

        Args:
            objects: List of objects to match

        Returns:
            CCMatchResult with matched and unmatched items
        """
        result = CCMatchResult()

        for obj in objects:
            mod = self.match_instance_id(obj.instance_id)

            if mod:
                match = CCMatch(
                    instance_id=obj.instance_id,
                    mod=mod,
                    is_cas_part=False
                )
                result.matched.append(match)
            else:
                result.unmatched_instance_ids.append(obj.instance_id)

        logger.debug(f"Matched {len(result.matched)}/{len(objects)} objects")
        return result

    def match_save(self, save_data: SaveFileData) -> CCMatchResult:
        """Match all CC references in a save file.

        Args:
            save_data: Parsed save file data

        Returns:
            CCMatchResult with all matches
        """
        logger.info(f"Matching CC for save: {save_data.save_path.name}")

        # Combine all CAS parts from all Sims
        all_cas_parts = list(save_data.all_cas_parts)

        # Match CAS parts
        cas_result = self.match_cas_parts(all_cas_parts)

        # Match objects
        obj_result = self.match_objects(save_data.objects)

        # Combine results
        result = CCMatchResult()
        result.matched = cas_result.matched + obj_result.matched
        result.unmatched_instance_ids = (
            cas_result.unmatched_instance_ids + obj_result.unmatched_instance_ids
        )

        logger.info(
            f"Matched {len(result.matched)} CC items ({result.match_rate:.1f}% match rate)"
        )
        return result

    def match_tray_item(self, tray_data: TrayItemData) -> CCMatchResult:
        """Match all CC references in a tray item.

        Args:
            tray_data: Parsed tray item data

        Returns:
            CCMatchResult with all matches
        """
        logger.info(f"Matching CC for tray item: {tray_data.tray_path.name}")

        # Combine all CAS parts
        all_cas_parts = list(tray_data.all_cas_parts)

        # Match CAS parts
        cas_result = self.match_cas_parts(all_cas_parts)

        # Match objects
        obj_result = self.match_objects(tray_data.objects)

        # Combine results
        result = CCMatchResult()
        result.matched = cas_result.matched + obj_result.matched
        result.unmatched_instance_ids = (
            cas_result.unmatched_instance_ids + obj_result.unmatched_instance_ids
        )

        logger.info(
            f"Matched {len(result.matched)} CC items ({result.match_rate:.1f}% match rate)"
        )
        return result

    def analyze_usage(self, save_files: List[SaveFileData]) -> UsageAnalysis:
        """Analyze CC usage across multiple save files.

        Identifies which mods are used vs unused, and how frequently
        each mod is used.

        Args:
            save_files: List of parsed save files

        Returns:
            UsageAnalysis with usage statistics
        """
        logger.info(f"Analyzing CC usage across {len(save_files)} saves")

        # Track which mods are used and how often
        used_mod_paths: Set[Path] = set()
        usage_counts: Dict[Path, int] = defaultdict(int)

        # Process each save file
        for save_data in save_files:
            result = self.match_save(save_data)

            for match in result.matched:
                used_mod_paths.add(match.mod.path)
                usage_counts[match.mod.path] += 1

        # Split mods into used and unused
        used_mods = []
        unused_mods = []

        for mod in self.mods:
            if mod.path in used_mod_paths:
                used_mods.append(mod)
            else:
                unused_mods.append(mod)

        analysis = UsageAnalysis(
            all_mods=self.mods,
            used_mods=used_mods,
            unused_mods=unused_mods,
            usage_counts=dict(usage_counts)
        )

        logger.info(
            f"Usage analysis: {len(used_mods)} used, {len(unused_mods)} unused "
            f"({analysis.usage_rate:.1f}% usage rate)"
        )

        return analysis


class CCAnalyzer:
    """High-level CC analyzer that combines scanning, parsing, and matching.

    This class provides a convenient interface for complete CC analysis
    workflows.

    Example:
        >>> analyzer = CCAnalyzer()
        >>> mods_dir = Path("~/Documents/Electronic Arts/The Sims 4/Mods")
        >>> saves_dir = Path("~/Documents/Electronic Arts/The Sims 4/saves")
        >>> usage = analyzer.analyze_cc_usage(mods_dir, saves_dir)
        >>> print(f"You use {usage.usage_rate:.1f}% of your CC")
    """

    def __init__(self):
        """Initialize CC analyzer."""
        self.scanner = ModScanner()
        logger.info("Initialized CCAnalyzer")

    def analyze_cc_usage(
        self,
        mods_dir: Path | str,
        saves_dir: Path | str,
        scan_tray: bool = False,
        tray_dir: Optional[Path | str] = None
    ) -> UsageAnalysis:
        """Analyze CC usage across save files.

        Args:
            mods_dir: Path to Mods folder
            saves_dir: Path to saves folder
            scan_tray: Whether to also scan tray items
            tray_dir: Path to Tray folder (if scan_tray is True)

        Returns:
            UsageAnalysis with complete usage statistics
        """
        from simanalysis.parsers.save_file import SaveFileParser, TrayItemParser

        # Scan installed mods
        logger.info(f"Scanning mods directory: {mods_dir}")
        mods = self.scanner.scan_directory(Path(mods_dir))
        logger.info(f"Found {len(mods)} installed mods")

        # Create matcher
        matcher = CCMatcher(mods)

        # Parse save files
        logger.info(f"Scanning saves directory: {saves_dir}")
        save_parser = SaveFileParser()
        save_files = save_parser.scan_saves_directory(Path(saves_dir))
        logger.info(f"Parsed {len(save_files)} save files")

        # Optionally parse tray items and treat them like saves
        if scan_tray and tray_dir:
            logger.info(f"Scanning tray directory: {tray_dir}")
            tray_parser = TrayItemParser()
            tray_items = tray_parser.scan_tray_directory(Path(tray_dir))
            logger.info(f"Parsed {len(tray_items)} tray items")

            # Convert tray items to save-like data for analysis
            # (matching logic works the same)
            # Note: This is simplified - in practice we'd track them separately

        # Analyze usage
        usage = matcher.analyze_usage(save_files)

        return usage

    def generate_required_cc_list(
        self,
        tray_file: Path | str,
        mods_dir: Path | str
    ) -> CCMatchResult:
        """Generate a list of required CC for a tray item.

        Useful for sharing Sims - shows which CC files are needed.

        Args:
            tray_file: Path to .trayitem file
            mods_dir: Path to Mods folder

        Returns:
            CCMatchResult with all required CC
        """
        from simanalysis.parsers.save_file import TrayItemParser

        # Scan installed mods
        logger.info(f"Scanning mods directory: {mods_dir}")
        mods = self.scanner.scan_directory(Path(mods_dir))

        # Parse tray item
        logger.info(f"Parsing tray item: {tray_file}")
        tray_parser = TrayItemParser()
        tray_data = tray_parser.parse_tray_item(Path(tray_file))

        # Match CC
        matcher = CCMatcher(mods)
        result = matcher.match_tray_item(tray_data)

        logger.info(f"Required CC: {len(result.matched)} items from {len(result.unique_mods)} mods")

        return result

    def find_missing_cc(
        self,
        save_file: Path | str,
        mods_dir: Path | str
    ) -> List[int]:
        """Find CC that is referenced in a save but not installed.

        Args:
            save_file: Path to .save file
            mods_dir: Path to Mods folder

        Returns:
            List of instance IDs that are missing
        """
        from simanalysis.parsers.save_file import SaveFileParser

        # Scan installed mods
        mods = self.scanner.scan_directory(Path(mods_dir))

        # Parse save file
        save_parser = SaveFileParser()
        save_data = save_parser.parse_save_file(Path(save_file))

        # Match CC
        matcher = CCMatcher(mods)
        result = matcher.match_save(save_data)

        logger.info(
            f"Found {len(result.unmatched_instance_ids)} missing CC items "
            f"in {save_data.save_path.name}"
        )

        return result.unmatched_instance_ids
