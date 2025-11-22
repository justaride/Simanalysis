"""Resource conflict detector for Sims 4 mods.

Detects when multiple mods contain duplicate or conflicting resources,
such as textures, meshes, audio files, or string tables.
"""

import logging
from collections import defaultdict
from typing import Dict, List, Set

from simanalysis.detectors.base import (
    ConflictDetector,
    ConflictResolutions,
    SeverityRules,
)
from simanalysis.models import ConflictType, Mod, ModConflict

logger = logging.getLogger(__name__)


class ResourceConflictDetector(ConflictDetector):
    """
    Detects resource conflicts between mods.

    Resource conflicts occur when multiple mods contain resources with
    the same key (type, group, instance). This can cause:
    - Visual glitches (wrong textures/meshes)
    - Missing content (last loaded wins)
    - Game instability

    Example:
        >>> detector = ResourceConflictDetector()
        >>> conflicts = detector.detect(mods)
        >>> print(f"Found {len(conflicts)} resource conflicts")
    """

    # Critical resource types that affect gameplay
    CRITICAL_RESOURCE_TYPES = {
        0x545503B2,  # SimData (core game data)
        0x0333406C,  # OBJD (object definitions)
        0x034AEECB,  # OBJK (object keys)
        0x00B2D882,  # CAS Part (Create-A-Sim)
    }

    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Detect resource conflicts across mods.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        logger.info(f"Starting resource conflict detection for {len(mods)} mods")
        conflicts: List[ModConflict] = []

        # Build index: resource_key -> list of mods
        resource_index = self._build_resource_index(mods)
        logger.debug(f"Built resource index: {len(resource_index)} unique resource keys")

        # Find conflicts (resources in multiple mods)
        duplicate_count = 0
        for resource_key, mod_list in resource_index.items():
            if len(mod_list) > 1:
                duplicate_count += 1
                logger.warning(f"Resource collision: key={resource_key} in {len(mod_list)} mods")
                conflict = self._create_resource_conflict(resource_key, mod_list)
                conflicts.append(conflict)

        logger.debug(f"Found {duplicate_count} duplicate resources")

        # Also check for hash collisions (same hash, different keys)
        hash_conflicts = self._detect_hash_collisions(mods)
        if hash_conflicts:
            logger.warning(f"Detected {len(hash_conflicts)} hash collision conflicts")
        conflicts.extend(hash_conflicts)

        logger.info(f"Detected {len(conflicts)} resource conflicts total")
        return conflicts

    def _build_resource_index(
        self, mods: List[Mod]
    ) -> Dict[tuple[int, int, int], List[Mod]]:
        """
        Build index of resource keys to mods that contain them.

        Args:
            mods: List of mods to index

        Returns:
            Dictionary mapping resource_key -> [mods]
        """
        resource_index: Dict[tuple[int, int, int], List[Mod]] = defaultdict(list)

        for mod in mods:
            for resource_key in mod.resource_keys:
                resource_index[resource_key].append(mod)

        return resource_index

    def _create_resource_conflict(
        self, resource_key: tuple[int, int, int], mod_list: List[Mod]
    ) -> ModConflict:
        """
        Create conflict object for resource key conflict.

        Args:
            resource_key: Conflicting resource key (type, group, instance)
            mod_list: List of mods containing this resource

        Returns:
            ModConflict object
        """
        # Extract resource type from key tuple
        resource_type, resource_group, resource_instance = resource_key

        # Check if this is a critical resource type
        is_critical = resource_type in self.CRITICAL_RESOURCE_TYPES

        # Build resource key string for display
        key_string = f"0x{resource_type:08X}:0x{resource_group:08X}:0x{resource_instance:016X}"

        # Build description
        resource_type_name = self._get_resource_type_name(resource_type)
        description = (
            f"Resource {key_string} ({resource_type_name}) is present in "
            f"{len(mod_list)} mods. Only one version will be used (last loaded wins)."
        )

        if is_critical:
            description += " This is a critical resource that affects core gameplay."

        # Build details
        details = {
            "resource_key": key_string,
            "resource_type": resource_type,
            "resource_type_hex": f"0x{resource_type:08X}",
            "resource_type_name": resource_type_name,
            "mod_count": len(mod_list),
            "is_critical_resource": is_critical,
            "affected_mod_names": [mod.name for mod in mod_list],
        }

        # Create conflict
        return self.create_conflict(
            conflict_type=ConflictType.RESOURCE_DUPLICATE,
            affected_mods=[mod.name for mod in mod_list],
            description=description,
            identifier=f"{resource_type:08X}_{resource_group:08X}_{resource_instance:016X}",
            resolution=ConflictResolutions.RESOURCE_DUPLICATE,
            details=details,
            is_core_resource=is_critical,
        )

    def _detect_hash_collisions(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Detect hash collisions (different mods with same file hash).

        This can indicate:
        - Duplicate content packaged separately
        - Republished mods under different names
        - Legitimate identical resources

        Args:
            mods: List of mods to analyze

        Returns:
            List of hash collision conflicts
        """
        conflicts: List[ModConflict] = []

        # Build hash index: hash -> list of mods
        hash_index: Dict[str, List[Mod]] = defaultdict(list)
        for mod in mods:
            if mod.hash:  # Only process mods with hashes
                hash_index[mod.hash].append(mod)

        # Find hash collisions (same hash, multiple mods)
        for file_hash, mod_list in hash_index.items():
            if len(mod_list) > 1:
                # Build description
                description = (
                    f"Multiple mods have identical file hashes ({file_hash[:12]}...). "
                    f"This likely indicates duplicate content. Consider keeping only one."
                )

                # Build details
                details = {
                    "file_hash": file_hash,
                    "mod_count": len(mod_list),
                    "affected_mod_names": [mod.name for mod in mod_list],
                    "total_size": sum(mod.size for mod in mod_list),
                }

                # Create conflict
                conflict = self.create_conflict(
                    conflict_type=ConflictType.RESOURCE_DUPLICATE,
                    affected_mods=[mod.name for mod in mod_list],
                    description=description,
                    identifier=f"hash_{file_hash[:16]}",
                    resolution=(
                        "These mods appear to be duplicates. Keep only one to save "
                        "space and avoid potential conflicts."
                    ),
                    details=details,
                    is_core_resource=False,
                )

                conflicts.append(conflict)

        return conflicts

    def _get_resource_type_name(self, resource_type: int) -> str:
        """
        Get human-readable name for resource type.

        Args:
            resource_type: Resource type ID

        Returns:
            Resource type name
        """
        type_names = {
            0x545503B2: "SimData",
            0x0333406C: "Object Definition",
            0x034AEECB: "Object Key",
            0x00B2D882: "CAS Part",
            0x319E4F1D: "String Table",
            0x2E75C764: "Texture",
            0x015A1849: "Geometry",
            0x8EAF13DE: "Animation",
            0x62B1D5C6: "Audio",
        }
        return type_names.get(resource_type, "Unknown")

    def get_critical_conflicts(self, conflicts: List[ModConflict]) -> List[ModConflict]:
        """
        Get only conflicts affecting critical resources.

        Args:
            conflicts: List of conflicts to filter

        Returns:
            List of critical resource conflicts
        """
        return [
            c for c in conflicts if c.details.get("is_critical_resource", False)
        ]

    def get_conflicts_by_type(
        self, conflicts: List[ModConflict], resource_type_name: str
    ) -> List[ModConflict]:
        """
        Filter conflicts by resource type name.

        Args:
            conflicts: List of conflicts to filter
            resource_type_name: Resource type name (e.g., "Texture", "SimData")

        Returns:
            Filtered list of conflicts
        """
        return [
            c
            for c in conflicts
            if c.details.get("resource_type_name") == resource_type_name
        ]

    def get_hash_collision_conflicts(
        self, conflicts: List[ModConflict]
    ) -> List[ModConflict]:
        """
        Get only hash collision conflicts.

        Args:
            conflicts: List of conflicts to filter

        Returns:
            List of hash collision conflicts
        """
        return [c for c in conflicts if "file_hash" in c.details]

    def get_conflict_summary(self, conflicts: List[ModConflict]) -> Dict[str, int]:
        """
        Get summary statistics about resource conflicts.

        Args:
            conflicts: List of conflicts to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            "total_conflicts": len(conflicts),
            "critical_resource_conflicts": sum(
                1 for c in conflicts if c.details.get("is_critical_resource", False)
            ),
            "hash_collision_conflicts": sum(
                1 for c in conflicts if "file_hash" in c.details
            ),
            "resource_key_conflicts": sum(
                1 for c in conflicts if "resource_key" in c.details
            ),
        }

        # Count by resource type
        type_counts: Dict[str, int] = defaultdict(int)
        for conflict in conflicts:
            type_name = conflict.details.get("resource_type_name", "Unknown")
            if type_name != "Unknown":  # Don't count hash collisions
                type_counts[type_name] += 1

        summary["by_resource_type"] = dict(type_counts)

        return summary
