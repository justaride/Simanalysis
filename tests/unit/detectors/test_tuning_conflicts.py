"""Tests for tuning conflict detector."""

from pathlib import Path

import pytest

from simanalysis.detectors.tuning_conflicts import TuningConflictDetector
from simanalysis.models import (
    ConflictType,
    Mod,
    ModType,
    Severity,
    TuningData,
)


class TestTuningConflictDetector:
    """Tests for TuningConflictDetector."""

    @pytest.fixture
    def detector(self) -> TuningConflictDetector:
        """Create detector instance."""
        return TuningConflictDetector()

    @pytest.fixture
    def mods_no_conflicts(self) -> list[Mod]:
        """Create mods with no tuning conflicts."""
        mod1 = Mod(
            name="mod1.package",
            path=Path("/mods/mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=0x12345678,
                    tuning_name="buff_happy",
                    tuning_class="Buff",
                    module="buffs.buff",
                ),
            ],
        )

        mod2 = Mod(
            name="mod2.package",
            path=Path("/mods/mod2.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash2",
            tunings=[
                TuningData(
                    instance_id=0x87654321,  # Different ID
                    tuning_name="buff_sad",
                    tuning_class="Buff",
                    module="buffs.buff",
                ),
            ],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_conflict(self) -> list[Mod]:
        """Create mods with tuning conflict."""
        shared_tuning_id = 0xAABBCCDD

        mod1 = Mod(
            name="mod_a.package",
            path=Path("/mods/mod_a.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash_a",
            tunings=[
                TuningData(
                    instance_id=shared_tuning_id,
                    tuning_name="trait_active",
                    tuning_class="Trait",
                    module="traits.trait",
                    modified_attributes={"energy": 10},
                ),
            ],
        )

        mod2 = Mod(
            name="mod_b.package",
            path=Path("/mods/mod_b.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash_b",
            tunings=[
                TuningData(
                    instance_id=shared_tuning_id,  # Same ID = conflict
                    tuning_name="trait_active",
                    tuning_class="Trait",
                    module="traits.trait",
                    modified_attributes={"energy": 15},
                ),
            ],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_core_conflict(self) -> list[Mod]:
        """Create mods with core tuning conflict."""
        shared_tuning_id = 0x11111111

        mod1 = Mod(
            name="buff_mod1.package",
            path=Path("/mods/buff_mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=shared_tuning_id,
                    tuning_name="buff_confident",
                    tuning_class="Buff",  # Core tuning type
                    module="buffs.buff",
                ),
            ],
        )

        mod2 = Mod(
            name="buff_mod2.package",
            path=Path("/mods/buff_mod2.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash2",
            tunings=[
                TuningData(
                    instance_id=shared_tuning_id,
                    tuning_name="buff_confident",
                    tuning_class="Buff",
                    module="buffs.buff",
                ),
            ],
        )

        return [mod1, mod2]

    @pytest.fixture
    def mods_with_multiple_conflicts(self) -> list[Mod]:
        """Create mods with multiple conflicts."""
        mod1 = Mod(
            name="multi_mod1.package",
            path=Path("/mods/multi_mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=0x11111111,
                    tuning_name="buff1",
                    tuning_class="Buff",
                    module="buffs",
                ),
                TuningData(
                    instance_id=0x22222222,
                    tuning_name="trait1",
                    tuning_class="Trait",
                    module="traits",
                ),
            ],
        )

        mod2 = Mod(
            name="multi_mod2.package",
            path=Path("/mods/multi_mod2.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash2",
            tunings=[
                TuningData(
                    instance_id=0x11111111,  # Conflicts with mod1
                    tuning_name="buff1",
                    tuning_class="Buff",
                    module="buffs",
                ),
                TuningData(
                    instance_id=0x22222222,  # Conflicts with mod1
                    tuning_name="trait1",
                    tuning_class="Trait",
                    module="traits",
                ),
            ],
        )

        return [mod1, mod2]

    def test_no_conflicts(
        self, detector: TuningConflictDetector, mods_no_conflicts: list[Mod]
    ) -> None:
        """Test detection with no conflicts."""
        conflicts = detector.detect(mods_no_conflicts)

        assert len(conflicts) == 0

    def test_detect_conflict(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test detecting a single conflict."""
        conflicts = detector.detect(mods_with_conflict)

        assert len(conflicts) == 1

        conflict = conflicts[0]
        assert conflict.type == ConflictType.TUNING_OVERLAP
        assert len(conflict.affected_mods) == 2
        assert "mod_a.package" in conflict.affected_mods
        assert "mod_b.package" in conflict.affected_mods

    def test_conflict_details(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflict details are populated correctly."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert "tuning_id" in conflict.details
        assert conflict.details["tuning_id"] == 0xAABBCCDD
        assert "tuning_id_hex" in conflict.details
        assert conflict.details["tuning_id_hex"] == "0xAABBCCDD"
        assert conflict.details["tuning_name"] == "trait_active"
        assert conflict.details["tuning_class"] == "Trait"
        assert conflict.details["mod_count"] == 2

    def test_conflict_description(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflict description is generated."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert len(conflict.description) > 0
        assert "trait_active" in conflict.description
        assert "0xAABBCCDD" in conflict.description
        assert "Trait" in conflict.description

    def test_core_conflict_severity(
        self, detector: TuningConflictDetector, mods_with_core_conflict: list[Mod]
    ) -> None:
        """Test core tuning conflicts get CRITICAL severity."""
        conflicts = detector.detect(mods_with_core_conflict)
        conflict = conflicts[0]

        # Buff is core tuning, should be CRITICAL
        assert conflict.severity == Severity.CRITICAL
        assert conflict.details["is_core_tuning"] is True

    def test_non_core_conflict_severity(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test non-core conflicts get appropriate severity."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        # Trait IS a core tuning type, so it gets CRITICAL severity
        # This test verifies that Trait conflicts are properly marked as core
        assert conflict.severity == Severity.CRITICAL
        assert conflict.details["is_core_tuning"] is True

    def test_truly_non_core_conflict_severity(
        self, detector: TuningConflictDetector
    ) -> None:
        """Test that non-core tuning types get appropriate severity."""
        shared_id = 0xDEADBEEF

        mod1 = Mod(
            name="obj_mod1.package",
            path=Path("/mods/obj_mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=shared_id,
                    tuning_name="object_table",
                    tuning_class="Object",  # Not in CORE_TUNING_TYPES
                    module="objects",
                )
            ],
        )

        mod2 = Mod(
            name="obj_mod2.package",
            path=Path("/mods/obj_mod2.package"),
            type=ModType.PACKAGE,
            size=2000,
            hash="hash2",
            tunings=[
                TuningData(
                    instance_id=shared_id,
                    tuning_name="object_table",
                    tuning_class="Object",
                    module="objects",
                )
            ],
        )

        conflicts = detector.detect([mod1, mod2])
        conflict = conflicts[0]

        # Object is NOT core tuning, 2 mods = MEDIUM
        assert conflict.details["is_core_tuning"] is False
        assert conflict.severity == Severity.MEDIUM

    def test_multiple_conflicts(
        self,
        detector: TuningConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test detecting multiple conflicts."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        assert len(conflicts) == 2

        # Should find conflicts for both tuning IDs
        tuning_ids = {c.details["tuning_id"] for c in conflicts}
        assert 0x11111111 in tuning_ids
        assert 0x22222222 in tuning_ids

    def test_three_way_conflict(self, detector: TuningConflictDetector) -> None:
        """Test conflict with three mods."""
        shared_id = 0x99999999

        mods = [
            Mod(
                name=f"mod{i}.package",
                path=Path(f"/mods/mod{i}.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash=f"hash{i}",
                tunings=[
                    TuningData(
                        instance_id=shared_id,
                        tuning_name="skill_fitness",
                        tuning_class="Skill",
                        module="skills",
                    ),
                ],
            )
            for i in range(3)
        ]

        conflicts = detector.detect(mods)

        assert len(conflicts) == 1
        assert len(conflicts[0].affected_mods) == 3
        # 3 mods with Skill (core) = HIGH severity
        assert conflicts[0].severity == Severity.CRITICAL

    def test_get_conflicts_by_class(
        self,
        detector: TuningConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test filtering conflicts by tuning class."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        buff_conflicts = detector.get_conflicts_by_class(conflicts, "Buff")
        assert len(buff_conflicts) == 1
        assert buff_conflicts[0].details["tuning_class"] == "Buff"

        trait_conflicts = detector.get_conflicts_by_class(conflicts, "Trait")
        assert len(trait_conflicts) == 1
        assert trait_conflicts[0].details["tuning_class"] == "Trait"

        # Non-existent class
        object_conflicts = detector.get_conflicts_by_class(conflicts, "Object")
        assert len(object_conflicts) == 0

    def test_get_core_conflicts(
        self, detector: TuningConflictDetector, mods_with_core_conflict: list[Mod]
    ) -> None:
        """Test filtering for core conflicts."""
        conflicts = detector.detect(mods_with_core_conflict)

        core_conflicts = detector.get_core_conflicts(conflicts)
        assert len(core_conflicts) == 1
        assert core_conflicts[0].details["is_core_tuning"] is True

    def test_get_conflict_summary(
        self,
        detector: TuningConflictDetector,
        mods_with_multiple_conflicts: list[Mod],
    ) -> None:
        """Test getting conflict summary statistics."""
        conflicts = detector.detect(mods_with_multiple_conflicts)

        summary = detector.get_conflict_summary(conflicts)

        assert summary["total_conflicts"] == 2
        assert "by_tuning_class" in summary
        assert summary["by_tuning_class"]["Buff"] == 1
        assert summary["by_tuning_class"]["Trait"] == 1

    def test_empty_mods_list(self, detector: TuningConflictDetector) -> None:
        """Test with empty mods list."""
        conflicts = detector.detect([])

        assert len(conflicts) == 0

    def test_mod_with_no_tunings(self, detector: TuningConflictDetector) -> None:
        """Test mod with no tunings."""
        mod = Mod(
            name="empty.package",
            path=Path("/mods/empty.package"),
            type=ModType.PACKAGE,
            size=100,
            hash="hash",
            tunings=[],  # No tunings
        )

        conflicts = detector.detect([mod])
        assert len(conflicts) == 0

    def test_modification_details(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test modification details extraction."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        modifications = conflict.details["modifications"]
        assert len(modifications) == 2

        # Check first modification
        mod1_info = modifications[0]
        assert "mod_name" in mod1_info
        assert "tuning_module" in mod1_info
        assert "attributes_modified" in mod1_info
        assert mod1_info["attributes_modified"] == 1  # {energy: 10}

    def test_conflict_has_resolution(
        self, detector: TuningConflictDetector, mods_with_conflict: list[Mod]
    ) -> None:
        """Test conflicts include resolution suggestions."""
        conflicts = detector.detect(mods_with_conflict)
        conflict = conflicts[0]

        assert conflict.resolution is not None
        assert len(conflict.resolution) > 0
        assert "compatibility" in conflict.resolution.lower()
