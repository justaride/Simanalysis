"""Tests for TS4Script analyzer."""

import zipfile
from pathlib import Path

import pytest

from simanalysis.exceptions import ScriptError
from simanalysis.models import ScriptMetadata, ScriptModule
from simanalysis.parsers.script import ScriptAnalyzer


class TestScriptAnalyzer:
    """Tests for ScriptAnalyzer class."""

    @pytest.fixture
    def simple_script_file(self, tmp_path: Path) -> Path:
        """Create a simple valid ts4script file."""
        script_file = tmp_path / "test_mod.ts4script"

        # Create a ZIP file
        with zipfile.ZipFile(script_file, "w") as zf:
            # Add metadata file
            metadata_content = """Name: Test Mod
Version: 1.0.0
Author: Test Author
"""
            zf.writestr("metadata.txt", metadata_content)

            # Add a simple Python module
            module_content = """# Simple module
import sims4
from sims4.commands import Command

def test_function():
    pass

class TestClass:
    def method(self):
        if True:
            pass
"""
            zf.writestr("test_module.py", module_content)

        return script_file

    @pytest.fixture
    def script_with_hooks(self, tmp_path: Path) -> Path:
        """Create a script with game hooks."""
        script_file = tmp_path / "hooks_mod.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            module_content = """import sims4
from sims4.utils import inject_to

