"""Tests for dependency detection."""

from pathlib import Path
import pytest

from simanalysis.analyzers.dependency_detector import DependencyDetector
from simanalysis.models import Mod, ModType, TuningData, ScriptModule


@pytest.fixture
def detector():
    """Create DependencyDetector instance."""
    return DependencyDetector()


@pytest.fixture
def package_mod():
    """Create a package mod with tuning data."""
    mod = Mod(
        name="TestMod.package",
        path=Path("TestMod.package"),
        type=ModType.PACKAGE,
        size=1000,
        hash="abc123",
    )

    # Add tuning with pack requirement
    tuning = TuningData(
        instance_id=0x12345678,
        tuning_name="trait_Test",
        tuning_class="Trait",
        module="traits.trait_test",
    )
    tuning.pack_requirements = {"EP01"}  # Get to Work
    mod.tunings.append(tuning)

    return mod


@pytest.fixture
def script_mod_with_imports():
    """Create a script mod with imports."""
    mod = Mod(
        name="ScriptMod.ts4script",
        path=Path("ScriptMod.ts4script"),
        type=ModType.SCRIPT,
        size=2000,
        hash="def456",
    )

    # Add script module with imports
    script = ScriptModule(
        name="main.py",
        path="main.py",
    )

    # Add import that matches known mod
    script.imports = {"mccc_module.core", "sims4.commands"}

    mod.scripts.append(script)

    return mod


