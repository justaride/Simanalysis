"""Tests for base detector framework."""

from datetime import datetime
from pathlib import Path

import pytest

from simanalysis.detectors.base import (
    ConflictDetector,
    ConflictResolutions,
    SeverityRules,
)
from simanalysis.models import (
    ConflictType,
    Mod,
    ModConflict,
    ModType,
    Severity,
)


class TestConflictDetector:
    """Tests for ConflictDetector base class."""

    class SimpleDetector(ConflictDetector):
        """Simple detector for testing."""

        def detect(self, mods):
            """Return empty list."""
            return []

    class CountingDetector(ConflictDetector):
        """Detector that creates test conflicts."""

        def detect(self, mods):
            """Create test conflicts."""
            conflicts = []
            if len(mods) >= 2:
                conflicts.append(
                    self.create_conflict(
                        conflict_type=ConflictType.TUNING_OVERLAP,
                        affected_mods=[mods[0].name, mods[1].name],
                        description="Test conflict",
                        identifier="test_001",
                    )
                )
            return conflicts

    @pytest.fixture
    def detector(self):
        """Create a simple detector."""
        return self.SimpleDetector()

    @pytest.fixture
    def counting_detector(self):
        """Create a counting detector."""
        return self.CountingDetector()

    @pytest.fixture
    def sample_mods(self):
        """Create sample mods for testing."""
        return [
            Mod(
                name="mod_a.package",
                path=Path("/mods/mod_a.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash="hash_a",
            ),
            Mod(
                name="mod_b.package",
                path=Path("/mods/mod_b.package"),
                type=ModType.PACKAGE,
                size=2000,
                hash="hash_b",
            ),
            Mod(
                name="mod_c.package",
                path=Path("/mods/mod_c.package"),
                type=ModType.PACKAGE,
                size=3000,
                hash="hash_c",
            ),
        ]

    def test_detector_initialization(self, detector):
        """Test detector initializes correctly."""
        assert detector.conflicts_found == 0
        assert detector.last_run is None

    def test_calculate_severity_core_resource(self, detector):
        """Test that core resources always get CRITICAL severity."""
        severity = detector.calculate_severity(
            ConflictType.TUNING_OVERLAP, affected_count=1, is_core_resource=True
        )

        assert severity == Severity.CRITICAL

    def test_calculate_severity_script_injection(self, detector):
        """Test severity calculation for script injections."""
        # 3+ affected = CRITICAL
        severity = detector.calculate_severity(
            ConflictType.SCRIPT_INJECTION, affected_count=3
        )
        assert severity == Severity.CRITICAL

        # 2 affected = HIGH
        severity = detector.calculate_severity(
            ConflictType.SCRIPT_INJECTION, affected_count=2
        )
        assert severity == Severity.HIGH

        # 1 affected = MEDIUM
        severity = detector.calculate_severity(
            ConflictType.SCRIPT_INJECTION, affected_count=1
        )
        assert severity == Severity.MEDIUM

    def test_calculate_severity_tuning_overlap(self, detector):
        """Test severity calculation for tuning overlaps."""
        # 3+ affected = HIGH
        severity = detector.calculate_severity(
            ConflictType.TUNING_OVERLAP, affected_count=3
        )
        assert severity == Severity.HIGH

        # 2 affected = MEDIUM
        severity = detector.calculate_severity(
            ConflictType.TUNING_OVERLAP, affected_count=2
        )
        assert severity == Severity.MEDIUM

        # 1 affected = LOW
        severity = detector.calculate_severity(
            ConflictType.TUNING_OVERLAP, affected_count=1
        )
        assert severity == Severity.LOW

    def test_calculate_severity_resource_duplicate(self, detector):
        """Test severity calculation for resource duplicates."""
        # 3+ affected = MEDIUM
        severity = detector.calculate_severity(
            ConflictType.RESOURCE_DUPLICATE, affected_count=3
        )
        assert severity == Severity.MEDIUM

        # <3 affected = LOW
        severity = detector.calculate_severity(
            ConflictType.RESOURCE_DUPLICATE, affected_count=2
        )
        assert severity == Severity.LOW

    def test_calculate_severity_dependency_missing(self, detector):
        """Test severity for missing dependencies."""
        severity = detector.calculate_severity(
            ConflictType.DEPENDENCY_MISSING, affected_count=1
        )
        assert severity == Severity.HIGH

    def test_calculate_severity_version_conflict(self, detector):
        """Test severity for version conflicts."""
        severity = detector.calculate_severity(
            ConflictType.VERSION_CONFLICT, affected_count=2
        )
        assert severity == Severity.MEDIUM

    def test_calculate_severity_namespace_collision(self, detector):
        """Test severity for namespace collisions."""
        # 2+ affected = HIGH
        severity = detector.calculate_severity(
            ConflictType.NAMESPACE_COLLISION, affected_count=2
        )
        assert severity == Severity.HIGH

        # 1 affected = MEDIUM
        severity = detector.calculate_severity(
            ConflictType.NAMESPACE_COLLISION, affected_count=1
        )
        assert severity == Severity.MEDIUM

    def test_generate_conflict_id(self, detector):
        """Test conflict ID generation."""
        conflict_id = detector.generate_conflict_id(
            ConflictType.TUNING_OVERLAP, "12345678"
        )

        assert conflict_id.startswith("tuni_")
        assert "12345678" in conflict_id

    def test_generate_conflict_id_unique_types(self, detector):
        """Test that different conflict types get different prefixes."""
        id1 = detector.generate_conflict_id(ConflictType.TUNING_OVERLAP, "test")
        id2 = detector.generate_conflict_id(ConflictType.SCRIPT_INJECTION, "test")
        id3 = detector.generate_conflict_id(ConflictType.RESOURCE_DUPLICATE, "test")

        # All should be different due to type prefix
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_create_conflict(self, detector):
        """Test creating a conflict object."""
        conflict = detector.create_conflict(
            conflict_type=ConflictType.TUNING_OVERLAP,
            affected_mods=["mod_a", "mod_b"],
            description="Test conflict",
            identifier="test_001",
            resolution="Remove one mod",
            details={"tuning_id": 12345},
        )

        assert isinstance(conflict, ModConflict)
        assert conflict.type == ConflictType.TUNING_OVERLAP
        assert len(conflict.affected_mods) == 2
        assert "mod_a" in conflict.affected_mods
        assert conflict.description == "Test conflict"
        assert conflict.resolution == "Remove one mod"
        assert conflict.details["tuning_id"] == 12345
        assert conflict.severity == Severity.MEDIUM  # 2 mods = MEDIUM for tuning

    def test_create_conflict_without_optional_args(self, detector):
        """Test creating conflict without optional arguments."""
        conflict = detector.create_conflict(
            conflict_type=ConflictType.TUNING_OVERLAP,
            affected_mods=["mod_a"],
            description="Test",
            identifier="test_002",
        )

        assert conflict.resolution is None
        assert conflict.details == {}

    def test_run_tracks_metadata(self, counting_detector, sample_mods):
        """Test that run() tracks execution metadata."""
        # Initially no run
        assert counting_detector.last_run is None
        assert counting_detector.conflicts_found == 0

        # Run detection
        before = datetime.now()
        conflicts = counting_detector.run(sample_mods)
        after = datetime.now()

        # Should have tracked run
        assert counting_detector.last_run is not None
        assert before <= counting_detector.last_run <= after
        assert counting_detector.conflicts_found == len(conflicts)
        assert counting_detector.conflicts_found == 1  # Should find 1 conflict

    def test_run_returns_conflicts(self, counting_detector, sample_mods):
        """Test that run() returns conflicts from detect()."""
        conflicts = counting_detector.run(sample_mods)

        assert len(conflicts) == 1
        assert isinstance(conflicts[0], ModConflict)


class TestSeverityRules:
    """Tests for SeverityRules class."""

    def test_critical_threshold(self):
        """Test critical threshold constant."""
        assert SeverityRules.CRITICAL_THRESHOLD == 3

    def test_high_threshold(self):
        """Test high threshold constant."""
        assert SeverityRules.HIGH_THRESHOLD == 2

    def test_medium_threshold(self):
        """Test medium threshold constant."""
        assert SeverityRules.MEDIUM_THRESHOLD == 1

    def test_is_core_tuning_true(self):
        """Test identifying core tuning types."""
        assert SeverityRules.is_core_tuning("Buff") is True
        assert SeverityRules.is_core_tuning("Trait") is True
        assert SeverityRules.is_core_tuning("Skill") is True
        assert SeverityRules.is_core_tuning("Career") is True

    def test_is_core_tuning_false(self):
        """Test non-core tuning types."""
        assert SeverityRules.is_core_tuning("Object") is False
        assert SeverityRules.is_core_tuning("Interaction") is False
        assert SeverityRules.is_core_tuning("Unknown") is False

    def test_is_high_risk_hook_true(self):
        """Test identifying high-risk hooks."""
        assert SeverityRules.is_high_risk_hook("inject_to") is True
        assert SeverityRules.is_high_risk_hook("wrap_function") is True
        assert SeverityRules.is_high_risk_hook("override") is True
        assert SeverityRules.is_high_risk_hook("@inject_to") is True

    def test_is_high_risk_hook_false(self):
        """Test non-high-risk hooks."""
        assert SeverityRules.is_high_risk_hook("listener") is False
        assert SeverityRules.is_high_risk_hook("event.register") is False

    def test_core_tuning_types_defined(self):
        """Test that core tuning types are defined."""
        assert len(SeverityRules.CORE_TUNING_TYPES) > 0
        assert "Buff" in SeverityRules.CORE_TUNING_TYPES

    def test_high_risk_hooks_defined(self):
        """Test that high-risk hooks are defined."""
        assert len(SeverityRules.HIGH_RISK_HOOKS) > 0
        assert "inject_to" in SeverityRules.HIGH_RISK_HOOKS


class TestConflictResolutions:
    """Tests for ConflictResolutions class."""

    def test_tuning_overlap_resolution(self):
        """Test tuning overlap resolution text."""
        assert len(ConflictResolutions.TUNING_OVERLAP) > 0
        assert "compatibility" in ConflictResolutions.TUNING_OVERLAP.lower()

    def test_resource_duplicate_resolution(self):
        """Test resource duplicate resolution text."""
        assert len(ConflictResolutions.RESOURCE_DUPLICATE) > 0
        assert "duplicate" in ConflictResolutions.RESOURCE_DUPLICATE.lower()

    def test_script_injection_resolution(self):
        """Test script injection resolution text."""
        assert len(ConflictResolutions.SCRIPT_INJECTION) > 0
        assert "inject" in ConflictResolutions.SCRIPT_INJECTION.lower()

    def test_get_resolution_known_types(self):
        """Test getting resolution for known conflict types."""
        resolution = ConflictResolutions.get_resolution(ConflictType.TUNING_OVERLAP)
        assert resolution == ConflictResolutions.TUNING_OVERLAP

        resolution = ConflictResolutions.get_resolution(
            ConflictType.RESOURCE_DUPLICATE
        )
        assert resolution == ConflictResolutions.RESOURCE_DUPLICATE

    def test_get_resolution_all_types(self):
        """Test that all conflict types have resolutions."""
        for conflict_type in ConflictType:
            resolution = ConflictResolutions.get_resolution(conflict_type)
            assert len(resolution) > 0
            assert isinstance(resolution, str)