@inject_to(TargetClass, 'target_method')
def my_injection(original, self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    return result

def wrap_function(target):
    pass

class ModClass:
    def override(self):
        pass
"""
            zf.writestr("hooks_module.py", module_content)

        return script_file

    @pytest.fixture
    def complex_script(self, tmp_path: Path) -> Path:
        """Create a complex script with multiple modules."""
        script_file = tmp_path / "complex_mod.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            # __init__.py with metadata in docstring
            init_content = '''"""
Complex Mod
Author: Complex Author
Version: 2.5.0
"""
import sys
from . import submodule
'''
            zf.writestr("__init__.py", init_content)

            # Submodule
            sub_content = """import sims4
from sims4.tuning import TunableFactory

class ComplexClass:
    def method1(self):
        for i in range(10):
            if i % 2 == 0:
                try:
                    pass
                except Exception:
                    pass

    def method2(self):
        while True:
            break
"""
            zf.writestr("submodule.py", sub_content)

            # requirements.txt
            requirements = """sims4
# Comment
somepackage>=1.0
"""
            zf.writestr("requirements.txt", requirements)

        return script_file

    @pytest.fixture
    def invalid_script(self, tmp_path: Path) -> Path:
        """Create an invalid (non-ZIP) file."""
        script_file = tmp_path / "invalid.ts4script"
        script_file.write_text("This is not a ZIP file")
        return script_file

    @pytest.fixture
    def script_with_syntax_error(self, tmp_path: Path) -> Path:
        """Create a script with syntax errors."""
        script_file = tmp_path / "syntax_error.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            module_content = """import sims4
def broken_function(
    # Missing closing parenthesis
    pass
"""
            zf.writestr("broken.py", module_content)

        return script_file

    def test_init_nonexistent_file(self) -> None:
        """Test initialization with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            ScriptAnalyzer("/nonexistent/script.ts4script")

    def test_init_directory(self, tmp_path: Path) -> None:
        """Test initialization with directory."""
        with pytest.raises(ScriptError, match="Path is not a file"):
            ScriptAnalyzer(tmp_path)

    def test_init_invalid_zip(self, invalid_script: Path) -> None:
        """Test initialization with non-ZIP file."""
        with pytest.raises(ScriptError, match="not a valid ZIP archive"):
            ScriptAnalyzer(invalid_script)

    def test_extract_metadata_simple(self, simple_script_file: Path) -> None:
        """Test extracting metadata from simple script."""
        analyzer = ScriptAnalyzer(simple_script_file)
        metadata = analyzer.extract_metadata()

        assert isinstance(metadata, ScriptMetadata)
        assert metadata.name == "Test Mod"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Test Author"
        assert metadata.python_version == "3.7"

    def test_extract_metadata_from_init(self, complex_script: Path) -> None:
        """Test extracting metadata from __init__.py docstring."""
        analyzer = ScriptAnalyzer(complex_script)
        metadata = analyzer.extract_metadata()

        assert "Complex Author" in metadata.author or metadata.author == "unknown"

    def test_extract_requirements(self, complex_script: Path) -> None:
        """Test extracting requirements from requirements.txt."""
        analyzer = ScriptAnalyzer(complex_script)
        metadata = analyzer.extract_metadata()

        assert len(metadata.requires) > 0
        assert "sims4" in metadata.requires
        assert "somepackage>=1.0" in metadata.requires

    def test_metadata_fallback_to_filename(self, tmp_path: Path) -> None:
        """Test metadata falls back to filename when no metadata found."""
        script_file = tmp_path / "my_awesome_mod.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            zf.writestr("dummy.py", "# No metadata")

        analyzer = ScriptAnalyzer(script_file)
        metadata = analyzer.extract_metadata()

        assert metadata.name == "my_awesome_mod"
        assert metadata.version == "unknown"
        assert metadata.author == "unknown"

    def test_list_modules(self, simple_script_file: Path) -> None:
        """Test listing modules in script."""
        analyzer = ScriptAnalyzer(simple_script_file)
        modules = analyzer.list_modules()

        assert len(modules) == 1
        assert isinstance(modules[0], ScriptModule)
        assert modules[0].name == "test_module.py"

    def test_list_multiple_modules(self, complex_script: Path) -> None:
        """Test listing multiple modules."""
        analyzer = ScriptAnalyzer(complex_script)
        modules = analyzer.list_modules()

        assert len(modules) >= 2
        module_names = [m.name for m in modules]
        assert "__init__.py" in module_names
        assert "submodule.py" in module_names

    def test_analyze_module_imports(self, simple_script_file: Path) -> None:
        """Test extracting imports from module."""
        analyzer = ScriptAnalyzer(simple_script_file)
        modules = analyzer.list_modules()

        module = modules[0]
        assert "sims4" in module.imports
        assert "sims4.commands" in module.imports

    def test_detect_hooks(self, script_with_hooks: Path) -> None:
        """Test detecting game hooks."""
        analyzer = ScriptAnalyzer(script_with_hooks)
        modules = analyzer.list_modules()

        module = modules[0]
        assert len(module.hooks) > 0
        # Should detect inject_to and wrap_function
        assert any("inject" in hook for hook in module.hooks)

    def test_detect_decorator_hooks(self, script_with_hooks: Path) -> None:
        """Test detecting decorator-based hooks."""
        analyzer = ScriptAnalyzer(script_with_hooks)
        modules = analyzer.list_modules()

        module = modules[0]
        # Should detect @inject_to decorator
        assert any("@inject" in hook for hook in module.hooks)

    def test_calculate_complexity(self, complex_script: Path) -> None:
        """Test calculating code complexity."""
        analyzer = ScriptAnalyzer(complex_script)
        modules = analyzer.list_modules()

        # Find submodule (should have higher complexity)
        submodule = next(m for m in modules if "submodule" in m.name)

        assert submodule.complexity > 0
        # Should count: class, methods, for, if, try, while
        assert submodule.complexity >= 6

    def test_handle_syntax_error(self, script_with_syntax_error: Path) -> None:
        """Test handling modules with syntax errors."""
        analyzer = ScriptAnalyzer(script_with_syntax_error)
        modules = analyzer.list_modules()

        # Should still return module, but with basic info
        assert len(modules) == 1
        module = modules[0]
        assert module.name == "broken.py"
        assert module.complexity == 0  # Can't calculate for broken code

    def test_lazy_loading_metadata(self, simple_script_file: Path) -> None:
        """Test that metadata is lazy loaded."""
        analyzer = ScriptAnalyzer(simple_script_file)

        # Metadata should not be loaded yet
        assert analyzer._metadata is None

        # Access metadata property
        metadata = analyzer.metadata

        # Metadata should now be loaded
        assert analyzer._metadata is not None
        assert metadata.name == "Test Mod"

        # Accessing again should return cached metadata
        metadata2 = analyzer.metadata
        assert metadata is metadata2

    def test_lazy_loading_modules(self, simple_script_file: Path) -> None:
        """Test that modules are lazy loaded."""
        analyzer = ScriptAnalyzer(simple_script_file)

        # Modules should not be loaded yet
        assert analyzer._modules is None

        # Access modules property
        modules = analyzer.modules

        # Modules should now be loaded
        assert analyzer._modules is not None
        assert len(modules) == 1

        # Accessing again should return cached modules
        modules2 = analyzer.modules
        assert modules is modules2

    def test_no_pyc_files_analyzed(self, tmp_path: Path) -> None:
        """Test that .pyc files are not analyzed (only .py)."""
        script_file = tmp_path / "with_pyc.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            zf.writestr("module.py", "# Python source")
            zf.writestr("module.pyc", b"\x00\x00\x00\x00")  # Bytecode

        analyzer = ScriptAnalyzer(script_file)
        modules = analyzer.list_modules()

        # Should only find .py file
        assert len(modules) == 1
        assert modules[0].name == "module.py"

    def test_empty_script(self, tmp_path: Path) -> None:
        """Test script with no Python files."""
        script_file = tmp_path / "empty.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            zf.writestr("README.md", "# Empty mod")

        analyzer = ScriptAnalyzer(script_file)
        modules = analyzer.list_modules()

        assert len(modules) == 0

    def test_hook_patterns_constant(self) -> None:
        """Test that HOOK_PATTERNS is defined."""
        assert len(ScriptAnalyzer.HOOK_PATTERNS) > 0
        assert "inject_to" in ScriptAnalyzer.HOOK_PATTERNS
        assert "wrap_function" in ScriptAnalyzer.HOOK_PATTERNS

    def test_multiple_imports_formats(self, tmp_path: Path) -> None:
        """Test extracting various import formats."""
        script_file = tmp_path / "imports.ts4script"

        with zipfile.ZipFile(script_file, "w") as zf:
            module_content = """import sims4
import sims4.commands
from sims4.tuning import TunableFactory
from sims4.utils import *
import sys, os
"""
            zf.writestr("imports.py", module_content)

        analyzer = ScriptAnalyzer(script_file)
        modules = analyzer.list_modules()

        imports = modules[0].imports
        assert "sims4" in imports
        assert "sims4.commands" in imports
        assert "sims4.tuning" in imports
        assert "sims4.utils" in imports
        assert "sys" in imports
        assert "os" in imports