class TestPackRequirements:
    """Test pack requirement detection."""

    def test_detect_single_pack(self, detector, package_mod):
        """Test detecting single pack requirement."""
        deps = detector._detect_pack_requirements(package_mod)

        assert len(deps) == 1
        assert "Get to Work" in deps

    def test_detect_multiple_packs(self, detector):
        """Test detecting multiple pack requirements."""
        mod = Mod(
            name="TestMod.package",
            path=Path("TestMod.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="abc123",
        )

        # Add tuning with multiple packs
        tuning = TuningData(
            instance_id=0x12345678,
            tuning_name="trait_Test",
            tuning_class="Trait",
            module="traits.trait_test",
        )
        tuning.pack_requirements = {"EP01", "GP02", "SP10"}  # Multiple packs
        mod.tunings.append(tuning)

        deps = detector._detect_pack_requirements(mod)

        assert len(deps) == 3
        assert "Get to Work" in deps
        assert "Spa Day" in deps
        assert "Bowling Night Stuff" in deps

    def test_unknown_pack_code(self, detector):
        """Test handling of unknown pack codes."""
        mod = Mod(
            name="TestMod.package",
            path=Path("TestMod.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="abc123",
        )

        tuning = TuningData(
            instance_id=0x12345678,
            tuning_name="trait_Test",
            tuning_class="Trait",
            module="traits.trait_test",
        )
        tuning.pack_requirements = {"UNKNOWN99"}
        mod.tunings.append(tuning)

        deps = detector._detect_pack_requirements(mod)

        assert len(deps) == 0

    def test_no_pack_requirements(self, detector):
        """Test mod with no pack requirements."""
        mod = Mod(
            name="TestMod.package",
            path=Path("TestMod.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="abc123",
        )

        deps = detector._detect_pack_requirements(mod)

        assert len(deps) == 0


class TestScriptDependencies:
    """Test script import detection."""

    def test_detect_mccc_import(self, detector, script_mod_with_imports):
        """Test detecting MC Command Center import."""
        deps = detector._detect_script_dependencies(script_mod_with_imports)

        assert len(deps) == 1
        assert "MC Command Center" in deps

    def test_detect_basemental_import(self, detector):
        """Test detecting Basemental import."""
        mod = Mod(
            name="Script.ts4script",
            path=Path("Script.ts4script"),
            type=ModType.SCRIPT,
            size=2000,
            hash="def456",
        )

        script = ScriptModule(name="main.py", path="main.py")
        script.imports = {"basemental.drugs", "sims4.commands"}
        mod.scripts.append(script)

        deps = detector._detect_script_dependencies(mod)

        assert "Basemental Drugs" in deps

    def test_multiple_mod_imports(self, detector):
        """Test detecting multiple mod imports."""
        mod = Mod(
            name="Script.ts4script",
            path=Path("Script.ts4script"),
            type=ModType.SCRIPT,
            size=2000,
            hash="def456",
        )

        script = ScriptModule(name="main.py", path="main.py")
        script.imports = {
            "mccc_module",
            "wonderfulwhims.core",
            "ui_cheats.extension",
            "sims4.commands",
        }
        mod.scripts.append(script)

        deps = detector._detect_script_dependencies(mod)

        assert len(deps) >= 3
        assert "MC Command Center" in deps
        assert "Wonderful Whims" in deps
        assert "UI Cheats Extension" in deps

    def test_no_script_imports(self, detector):
        """Test mod with no script imports."""
        mod = Mod(
            name="Script.ts4script",
            path=Path("Script.ts4script"),
            type=ModType.SCRIPT,
            size=2000,
            hash="def456",
        )

        deps = detector._detect_script_dependencies(mod)

        assert len(deps) == 0


class TestInjectionDependencies:
    """Test injection target detection."""

    def test_inject_to_pattern(self, detector):
        """Test detecting @inject_to decorator."""
        content = """
@inject_to(mccc.main, 'execute')
def my_function():
    pass
"""
        patterns = [r"@inject_to\(([^,]+)"]
        deps = detector._find_injection_targets(content, patterns)

        assert "MC Command Center" in deps

    def test_inject_pattern(self, detector):
        """Test detecting @inject decorator."""
        content = """
@inject(target_class=wickedwhims.core.Manager)
def patched_method():
    pass
"""
        patterns = [r"@inject\(([^)]+)\)"]
        deps = detector._find_injection_targets(content, patterns)

        assert "WickedWhims" in deps

    def test_multiple_injections(self, detector):
        """Test detecting multiple injection points."""
        content = """
@inject_to(mccc.main, 'execute')
def func1():
    pass

@inject(target=wonderfulwhims.core)
def func2():
    pass
"""
        patterns = [r"@inject_to\(([^,]+)", r"@inject\(([^)]+)\)"]
        deps = detector._find_injection_targets(content, patterns)

        assert len(deps) >= 2
        assert "MC Command Center" in deps
        assert "Wonderful Whims" in deps

    def test_no_injections(self, detector):
        """Test content with no injections."""
        content = """
def normal_function():
    pass
"""
        patterns = [r"@inject_to\(([^,]+)", r"@inject\(([^)]+)\)"]
        deps = detector._find_injection_targets(content, patterns)

        assert len(deps) == 0


class TestReadmeDependencies:
    """Test README dependency detection."""

    def test_extract_requires_pattern(self, detector):
        """Test extracting 'Requires:' pattern."""
        text = "Requires: MC Command Center v2024.1+"
        patterns = [r"requires?:?\s*([^\n]+)"]

        deps = detector._extract_dependencies_from_text(text, patterns)

        assert "MC Command Center" in deps

    def test_extract_dependencies_pattern(self, detector):
        """Test extracting 'Dependencies:' pattern."""
        text = "Dependencies: Wonderful Whims, Basemental Drugs"
        patterns = [r"dependencies?:?\s*([^\n]+)"]

        deps = detector._extract_dependencies_from_text(text, patterns)

        assert len(deps) >= 2
        assert "Wonderful Whims" in deps
        assert "Basemental Drugs" in deps

    def test_extract_with_and(self, detector):
        """Test extracting dependencies with 'and' separator."""
        text = "Depends on: MC Command Center and UI Cheats Extension"
        patterns = [r"depends on:?\s*([^\n]+)"]

        deps = detector._extract_dependencies_from_text(text, patterns)

        assert len(deps) >= 2
        assert "MC Command Center" in deps
        assert "UI Cheats Extension" in deps

    def test_remove_version_numbers(self, detector):
        """Test that version numbers are stripped."""
        text = "Requires: Wonderful Whims v1.5.0, Basemental v3.2+"
        patterns = [r"requires?:?\s*([^\n]+)"]

        deps = detector._extract_dependencies_from_text(text, patterns)

        # Should have mod names without versions
        assert "Wonderful Whims" in deps
        assert "Basemental Drugs" in deps

    def test_no_dependencies_in_text(self, detector):
        """Test text with no dependency declarations."""
        text = "This is a great mod that adds cool features!"
        patterns = [r"requires?:?\s*([^\n]+)", r"dependencies?:?\s*([^\n]+)"]

        deps = detector._extract_dependencies_from_text(text, patterns)

        assert len(deps) == 0


class TestFullDetection:
    """Test complete dependency detection."""

    def test_package_mod_full_detection(self, detector, package_mod):
        """Test full detection on package mod."""
        deps = detector.detect_dependencies(package_mod)

        # Should detect pack requirement
        assert "Get to Work" in deps

    def test_script_mod_full_detection(self, detector, script_mod_with_imports):
        """Test full detection on script mod."""
        deps = detector.detect_dependencies(script_mod_with_imports)

        # Should detect MCCC from imports
        assert "MC Command Center" in deps

    def test_hybrid_mod(self, detector):
        """Test detection on hybrid mod (package + script)."""
        mod = Mod(
            name="Hybrid.package",
            path=Path("Hybrid.package"),
            type=ModType.HYBRID,
            size=3000,
            hash="ghi789",
        )

        # Add pack requirement
        tuning = TuningData(
            instance_id=0x12345678,
            tuning_name="trait_Test",
            tuning_class="Trait",
            module="traits.trait_test",
        )
        tuning.pack_requirements = {"EP04"}  # Cats & Dogs
        mod.tunings.append(tuning)

        # Add script import
        script = ScriptModule(name="main.py", path="main.py")
        script.imports = {"mccc_module", "sims4.commands"}
        mod.scripts.append(script)

        deps = detector.detect_dependencies(mod)

        # Should detect both pack and mod dependency
        assert len(deps) >= 2
        assert "Cats & Dogs" in deps
        assert "MC Command Center" in deps

    def test_no_dependencies(self, detector):
        """Test mod with no dependencies."""
        mod = Mod(
            name="Standalone.package",
            path=Path("Standalone.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="abc123",
        )

        deps = detector.detect_dependencies(mod)

        assert len(deps) == 0


class TestBatchDetection:
    """Test detecting dependencies for multiple mods."""

    def test_detect_all_dependencies(self, detector, package_mod, script_mod_with_imports):
        """Test batch detection."""
        mods = [package_mod, script_mod_with_imports]

        all_deps = detector.detect_all_dependencies(mods)

        assert len(all_deps) == 2
        assert "TestMod.package" in all_deps
        assert "ScriptMod.ts4script" in all_deps

        # Check individual dependencies
        assert "Get to Work" in all_deps["TestMod.package"]
        assert "MC Command Center" in all_deps["ScriptMod.ts4script"]

    def test_only_includes_mods_with_dependencies(self, detector):
        """Test that only mods with dependencies are included."""
        mod_with_deps = Mod(
            name="WithDeps.package",
            path=Path("WithDeps.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="abc123",
        )
        tuning = TuningData(
            instance_id=0x12345678,
            tuning_name="trait_Test",
            tuning_class="Trait",
            module="traits.trait_test",
        )
        tuning.pack_requirements = {"EP01"}
        mod_with_deps.tunings.append(tuning)

        mod_without_deps = Mod(
            name="NoDeps.package",
            path=Path("NoDeps.package"),
            type=ModType.PACKAGE,
            size=1000,
            hash="def456",
        )

        mods = [mod_with_deps, mod_without_deps]
        all_deps = detector.detect_all_dependencies(mods)

        # Only mod with dependencies should be in result
        assert len(all_deps) == 1
        assert "WithDeps.package" in all_deps
        assert "NoDeps.package" not in all_deps


class TestKnownMods:
    """Test known mod database."""

    def test_mccc_variants(self, detector):
        """Test multiple MCCC naming variants."""
        test_modules = ["mccc_module", "mc_cmd_center.core", "mccc.main"]

        for module in test_modules:
            # Should match MC Command Center
            found = False
            for key, mod_name in detector.KNOWN_MODS.items():
                if key in module.lower():
                    found = True
                    assert mod_name == "MC Command Center"
                    break
            assert found, f"Failed to match {module}"

    def test_all_known_mods_present(self, detector):
        """Test that all major mods are in database."""
        required_mods = [
            "MC Command Center",
            "Basemental Drugs",
            "Wonderful Whims",
            "WickedWhims",
            "UI Cheats Extension",
        ]

        known_mod_names = set(detector.KNOWN_MODS.values())

        for mod in required_mods:
            assert mod in known_mod_names, f"{mod} not in KNOWN_MODS"

    def test_all_expansion_packs(self, detector):
        """Test that all major expansion packs are in database."""
        # Test a sample of packs
        pack_samples = [
            ("EP01", "Get to Work"),
            ("EP04", "Cats & Dogs"),
            ("EP08", "Discover University"),
            ("GP04", "Vampires"),
            ("SP13", "Laundry Day Stuff"),
        ]

        for code, name in pack_samples:
            assert code in detector.PACK_NAMES
            assert detector.PACK_NAMES[code] == name
