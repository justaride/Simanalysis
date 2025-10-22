"""Tests for data models."""

import pytest
from datetime import datetime
from pathlib import Path

from simanalysis.models import (
    AnalysisMetadata,
    AnalysisResult,
    ConflictType,
    DBPFHeader,
    DBPFResource,
    Mod,
    ModConflict,
    ModType,
    PerformanceMetrics,
    ScriptMetadata,
    ScriptModule,
    Severity,
    TuningData,
)


class TestDBPFHeader:
    """Tests for DBPFHeader model."""

    def test_valid_header(self) -> None:
        """Test creating a valid DBPF header."""
        header = DBPFHeader(
            magic=b"DBPF",
            major_version=2,
            minor_version=0,
            user_version=0,
            index_count=10,
            index_offset=96,
            index_size=240,
        )

        assert header.magic == b"DBPF"
        assert header.major_version == 2
        assert header.index_count == 10

    def test_invalid_magic(self) -> None:
        """Test that invalid magic raises ValueError."""
        with pytest.raises(ValueError, match="Invalid DBPF magic"):
            DBPFHeader(
                magic=b"ABCD",
                major_version=2,
                minor_version=0,
                user_version=0,
                index_count=10,
                index_offset=96,
                index_size=240,
            )

    def test_invalid_version(self) -> None:
        """Test that unsupported version raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported DBPF version"):
            DBPFHeader(
                magic=b"DBPF",
                major_version=1,
                minor_version=0,
                user_version=0,
                index_count=10,
                index_offset=96,
                index_size=240,
            )


class TestDBPFResource:
    """Tests for DBPFResource model."""

    def test_resource_key(self) -> None:
        """Test resource key property."""
        resource = DBPFResource(
            type=0x545238C9,
            group=0x00000000,
            instance=0x1234567890ABCDEF,
            offset=1000,
            size=500,
        )

        assert resource.key == (0x545238C9, 0x00000000, 0x1234567890ABCDEF)

    def test_not_compressed(self) -> None:
        """Test is_compressed for uncompressed resource."""
        resource = DBPFResource(
            type=0x545238C9,
            group=0x00000000,
            instance=0x1234567890ABCDEF,
            offset=1000,
            size=500,
            compressed_size=0,
        )

        assert not resource.is_compressed

    def test_compressed(self) -> None:
        """Test is_compressed for compressed resource."""
        resource = DBPFResource(
            type=0x545238C9,
            group=0x00000000,
            instance=0x1234567890ABCDEF,
            offset=1000,
            size=500,
            compressed_size=300,
        )

        assert resource.is_compressed


class TestTuningData:
    """Tests for TuningData model."""

    def test_tuning_data_creation(self) -> None:
        """Test creating tuning data."""
        tuning = TuningData(
            instance_id=0x12345678,
            tuning_name="test_tuning",
            tuning_class="Buff",
            module="buffs.buff_tuning",
            modified_attributes={"mood_weight": 10},
            references={0x87654321},
            pack_requirements={"EP01"},
        )

        assert tuning.instance_id == 0x12345678
        assert tuning.tuning_name == "test_tuning"
        assert "EP01" in tuning.pack_requirements


class TestMod:
    """Tests for Mod model."""

    def test_mod_creation(self) -> None:
        """Test creating a mod."""
        mod = Mod(
            name="test_mod.package",
            path=Path("/mods/test_mod.package"),
            type=ModType.PACKAGE,
            size=1024000,
            hash="abc123",
        )

        assert mod.name == "test_mod.package"
        assert mod.type == ModType.PACKAGE
        assert mod.size == 1024000

    def test_tuning_ids_property(self) -> None:
        """Test tuning_ids property."""
        mod = Mod(
            name="test_mod.package",
            path=Path("/mods/test_mod.package"),
            type=ModType.PACKAGE,
            size=1024000,
            hash="abc123",
            tunings=[
                TuningData(
                    instance_id=0x12345678,
                    tuning_name="test1",
                    tuning_class="Buff",
                    module="buffs",
                ),
                TuningData(
                    instance_id=0x87654321,
                    tuning_name="test2",
                    tuning_class="Buff",
                    module="buffs",
                ),
            ],
        )

        tuning_ids = mod.tuning_ids
        assert len(tuning_ids) == 2
        assert 0x12345678 in tuning_ids
        assert 0x87654321 in tuning_ids

    def test_resource_keys_property(self) -> None:
        """Test resource_keys property."""
        mod = Mod(
            name="test_mod.package",
            path=Path("/mods/test_mod.package"),
            type=ModType.PACKAGE,
            size=1024000,
            hash="abc123",
            resources=[
                DBPFResource(
                    type=0x545238C9,
                    group=0x00000000,
                    instance=0x1111111111111111,
                    offset=1000,
                    size=500,
                ),
                DBPFResource(
                    type=0x545238C9,
                    group=0x00000000,
                    instance=0x2222222222222222,
                    offset=2000,
                    size=600,
                ),
            ],
        )

        resource_keys = mod.resource_keys
        assert len(resource_keys) == 2
        assert (0x545238C9, 0x00000000, 0x1111111111111111) in resource_keys


class TestModConflict:
    """Tests for ModConflict model."""

    def test_conflict_creation(self) -> None:
        """Test creating a conflict."""
        conflict = ModConflict(
            id="conflict_001",
            severity=Severity.HIGH,
            type=ConflictType.TUNING_OVERLAP,
            affected_mods=["mod_a.package", "mod_b.package"],
            description="Tuning ID 0x12345678 modified by multiple mods",
            resolution="Keep only one mod or use compatibility patch",
        )

        assert conflict.severity == Severity.HIGH
        assert conflict.type == ConflictType.TUNING_OVERLAP
        assert len(conflict.affected_mods) == 2


class TestAnalysisResult:
    """Tests for AnalysisResult model."""

    def test_get_conflicts_by_severity(self) -> None:
        """Test filtering conflicts by severity."""
        metadata = AnalysisMetadata(
            timestamp=datetime.now(),
            version="2.0.0",
            mod_directory="/mods",
            analysis_duration_seconds=10.5,
            total_mods_analyzed=100,
        )

        performance = PerformanceMetrics(
            total_mods=100,
            total_size_mb=500.0,
            total_resources=1000,
            total_tunings=200,
            total_scripts=50,
            estimated_load_time_seconds=30.0,
            estimated_memory_mb=250.0,
            complexity_score=65.5,
        )

        conflicts = [
            ModConflict(
                id="c1",
                severity=Severity.CRITICAL,
                type=ConflictType.TUNING_OVERLAP,
                affected_mods=["mod1", "mod2"],
                description="Critical conflict",
            ),
            ModConflict(
                id="c2",
                severity=Severity.HIGH,
                type=ConflictType.RESOURCE_DUPLICATE,
                affected_mods=["mod3", "mod4"],
                description="High severity conflict",
            ),
            ModConflict(
                id="c3",
                severity=Severity.CRITICAL,
                type=ConflictType.SCRIPT_INJECTION,
                affected_mods=["mod5", "mod6"],
                description="Another critical conflict",
            ),
        ]

        result = AnalysisResult(
            metadata=metadata,
            mods=[],
            conflicts=conflicts,
            dependencies={},
            performance=performance,
            recommendations=[],
        )

        critical_conflicts = result.get_conflicts(severity=Severity.CRITICAL)
        assert len(critical_conflicts) == 2

        high_conflicts = result.get_conflicts(severity=Severity.HIGH)
        assert len(high_conflicts) == 1

    def test_get_conflicts_by_type(self) -> None:
        """Test filtering conflicts by type."""
        metadata = AnalysisMetadata(
            timestamp=datetime.now(),
            version="2.0.0",
            mod_directory="/mods",
            analysis_duration_seconds=10.5,
            total_mods_analyzed=100,
        )

        performance = PerformanceMetrics(
            total_mods=100,
            total_size_mb=500.0,
            total_resources=1000,
            total_tunings=200,
            total_scripts=50,
            estimated_load_time_seconds=30.0,
            estimated_memory_mb=250.0,
            complexity_score=65.5,
        )

        conflicts = [
            ModConflict(
                id="c1",
                severity=Severity.CRITICAL,
                type=ConflictType.TUNING_OVERLAP,
                affected_mods=["mod1", "mod2"],
                description="Tuning conflict",
            ),
            ModConflict(
                id="c2",
                severity=Severity.HIGH,
                type=ConflictType.TUNING_OVERLAP,
                affected_mods=["mod3", "mod4"],
                description="Another tuning conflict",
            ),
        ]

        result = AnalysisResult(
            metadata=metadata,
            mods=[],
            conflicts=conflicts,
            dependencies={},
            performance=performance,
            recommendations=[],
        )

        tuning_conflicts = result.get_conflicts(type=ConflictType.TUNING_OVERLAP)
        assert len(tuning_conflicts) == 2

    def test_critical_conflicts_property(self) -> None:
        """Test critical_conflicts property."""
        metadata = AnalysisMetadata(
            timestamp=datetime.now(),
            version="2.0.0",
            mod_directory="/mods",
            analysis_duration_seconds=10.5,
            total_mods_analyzed=100,
        )

        performance = PerformanceMetrics(
            total_mods=100,
            total_size_mb=500.0,
            total_resources=1000,
            total_tunings=200,
            total_scripts=50,
            estimated_load_time_seconds=30.0,
            estimated_memory_mb=250.0,
            complexity_score=65.5,
        )

        conflicts = [
            ModConflict(
                id="c1",
                severity=Severity.CRITICAL,
                type=ConflictType.TUNING_OVERLAP,
                affected_mods=["mod1", "mod2"],
                description="Critical conflict",
            ),
        ]

        result = AnalysisResult(
            metadata=metadata,
            mods=[],
            conflicts=conflicts,
            dependencies={},
            performance=performance,
            recommendations=[],
        )

        assert len(result.critical_conflicts) == 1
        assert result.has_critical_issues is True
