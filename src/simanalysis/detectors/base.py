"""Base classes and utilities for conflict detection."""

import logging
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from simanalysis.models import Mod, ModConflict, Severity, ConflictType

logger = logging.getLogger(__name__)


class ConflictDetector(ABC):
    """
    Abstract base class for all conflict detectors.

    All conflict detectors should inherit from this class and implement
    the detect() method.

    Example:
        >>> class MyDetector(ConflictDetector):
        ...     def detect(self, mods: List[Mod]) -> List[ModConflict]:
        ...         # Implementation here
        ...         pass
    """

    def __init__(self) -> None:
        """Initialize detector."""
        self.conflicts_found = 0
        self.last_run: datetime | None = None
        logger.debug(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    def detect(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Detect conflicts in a collection of mods.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        pass

    def calculate_severity(
        self,
        conflict_type: ConflictType,
        affected_count: int,
        is_core_resource: bool = False,
    ) -> Severity:
        """
        Calculate conflict severity based on various factors.

        Args:
            conflict_type: Type of conflict
            affected_count: Number of mods affected
            is_core_resource: Whether conflict affects core game resources

        Returns:
            Severity level
        """
        logger.debug(f"Calculating severity: type={conflict_type}, affected={affected_count}, core={is_core_resource}")

        # Core resources are always critical
        if is_core_resource:
            logger.debug("Core resource conflict -> CRITICAL")
            return Severity.CRITICAL

        # Script injections are high risk
        if conflict_type == ConflictType.SCRIPT_INJECTION:
            if affected_count >= 3:
                return Severity.CRITICAL
            elif affected_count >= 2:
                return Severity.HIGH
            else:
                return Severity.MEDIUM

        # Tuning overlaps
        if conflict_type == ConflictType.TUNING_OVERLAP:
            if affected_count >= 3:
                return Severity.HIGH
            elif affected_count >= 2:
                return Severity.MEDIUM
            else:
                return Severity.LOW

        # Resource duplicates
        if conflict_type == ConflictType.RESOURCE_DUPLICATE:
            if affected_count >= 3:
                return Severity.MEDIUM
            else:
                return Severity.LOW

        # Missing dependencies
        if conflict_type == ConflictType.DEPENDENCY_MISSING:
            return Severity.HIGH

        # Version conflicts
        if conflict_type == ConflictType.VERSION_CONFLICT:
            return Severity.MEDIUM

        # Namespace collisions
        if conflict_type == ConflictType.NAMESPACE_COLLISION:
            if affected_count >= 2:
                return Severity.HIGH
            else:
                return Severity.MEDIUM

        # Default to medium
        return Severity.MEDIUM

    def generate_conflict_id(
        self, conflict_type: ConflictType, identifier: str
    ) -> str:
        """
        Generate unique conflict ID.

        Args:
            conflict_type: Type of conflict
            identifier: Unique identifier for this conflict

        Returns:
            Conflict ID string
        """
        type_prefix = conflict_type.value.lower()[:4]
        return f"{type_prefix}_{identifier}"

    def create_conflict(
        self,
        conflict_type: ConflictType,
        affected_mods: List[str],
        description: str,
        identifier: str,
        resolution: str | None = None,
        details: dict | None = None,
        is_core_resource: bool = False,
    ) -> ModConflict:
        """
        Create a ModConflict object with calculated severity.

        Args:
            conflict_type: Type of conflict
            affected_mods: List of affected mod names
            description: Human-readable description
            identifier: Unique identifier for conflict ID
            resolution: Suggested resolution (optional)
            details: Additional details (optional)
            is_core_resource: Whether this affects core resources

        Returns:
            ModConflict object
        """
        severity = self.calculate_severity(
            conflict_type, len(affected_mods), is_core_resource
        )

        conflict_id = self.generate_conflict_id(conflict_type, identifier)

        return ModConflict(
            id=conflict_id,
            severity=severity,
            type=conflict_type,
            affected_mods=affected_mods,
            description=description,
            resolution=resolution,
            details=details or {},
        )

    def run(self, mods: List[Mod]) -> List[ModConflict]:
        """
        Run conflict detection and track metadata.

        Args:
            mods: List of mods to analyze

        Returns:
            List of detected conflicts
        """
        self.last_run = datetime.now()
        conflicts = self.detect(mods)
        self.conflicts_found = len(conflicts)
        return conflicts


class SeverityRules:
    """
    Rules for determining conflict severity.

    This class contains constants and helper methods for severity calculation.
    """

    # Severity thresholds
    CRITICAL_THRESHOLD = 3  # 3+ mods = critical
    HIGH_THRESHOLD = 2  # 2+ mods = high
    MEDIUM_THRESHOLD = 1  # 1+ mods = medium

    # Core resource types (always critical if conflicted)
    CORE_TUNING_TYPES = {
        "Buff",
        "Trait",
        "Skill",
        "Career",
        "Aspiration",
        "Commodity",
    }

    # High-risk script patterns
    HIGH_RISK_HOOKS = {
        "inject_to",
        "wrap_function",
        "override",
    }

    @staticmethod
    def is_core_tuning(tuning_class: str) -> bool:
        """
        Check if tuning class is core/critical.

        Args:
            tuning_class: Tuning class name

        Returns:
            True if core tuning
        """
        return tuning_class in SeverityRules.CORE_TUNING_TYPES

    @staticmethod
    def is_high_risk_hook(hook_name: str) -> bool:
        """
        Check if hook is high-risk.

        Args:
            hook_name: Hook pattern name

        Returns:
            True if high-risk
        """
        return any(
            risk_pattern in hook_name.lower()
            for risk_pattern in SeverityRules.HIGH_RISK_HOOKS
        )


class ConflictResolutions:
    """
    Standard resolution suggestions for common conflicts.

    This class provides template resolutions that detectors can use.
    """

    TUNING_OVERLAP = (
        "Keep only one mod that modifies this tuning, or find a compatibility patch "
        "that merges both modifications."
    )

    RESOURCE_DUPLICATE = (
        "Remove duplicate resources. Keep the mod with the desired version. "
        "Check mod descriptions for which is recommended."
    )

    SCRIPT_INJECTION = (
        "These mods may conflict if they inject into the same game function. "
        "Test carefully and report issues to mod authors."
    )

    DEPENDENCY_MISSING = (
        "Install the required dependency mod. Check mod description for "
        "download links and installation instructions."
    )

    VERSION_CONFLICT = (
        "Update mods to compatible versions. Check mod pages for version "
        "compatibility information."
    )

    NAMESPACE_COLLISION = (
        "These mods use conflicting Python namespaces. Only use one at a time, "
        "or contact mod authors about compatibility."
    )

    @staticmethod
    def get_resolution(conflict_type: ConflictType) -> str:
        """
        Get standard resolution for conflict type.

        Args:
            conflict_type: Type of conflict

        Returns:
            Resolution suggestion
        """
        resolutions = {
            ConflictType.TUNING_OVERLAP: ConflictResolutions.TUNING_OVERLAP,
            ConflictType.RESOURCE_DUPLICATE: ConflictResolutions.RESOURCE_DUPLICATE,
            ConflictType.SCRIPT_INJECTION: ConflictResolutions.SCRIPT_INJECTION,
            ConflictType.DEPENDENCY_MISSING: ConflictResolutions.DEPENDENCY_MISSING,
            ConflictType.VERSION_CONFLICT: ConflictResolutions.VERSION_CONFLICT,
            ConflictType.NAMESPACE_COLLISION: ConflictResolutions.NAMESPACE_COLLISION,
        }

        return resolutions.get(
            conflict_type,
            "Review mod descriptions and test in-game to determine compatibility.",
        )
