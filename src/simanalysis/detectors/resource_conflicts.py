"""Resource conflict detector for Sims 4 mods.

Detects when multiple mods contain duplicate or conflicting resources,
such as textures, meshes, audio files, or string tables.
"""

from collections import defaultdict
from typing import Any, ClassVar, Optional

from simanalysis.detectors.base import (
    ConflictDetector,
    ConflictResolutions,
)
from simanalysis.formats.types import CASP, COBJ, OBJD, SIMDATA, TuningResourceType, type_name
from simanalysis.load_order import LoadOrderPlan
from simanalysis.models import ConflictType, Mod, ModConflict


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
    CRITICAL_RESOURCE_TYPES: ClassVar[set[int]] = {
        int(SIMDATA),
        int(OBJD),
        int(CASP),
        int(COBJ),
    }

    def __init__(self, load_order: Optional[LoadOrderPlan] = None) -> None:
        """Initialize detector with optional package load-order context."""
        self.load_order = load_order

    def detect(self, mods: list[Mod]) -> list[ModConflict]:
        """
        Detect resource conflicts across mods.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        conflicts: list[ModConflict] = []

        # Build index: resource_key -> list of mods
        resource_index = self._build_resource_index(mods)

        # Find conflicts (resources in multiple mods)
        for resource_key, mod_list in resource_index.items():
            if len(mod_list) > 1:
                conflict = self._create_resource_conflict(resource_key, mod_list)
                conflicts.append(conflict)

        # Also check for hash collisions (same hash, different keys)
        hash_conflicts = self._detect_hash_collisions(mods)
        conflicts.extend(hash_conflicts)

        return conflicts

    def _build_resource_index(self, mods: list[Mod]) -> dict[tuple[int, int, int], list[Mod]]:
        """
        Build index of resource keys to mods that contain them.

        Args:
            mods: List of mods to index

        Returns:
            Dictionary mapping resource_key -> [mods]
        """
        resource_index: dict[tuple[int, int, int], list[Mod]] = defaultdict(list)

        for mod in mods:
            for resource_key in mod.resource_keys:
                resource_index[resource_key].append(mod)

        return resource_index

    def _create_resource_conflict(
        self, resource_key: tuple[int, int, int], mod_list: list[Mod]
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
        if self.load_order is not None:
            load_order_details = self._load_order_details(mod_list)
            details["load_order"] = load_order_details
            if load_order_details["winner_mod_name"]:
                description += (
                    f" Simulated winner: {load_order_details['winner_mod_name']} "
                    f"({load_order_details['confidence']} confidence)."
                )
        self._add_v2_details(details, resource_type, mod_list)

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

    def _add_v2_details(
        self,
        details: dict[str, Any],
        resource_type: int,
        mod_list: list[Mod],
    ) -> None:
        """Add v2 conflict explanation metadata without changing legacy fields."""
        conflict_kind = self._conflict_kind(resource_type, mod_list)
        details["conflict_kind"] = conflict_kind
        details["review_status"] = self._review_status(conflict_kind, details)
        details["recommendation"] = self._recommendation(conflict_kind, details)

    def _conflict_kind(self, resource_type: int, mod_list: list[Mod]) -> str:
        """Return the calibrated conflict kind for a resource overlap."""
        if self._looks_like_default_replacement(mod_list):
            return "default_replacement_ambiguity"
        if resource_type in {
            int(TuningResourceType.PieMenuCategory),
            int(TuningResourceType.UserInterfaceInfo),
        }:
            return "ui_conflict"
        return "likely_override"

    def _review_status(self, conflict_kind: str, details: dict[str, Any]) -> str:
        """Return whether this needs review or may be intentional."""
        load_order = details.get("load_order", {})
        if isinstance(load_order, dict) and load_order.get("winner"):
            return "intentional_override_possible"
        if conflict_kind == "default_replacement_ambiguity":
            return "intentional_override_possible"
        return "needs_review"

    def _recommendation(self, conflict_kind: str, details: dict[str, Any]) -> dict[str, Any]:
        """Return profile-aware review guidance for the conflict kind."""
        load_order = details.get("load_order", {})
        winner_mod_name = None
        confidence = "medium"
        if isinstance(load_order, dict):
            winner_mod_name = load_order.get("winner_mod_name")
            confidence = str(load_order.get("confidence") or confidence)

        if conflict_kind == "default_replacement_ambiguity":
            return {
                "action": "verify_default_replacement",
                "confidence": confidence,
                "profile_aware": True,
                "winner_mod_name": winner_mod_name,
                "message": (
                    "Default replacement or override-style conflicts can be intentional "
                    "and are not automatically an error; verify the intended winner for "
                    "the active profile."
                ),
            }
        if conflict_kind == "ui_conflict":
            return {
                "action": "review_ui_mod_compatibility",
                "confidence": confidence,
                "profile_aware": True,
                "winner_mod_name": winner_mod_name,
                "message": (
                    "UI resource overlaps should be reviewed against the active profile "
                    "and current patch before assuming compatibility."
                ),
            }
        if winner_mod_name:
            return {
                "action": "verify_intentional_override",
                "confidence": confidence,
                "profile_aware": True,
                "winner_mod_name": winner_mod_name,
                "message": (
                    "A load-order winner is simulated; verify this override is intended "
                    "for the active profile before changing files."
                ),
            }
        return {
            "action": "review_load_order",
            "confidence": confidence,
            "profile_aware": True,
            "message": (
                "Review the active profile and load order; one resource definition will "
                "win, but this overlap may be intentional."
            ),
        }

    def _looks_like_default_replacement(self, mod_list: list[Mod]) -> bool:
        """Return whether filenames suggest default replacement semantics."""
        haystack = " ".join(
            f"{mod.name} {mod.path.as_posix()}".casefold().replace("\\", "/") for mod in mod_list
        )
        return "default replacement" in haystack or "default_replacement" in haystack

    def _load_order_details(self, mod_list: list[Mod]) -> dict[str, Any]:
        """Build JSON-safe load-order details for a resource conflict."""
        verdict = self.load_order.explain_winner(mod_list) if self.load_order else None
        if verdict is None:
            return {}

        return {
            "confidence": verdict.confidence,
            "winner": verdict.winner_relative_path,
            "winner_mod_name": verdict.winner_mod_name,
            "reason": verdict.reason,
            "unmatched": list(verdict.unmatched_relative_paths),
            "entries": [
                {
                    "mod_name": participant.mod_name,
                    "relative_path": participant.relative_path,
                    "load_index": participant.load_index,
                    "priority": participant.priority,
                    "rule_pattern": participant.rule_pattern,
                }
                for participant in verdict.participants
            ],
        }

    def _detect_hash_collisions(self, mods: list[Mod]) -> list[ModConflict]:
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
        conflicts: list[ModConflict] = []

        # Build hash index: hash -> list of mods
        hash_index: dict[str, list[Mod]] = defaultdict(list)
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
                    "conflict_kind": "exact_duplicate",
                    "review_status": "duplicate_file",
                    "recommendation": {
                        "action": "keep_one_copy",
                        "confidence": "direct",
                        "profile_aware": True,
                        "message": (
                            "These files have identical hashes; keep one copy per active "
                            "profile unless duplicates are intentionally staged."
                        ),
                    },
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
        return type_name(resource_type)

    def get_critical_conflicts(self, conflicts: list[ModConflict]) -> list[ModConflict]:
        """
        Get only conflicts affecting critical resources.

        Args:
            conflicts: List of conflicts to filter

        Returns:
            List of critical resource conflicts
        """
        return [c for c in conflicts if c.details.get("is_critical_resource", False)]

    def get_conflicts_by_type(
        self, conflicts: list[ModConflict], resource_type_name: str
    ) -> list[ModConflict]:
        """
        Filter conflicts by resource type name.

        Args:
            conflicts: List of conflicts to filter
            resource_type_name: Resource type name (e.g., "Texture", "SimData")

        Returns:
            Filtered list of conflicts
        """
        return [c for c in conflicts if c.details.get("resource_type_name") == resource_type_name]

    def get_hash_collision_conflicts(self, conflicts: list[ModConflict]) -> list[ModConflict]:
        """
        Get only hash collision conflicts.

        Args:
            conflicts: List of conflicts to filter

        Returns:
            List of hash collision conflicts
        """
        return [c for c in conflicts if "file_hash" in c.details]

    def get_conflict_summary(self, conflicts: list[ModConflict]) -> dict[str, Any]:
        """
        Get summary statistics about resource conflicts.

        Args:
            conflicts: List of conflicts to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary: dict[str, Any] = {
            "total_conflicts": len(conflicts),
            "critical_resource_conflicts": sum(
                1 for c in conflicts if c.details.get("is_critical_resource", False)
            ),
            "hash_collision_conflicts": sum(1 for c in conflicts if "file_hash" in c.details),
            "resource_key_conflicts": sum(1 for c in conflicts if "resource_key" in c.details),
        }

        # Count by resource type
        type_counts: dict[str, int] = defaultdict(int)
        for conflict in conflicts:
            type_name = conflict.details.get("resource_type_name", "Unknown")
            if type_name != "Unknown":  # Don't count hash collisions
                type_counts[type_name] += 1

        summary["by_resource_type"] = dict(type_counts)

        return summary
