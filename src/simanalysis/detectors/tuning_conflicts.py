"""Tuning conflict detector for Sims 4 mods.

Detects when multiple mods modify the same tuning instance IDs,
which can cause unexpected game behavior or crashes.
"""

from collections import defaultdict
from typing import Dict, List, Set

from simanalysis.detectors.base import (
    ConflictDetector,
    ConflictResolutions,
    SeverityRules,
)
from simanalysis.models import ConflictType, Mod, ModConflict


class TuningConflictDetector(ConflictDetector):
    """
    Detects tuning ID conflicts between mods.

    Tuning conflicts occur when multiple mods modify the same tuning
    instance ID. This can cause:
    - Only one mod's changes to apply (last loaded wins)
    - Unpredictable behavior
    - Game crashes if tunings are incompatible

    Example:
        >>> detector = TuningConflictDetector()
        >>> conflicts = detector.detect(mods)
        >>> print(f"Found {len(conflicts)} tuning conflicts")
    """

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Detect tuning conflicts across mods.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        conflicts: List[ModConflict] = []

        # Build index: tuning_id -> list of (mod, tuning_data)
        tuning_index = self._build_tuning_index(mods)

        # Find conflicts (tunings modified by multiple mods)
        for tuning_id, tuning_entries in tuning_index.items():
            if len(tuning_entries) > 1:
                conflict = self._create_tuning_conflict(tuning_id, tuning_entries)
                conflicts.append(conflict)

        return conflicts

    def _build_tuning_index(
        self, mods: List[Mod]
    ) -> Dict[int, List[tuple[Mod, object]]]:
        """
        Build index of tuning ID to mods that modify it.

        Args:
            mods: List of mods to index

        Returns:
            Dictionary mapping tuning_id -> [(mod, tuning_data), ...]
        """
        tuning_index: Dict[int, List[tuple[Mod, object]]] = defaultdict(list)

        for mod in mods:
            for tuning in mod.tunings:
                tuning_index[tuning.instance_id].append((mod, tuning))

        return tuning_index

    def _create_tuning_conflict(
        self, tuning_id: int, tuning_entries: List[tuple[Mod, object]]
    ) -> ModConflict:
        """
        Create conflict object for tuning ID conflict.

        Args:
            tuning_id: Conflicting tuning instance ID
            tuning_entries: List of (mod, tuning_data) tuples

        Returns:
            ModConflict object
        """
        # Extract mod names
        affected_mods = [mod.name for mod, _ in tuning_entries]

        # Get tuning info from first entry
        _, first_tuning = tuning_entries[0]
        tuning_class = getattr(first_tuning, "tuning_class", "unknown")
        tuning_name = getattr(first_tuning, "tuning_name", "unknown")

        # Check if this is a core tuning type
        is_core = SeverityRules.is_core_tuning(tuning_class)

        # Build description
        description = (
            f"Tuning '{tuning_name}' (ID: 0x{tuning_id:08X}, Class: {tuning_class}) "
            f"is modified by {len(affected_mods)} mods. "
            f"Only one mod's changes will apply (last loaded wins)."
        )

        # Get details about modifications
        details = {
            "tuning_id": tuning_id,
            "tuning_id_hex": f"0x{tuning_id:08X}",
            "tuning_name": tuning_name,
            "tuning_class": tuning_class,
            "mod_count": len(affected_mods),
            "is_core_tuning": is_core,
            "modifications": self._get_modification_details(tuning_entries),
        }

        # Create conflict
        return self.create_conflict(
            conflict_type=ConflictType.TUNING_OVERLAP,
            affected_mods=affected_mods,
            description=description,
            identifier=f"{tuning_id:08X}",
            resolution=ConflictResolutions.TUNING_OVERLAP,
            details=details,
            is_core_resource=is_core,
        )

    def _get_modification_details(
        self, tuning_entries: List[tuple[Mod, object]]
    ) -> List[Dict[str, str]]:
        """
        Extract modification details from tuning entries.

        Args:
            tuning_entries: List of (mod, tuning_data) tuples

        Returns:
            List of modification detail dictionaries
        """
        modifications = []

        for mod, tuning in tuning_entries:
            mod_info = {
                "mod_name": mod.name,
                "tuning_module": getattr(tuning, "module", "unknown"),
            }

            # Add attribute count if available
            if hasattr(tuning, "modified_attributes"):
                mod_info["attributes_modified"] = len(tuning.modified_attributes)

            modifications.append(mod_info)

        return modifications

    def get_conflicts_by_class(
        self, conflicts: List[ModConflict], tuning_class: str
    ) -> List[ModConflict]:
        """
        Filter conflicts by tuning class.

        Args:
            conflicts: List of conflicts to filter
            tuning_class: Tuning class to filter by (e.g., "Buff", "Trait")

        Returns:
            Filtered list of conflicts
        """
        return [
            c
            for c in conflicts
            if c.details.get("tuning_class") == tuning_class
        ]

    def get_core_conflicts(self, conflicts: List[ModConflict]) -> List[ModConflict]:
        """
        Get only conflicts affecting core tunings.

        Args:
            conflicts: List of conflicts to filter

        Returns:
            List of core tuning conflicts
        """
        return [
            c for c in conflicts if c.details.get("is_core_tuning", False)
        ]

    def get_conflict_summary(self, conflicts: List[ModConflict]) -> Dict[str, int]:
        """
        Get summary statistics about conflicts.

        Args:
            conflicts: List of conflicts to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_conflicts": len(conflicts),
            "critical_conflicts": sum(
                1 for c in conflicts if c.severity.value == "CRITICAL"
            ),
            "high_conflicts": sum(
                1 for c in conflicts if c.severity.value == "HIGH"
            ),
            "medium_conflicts": sum(
                1 for c in conflicts if c.severity.value == "MEDIUM"
            ),
            "low_conflicts": sum(
                1 for c in conflicts if c.severity.value == "LOW"
            ),
            "core_tuning_conflicts": sum(
                1 for c in conflicts if c.details.get("is_core_tuning", False)
            ),
        }

        # Count by tuning class
        class_counts: Dict[str, int] = defaultdict(int)
        for conflict in conflicts:
            tuning_class = conflict.details.get("tuning_class", "unknown")
            class_counts[tuning_class] += 1

        summary["by_tuning_class"] = dict(class_counts)

        return summary
