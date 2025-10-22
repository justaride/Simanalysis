"""Tests for mod analyzer."""

import json
import struct
import zlib
from pathlib import Path

import pytest

from simanalysis.analyzers import ModAnalyzer
from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import (
    ConflictType,
    DBPFResource,
    Mod,
    ModType,
    Severity,
    TuningData,
)


class TestModAnalyzer:
    """Tests for ModAnalyzer."""

    @pytest.fixture
    def analyzer(self) -> ModAnalyzer:
        """Create analyzer instance."""
        return ModAnalyzer()

    @pytest.fixture
    def test_mods_directory(self, tmp_path: Path) -> Path:
        """Create test directory with sample mods."""
        mods_dir = tmp_path / "Mods"
        mods_dir.mkdir()

        # Create two package files with conflicting tunings
        for i, name in enumerate(["mod_a.package", "mod_b.package"]):
            pkg_path = mods_dir / name
            self._create_test_package(pkg_path, tuning_id=0x12345678)

        return mods_dir

    @pytest.fixture
    def test_mods_with_conflicts(self) -> list[Mod]:
        """Create test mods with conflicts."""
        shared_tuning_id = 0xAABBCCDD

        mod1 = Mod(
            name="mod1.package",
            path=Path("/mods/mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=shared_tuning_id,
                    tuning_name="buff_happy",
                    tuning_class="Buff",
                    module="buffs",
                )
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
                    instance_id=shared_tuning_id,
                    tuning_name="buff_happy",
                    tuning_class="Buff",
                    module="buffs",
                )
            ],
        )

        return [mod1, mod2]

    @pytest.fixture
    def test_mods_no_conflicts(self) -> list[Mod]:
        """Create test mods without conflicts."""
        mod1 = Mod(
            name="mod1.package",
            path=Path("/mods/mod1.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="hash1",
            tunings=[
                TuningData(
                    instance_id=0x11111111,
                    tuning_name="buff_1",
                    tuning_class="Buff",
                    module="buffs",
                )
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
                    instance_id=0x22222222,
                    tuning_name="buff_2",
                    tuning_class="Buff",
                    module="buffs",
                )
            ],
        )

        return [mod1, mod2]

    def _create_test_package(
        self, path: Path, tuning_id: int = 0x12345678
    ) -> None:
        """Create a minimal test package file."""
        # Create minimal DBPF file (96-byte header)
        header = bytearray(96)
        header[0:4] = b"DBPF"
        header[4:8] = struct.pack("<I", 2)  # major_version
        header[40:44] = struct.pack("<I", 1)  # index_count
        header[44:48] = struct.pack("<I", 96)  # index_offset
        header[48:52] = struct.pack("<I", 32)  # index_size

        # Create resource
        resource_data = b"Test resource"
        compressed_data = zlib.compress(resource_data)
        resource_offset = 96 + 32

        # Create index entry
        index_entry = struct.pack(
            "<IIQIII",
            0x12345678,
            0x00000000,
            tuning_id,
            resource_offset,
            len(compressed_data),
            len(resource_data),
        )

        # Write file
        with open(path, "wb") as f:
            f.write(header)
            f.write(index_entry)
            f.write(compressed_data)

    def test_analyzer_initialization(self, analyzer: ModAnalyzer) -> None:
        """Test analyzer initializes correctly."""
        assert analyzer.scanner is not None
        assert len(analyzer.detectors) == 2  # Default detectors

    def test_analyzer_initialization_with_options(self) -> None:
        """Test analyzer with custom options."""
        analyzer = ModAnalyzer(
            parse_tunings=False,
            parse_scripts=False,
            calculate_hashes=False,
        )

        assert analyzer.scanner.parse_tunings is False
        assert analyzer.scanner.parse_scripts is False
        assert analyzer.scanner.calculate_hashes is False

    def test_analyzer_custom_detectors(self) -> None:
        """Test analyzer with custom detectors."""

        class CustomDetector(ConflictDetector):
            def detect(self, mods):
                return []

        custom_detectors = [CustomDetector()]
        analyzer = ModAnalyzer(detectors=custom_detectors)

        assert len(analyzer.detectors) == 1
        assert isinstance(analyzer.detectors[0], CustomDetector)

    def test_analyze_mods_with_conflicts(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod]
    ) -> None:
        """Test analyzing mods with conflicts."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)

        assert len(result.mods) == 2
        assert len(result.conflicts) > 0
        assert any(c.type == ConflictType.TUNING_OVERLAP for c in result.conflicts)

    def test_analyze_mods_no_conflicts(
        self, analyzer: ModAnalyzer, test_mods_no_conflicts: list[Mod]
    ) -> None:
        """Test analyzing mods without conflicts."""
        result = analyzer.analyze_mods(test_mods_no_conflicts)

        assert len(result.mods) == 2
        assert len(result.conflicts) == 0

    def test_detect_conflicts(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod]
    ) -> None:
        """Test conflict detection."""
        conflicts = analyzer.detect_conflicts(test_mods_with_conflicts)

        assert len(conflicts) > 0
        assert all(hasattr(c, "type") for c in conflicts)
        assert all(hasattr(c, "severity") for c in conflicts)

    def test_get_summary(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod]
    ) -> None:
        """Test getting summary statistics."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        summary = analyzer.get_summary(result)

        assert "total_mods" in summary
        assert "total_conflicts" in summary
        assert "critical_conflicts" in summary
        assert "high_conflicts" in summary
        assert "medium_conflicts" in summary
        assert "low_conflicts" in summary
        assert "scan_summary" in summary

        assert summary["total_mods"] == 2
        assert summary["total_conflicts"] > 0

    def test_get_recommendations_with_conflicts(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod]
    ) -> None:
        """Test getting recommendations with conflicts."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        recommendations = analyzer.get_recommendations(result)

        assert len(recommendations) > 0
        assert any("conflict" in rec.lower() for rec in recommendations)

    def test_get_recommendations_no_conflicts(
        self, analyzer: ModAnalyzer, test_mods_no_conflicts: list[Mod]
    ) -> None:
        """Test getting recommendations without conflicts."""
        result = analyzer.analyze_mods(test_mods_no_conflicts)
        recommendations = analyzer.get_recommendations(result)

        assert len(recommendations) > 0
        assert any("no conflicts" in rec.lower() for rec in recommendations)

    def test_get_recommendations_many_mods(self, analyzer: ModAnalyzer) -> None:
        """Test recommendations for many mods."""
        # Create 150 mods
        mods = [
            Mod(
                name=f"mod{i}.package",
                path=Path(f"/mods/mod{i}.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash=f"hash{i}",
            )
            for i in range(150)
        ]

        result = analyzer.analyze_mods(mods)
        recommendations = analyzer.get_recommendations(result)

        # Should mention organizing into subfolders
        assert any("organizing" in rec.lower() or "subfolders" in rec.lower() for rec in recommendations)

    def test_export_text_report(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test exporting text report."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        output_path = tmp_path / "report.txt"

        analyzer.export_report(result, output_path, format="txt")

        assert output_path.exists()
        content = output_path.read_text()

        assert "MOD ANALYSIS REPORT" in content
        assert "SUMMARY" in content
        assert "Total Mods" in content
        assert "Total Conflicts" in content

    def test_export_json_report(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test exporting JSON report."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        output_path = tmp_path / "report.json"

        analyzer.export_report(result, output_path, format="json")

        assert output_path.exists()

        # Parse JSON
        with open(output_path) as f:
            data = json.load(f)

        assert "summary" in data
        assert "recommendations" in data
        assert "mods" in data
        assert "conflicts" in data
        assert len(data["mods"]) == 2

    def test_export_unsupported_format(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test exporting with unsupported format."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        output_path = tmp_path / "report.xml"

        with pytest.raises(ValueError, match="Unsupported format"):
            analyzer.export_report(result, output_path, format="xml")

    def test_analyze_directory(
        self, analyzer: ModAnalyzer, test_mods_directory: Path
    ) -> None:
        """Test analyzing a directory."""
        result = analyzer.analyze_directory(test_mods_directory)

        assert len(result.mods) >= 2
        # Conflicts expected since both packages have same tuning ID
        # (though parsing might fail, that's OK for this test)

    def test_analyze_directory_non_recursive(
        self, analyzer: ModAnalyzer, test_mods_directory: Path
    ) -> None:
        """Test non-recursive directory analysis."""
        # Create subfolder with mods
        subfolder = test_mods_directory / "Subfolder"
        subfolder.mkdir()
        self._create_test_package(subfolder / "nested_mod.package")

        # Non-recursive should not find nested mod
        result = analyzer.analyze_directory(test_mods_directory, recursive=False)

        # Should only find mods in root directory
        assert all("Subfolder" not in str(mod.path) for mod in result.mods)

    def test_recommendations_critical_conflicts(
        self, analyzer: ModAnalyzer
    ) -> None:
        """Test recommendations with critical conflicts."""
        # Create mods with critical conflict (Buff is core)
        mods = [
            Mod(
                name=f"mod{i}.package",
                path=Path(f"/mods/mod{i}.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash=f"hash{i}",
                tunings=[
                    TuningData(
                        instance_id=0x99999999,
                        tuning_name="buff_critical",
                        tuning_class="Buff",  # Core tuning
                        module="buffs",
                    )
                ],
            )
            for i in range(2)
        ]

        result = analyzer.analyze_mods(mods)
        recommendations = analyzer.get_recommendations(result)

        # Should mention critical conflicts
        assert any("critical" in rec.lower() for rec in recommendations)

    def test_recommendations_hash_collisions(
        self, analyzer: ModAnalyzer
    ) -> None:
        """Test recommendations with hash collisions."""
        # Create mods with same hash
        duplicate_hash = "duplicate_hash_12345"
        mods = [
            Mod(
                name=f"mod{i}.package",
                path=Path(f"/mods/mod{i}.package"),
                type=ModType.PACKAGE,
                size=1000,
                hash=duplicate_hash,
            )
            for i in range(2)
        ]

        result = analyzer.analyze_mods(mods)
        recommendations = analyzer.get_recommendations(result)

        # Should mention duplicates
        assert any("duplicate" in rec.lower() for rec in recommendations)

    def test_text_report_includes_recommendations(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test that text report includes recommendations."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        output_path = tmp_path / "report.txt"

        analyzer.export_report(result, output_path, format="txt")

        content = output_path.read_text()
        assert "RECOMMENDATIONS" in content

    def test_text_report_groups_by_severity(
        self, analyzer: ModAnalyzer, test_mods_with_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test that text report groups conflicts by severity."""
        result = analyzer.analyze_mods(test_mods_with_conflicts)
        output_path = tmp_path / "report.txt"

        analyzer.export_report(result, output_path, format="txt")

        content = output_path.read_text()
        # Should have severity sections
        assert "CONFLICTS" in content
        # Will have at least one severity level mentioned
        assert any(sev in content for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"])

    def test_json_report_structure(
        self, analyzer: ModAnalyzer, test_mods_no_conflicts: list[Mod], tmp_path: Path
    ) -> None:
        """Test JSON report has correct structure."""
        result = analyzer.analyze_mods(test_mods_no_conflicts)
        output_path = tmp_path / "report.json"

        analyzer.export_report(result, output_path, format="json")

        with open(output_path) as f:
            data = json.load(f)

        # Check mod structure
        assert len(data["mods"]) == 2
        for mod_data in data["mods"]:
            assert "name" in mod_data
            assert "path" in mod_data
            assert "type" in mod_data
            assert "size" in mod_data

        # Check conflicts structure (should be empty for this case)
        assert len(data["conflicts"]) == 0
