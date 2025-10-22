"""Tests for resource conflict detector."""

from pathlib import Path

import pytest

from simanalysis.detectors.resource_conflicts import ResourceConflictDetector
from simanalysis.models import (
    ConflictType,
    DBPFResource,
    Mod,
    ModType,
    Severity,
)


class TestResourceConflictDetector:
    """Tests for ResourceConflictDetector."""

    @pytest.fixture
    def detector(self) -> ResourceConflictDetector:
        """Create detector instance."""
        return ResourceConflictDetector()

    @pytest.fixture
    def mods_no_conflicts(self) -> list[Mod]:
        """Create mods with no resource conflicts."""
        mod1 = Mod(
            name="mod1.package",
            path=Path("/mods/mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            resources=[
                DBPFResource(
                    type=0x12345678,
                    group=0x00000000,
                    instance=0xAAAAAAAA,
                    size=100,
                    offset=0,
                    compressed_size=0,
                ),
            ],
        )

        mod2 = Mod(
            name="mod2.package",
            path=Path("/mods/mod2.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash2",
            resources=[
                DBPFResource(
                    type=0x12345678,
                    group=0x00000000,
                    instance=0xBBBBBBBB,  # Different instance ID
                    size=200,
                    offset=0,
                    compressed_size=0,
                ),
            ],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_conflict(self) -> list[Mod]:
        """Create mods with resource conflict."""
        shared_resource = DBPFResource(
            type=0x2E75C764,  # Texture
            group=0x00000000,
            instance=0x12345678,
            size=1000,
            offset=0,
            compressed_size=0,
        )

        mod1 = Mod(
            name="texture_mod_a.package",
            path=Path("/mods/texture_mod_a.package"),
            type=ModType.PACKAGE,
            size=5000,
            hash="hash_a",
            resources=[shared_resource],
        )

        mod2 = Mod(
            name="texture_mod_b.package",
            path=Path("/mods/texture_mod_b.package"),
            type=ModType.PACKAGE,
            size=6000,
            hash="hash_b",
            resources=[shared_resource],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_critical_conflict(self) -> list[Mod]:
        """Create mods with critical resource conflict."""
        critical_resource = DBPFResource(
            type=0x545503B2,  # SimData (critical)
            group=0x00000000,
            instance=0x99999999,
            size=500,
            offset=0,
            compressed_size=0,
        )

        mod1 = Mod(
            name="simdata_mod1.package",
            path=Path("/mods/simdata_mod1.package"),
            type=ModType.PACKAGE,
            size=3000,
            hash="hash1",
            resources=[critical_resource],
        )

        mod2 = Mod(
            name="simdata_mod2.package",
            path=Path("/mods/simdata_mod2.package"),
            type=ModType.PACKAGE,
            size=3500,
            hash="hash2",
            resources=[critical_resource],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_hash_collision(self) -> list[Mod]:
        """Create mods with identical hashes (duplicates)."""
        duplicate_hash = "a1b2c3d4e5f6789012345678901234567890abcd"

        mod1 = Mod(
            name="duplicate_a.package",
            path=Path("/mods/duplicate_a.package"),
            type=ModType.PACKAGE,
            size=10000,
            hash=duplicate_hash,
            resources=[],
        )

        mod2 = Mod(
            name="duplicate_b.package",
            path=Path("/mods/duplicate_b.package"),
            type=ModType.PACKAGE,
            size=10000,
            hash=duplicate_hash,
            resources=[],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_multiple_conflicts(self) -> list[Mod]:
        """Create mods with multiple resource conflicts."""
        resource1 = DBPFResource(
            type=0x2E75C764,  # Texture
            group=0x00000000,
            instance=0x11111111,
            size=1000,
            offset=0,
            compressed_size=0,
        )

        resource2 = DBPFResource(
            type=0x015A1849,  # Geometry
            group=0x00000000,
            instance=0x22222222,
            size=2000,
            offset=0,
            compressed_size=0,
        )

        mod1 = Mod(
            name="multi_mod1.package",
            path=Path("/mods/multi_mod1.package"),
            type=ModType.PACKAGE,
            size=5000,
            hash="hash1",
            resources=[resource1, resource2],
        )

        mod2 = Mod(
            name="multi_mod2.package",
            path=Path("/mods/multi_mod2.package"),
            type=ModType.PACKAGE,
            size=6000,
            hash="hash2",
            resources=[resource1, resource2],
        )

        return [mod1, mod2]

    def test_no_conflicts(
        self, detector: ResourceConflictDetector, mods_no_conflicts: list[Mod]
    ) -> None:
        """Test detection with no conflicts."""
        conflicts = detector.detect(mods_no_conflicts)

        assert len(conflicts) == 0

    def test_detect_resource_conflict(
        self, detector: ResourceConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test detecting a resource conflict."""
        conflicts = detector.detect(mods_with_conflict)

        assert len(conflicts) == 1

        conflict = conflicts[0]
        assert conflict.type == ConflictType.RESOURCE_DUPLICATE
        assert len(conflict.affected_mods) == 2
        assert "texture_mod_a.package" in conflict.affected_mods
        assert "texture_mod_b.package" in conflict.affected_mods

    def test_conflict_details(
        self, detector: ResourceConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflict details are populated correctly."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert "resource_key" in conflict.details
        assert "resource_type" in conflict.details
        assert conflict.details["resource_type"] == 0x2E75C764
        assert conflict.details["resource_type_name"] == "Texture"
        assert conflict.details["mod_count"] == 2

    def test_conflict_description(
        self, detector: ResourceConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflict description is generated."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert len(conflict.description) > 0
        assert "Texture" in conflict.description
        assert "2 mods" in conflict.description

    def test_critical_resource_severity(
        self,
        detector: ResourceConflictDetector,
        mods_with_critical_conflict: list[Mod],
    ) -> None:
        """Test critical resources get CRITICAL severity."""
        conflicts = detector.detect(mods_with_critical_conflict)
        conflict = conflicts[0]

        # SimData is critical resource type
        assert conflict.severity == Severity.CRITICAL
        assert conflict.details["is_critical_resource"] is True
        assert "critical resource" in conflict.description.lower()

    def test_non_critical_resource_severity(
        self, detector: ResourceConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test non-critical resources get appropriate severity."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        # Texture with 2 mods = LOW (from RESOURCE_DUPLICATE rules)
        assert conflict.severity == Severity.LOW
        assert conflict.details["is_critical_resource"] is False

    def test_hash_collision_detection(
        self,
        detector: ResourceConflictDetector,
        mods_with_hash_collision: list[Mod],
    ) -> None:
        """Test detecting hash collisions (duplicate files)."""
        conflicts = detector.detect(mods_with_hash_collision)

        assert len(conflicts) == 1

        conflict = conflicts[0]
        assert conflict.type == ConflictType.RESOURCE_DUPLICATE
        assert "file_hash" in conflict.details
        assert conflict.details["mod_count"] == 2
        assert "duplicate" in conflict.description.lower()

    def test_hash_collision_details(
        self,
        detector: ResourceConflictDetector,
        mods_with_hash_collision: list[Mod],
    ) -> None:
        """Test hash collision details."""
        conflicts = detector.detect(mods_with_hash_collision)
        conflict = conflicts[0]

        assert conflict.details["file_hash"] == "a1b2c3d4e5f6789012345678901234567890abcd"
        assert conflict.details["total_size"] == 20000  # 10000 + 10000
        assert len(conflict.details["affected_mod_names"]) == 2

    def test_multiple_conflicts(
        self,
        detector: ResourceConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test detecting multiple conflicts."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        # Should find 2 resource key conflicts
        assert len(conflicts) == 2

        # Check resource types
        resource_types = {c.details["resource_type_name"] for c in conflicts}
        assert "Texture" in resource_types
        assert "Geometry" in resource_types

    def test_three_way_conflict(self, detector: ResourceConflictDetector) -> None:
        """Test conflict with three mods."""
        shared_resource = DBPFResource(
            type=0x0333406C,  # Object Definition (critical)
            group=0x00000000,
            instance=0xDEADBEEF,
            size=1000,
            offset=0,
            compressed_size=0,
        )

        mods = [
            Mod(
                name=f"obj_mod{i}.package",
                path=Path(f"/mods/obj_mod{i}.package"),
                type=ModType.PACKAGE,
                size=2000,
                hash=f"hash{i}",
                resources=[shared_resource],
            )
            for i in range(3)
        ]

        conflicts = detector.detect(mods)

        assert len(conflicts) == 1
        assert len(conflicts[0].affected_mods) == 3
        # Object Definition is critical, 3 mods = CRITICAL
        assert conflicts[0].severity == Severity.CRITICAL

    def test_get_critical_conflicts(
        self,
        detector: ResourceConflictDetector,
        mods_with_critical_conflict: list[Mod],
    ) -> None:
        """Test filtering for critical conflicts."""
        conflicts = detector.detect(mods_with_critical_conflict)

        critical_conflicts = detector.get_critical_conflicts(conflicts)
        assert len(critical_conflicts) == 1
        assert critical_conflicts[0].details["is_critical_resource"] is True

    def test_get_conflicts_by_type(
        self,
        detector: ResourceConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test filtering conflicts by resource type."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        texture_conflicts = detector.get_conflicts_by_type(conflicts, "Texture")
        assert len(texture_conflicts) == 1
        assert texture_conflicts[0].details["resource_type_name"] == "Texture"

        geometry_conflicts = detector.get_conflicts_by_type(conflicts, "Geometry")
        assert len(geometry_conflicts) == 1
        assert geometry_conflicts[0].details["resource_type_name"] == "Geometry"

        # Non-existent type
        audio_conflicts = detector.get_conflicts_by_type(conflicts, "Audio")
        assert len(audio_conflicts) == 0

    def test_get_hash_collision_conflicts(
        self,
        detector: ResourceConflictDetector,
        mods_with_hash_collision: list[Mod],
    ) -> None:
        """Test filtering for hash collision conflicts."""
        conflicts = detector.detect(mods_with_hash_collision)

        hash_conflicts = detector.get_hash_collision_conflicts(conflicts)
        assert len(hash_conflicts) == 1
        assert "file_hash" in hash_conflicts[0].details

    def test_get_conflict_summary(
        self,
        detector: ResourceConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test getting conflict summary statistics."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        summary = detector.get_conflict_summary(conflicts)

        assert summary["total_conflicts"] == 2
        assert "by_resource_type" in summary
        assert summary["by_resource_type"]["Texture"] == 1
        assert summary["by_resource_type"]["Geometry"] == 1
        assert summary["resource_key_conflicts"] == 2
        assert summary["hash_collision_conflicts"] == 0

    def test_empty_mods_list(self, detector: ResourceConflictDetector) -> None:
        """Test with empty mods list."""
        conflicts = detector.detect([])

        assert len(conflicts) == 0

    def test_mod_with_no_resources(self, detector: ResourceConflictDetector) -> None:
        """Test mod with no resources."""
        mod = Mod(
            name="empty.package",
            path=Path("/mods/empty.package"),
            type=ModType.PACKAGE,
            size=100,
            hash="hash",
            resources=[],  # No resources
        )

        conflicts = detector.detect([mod])
        assert len(conflicts) == 0

    def test_mixed_conflicts(self, detector: ResourceConflictDetector) -> None:
        """Test both resource key and hash collision conflicts."""
        shared_resource = DBPFResource(
            type=0x2E75C764,
            group=0x00000000,
            instance=0x12345678,
            size=1000,
            offset=0,
            compressed_size=0,
        )

        duplicate_hash = "duplicate_hash_value"

        mod1 = Mod(
            name="mod1.package",
            path=Path("/mods/mod1.package"),
            type=ModType.PACKAGE,
            size=5000,
            hash="unique_hash_1",
            resources=[shared_resource],
        )

        mod2 = Mod(
            name="mod2.package",
            path=Path("/mods/mod2.package"),
            type=ModType.PACKAGE,
            size=5000,
            hash="unique_hash_2",
            resources=[shared_resource],
        )

        mod3 = Mod(
            name="duplicate_a.package",
            path=Path("/mods/duplicate_a.package"),
            type=ModType.PACKAGE,
            size=3000,
            hash=duplicate_hash,
            resources=[],
        )

        mod4 = Mod(
            name="duplicate_b.package",
            path=Path("/mods/duplicate_b.package"),
            type=ModType.PACKAGE,
            size=3000,
            hash=duplicate_hash,
            resources=[],
        )

        conflicts = detector.detect([mod1, mod2, mod3, mod4])

        # Should find 1 resource key conflict + 1 hash collision
        assert len(conflicts) == 2

        # One should be resource key conflict, one hash collision
        resource_conflicts = [c for c in conflicts if "resource_key" in c.details]
        hash_conflicts = [c for c in conflicts if "file_hash" in c.details]

        assert len(resource_conflicts) == 1
        assert len(hash_conflicts) == 1

    def test_resource_type_names(self, detector: ResourceConflictDetector) -> None:
        """Test resource type name mapping."""
        assert detector._get_resource_type_name(0x545503B2) == "SimData"
        assert detector._get_resource_type_name(0x0333406C) == "Object Definition"
        assert detector._get_resource_type_name(0x2E75C764) == "Texture"
        assert detector._get_resource_type_name(0x015A1849) == "Geometry"
        assert detector._get_resource_type_name(0x99999999) == "Unknown"

    def test_conflict_has_resolution(
        self, detector: ResourceConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflicts include resolution suggestions."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert conflict.resolution is not None
        assert len(conflict.resolution) > 0
        assert "duplicate" in conflict.resolution.lower()

    def test_mods_without_hash(self, detector: ResourceConflictDetector) -> None:
        """Test handling mods without hash values."""
        mod1 = Mod(
            name="no_hash_mod.package",
            path=Path("/mods/no_hash_mod.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash=None,  # No hash
            resources=[],
        )

        conflicts = detector.detect([mod1])
        # Should not crash, no hash collisions detected
        assert len(conflicts) == 0
