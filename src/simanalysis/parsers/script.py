"""TS4Script analyzer for Sims 4 Python script mods.

TS4Script files are ZIP archives containing Python (.py and .pyc) files.
This module provides tools to analyze these scripts for:
- Metadata (name, version, author)
- Module structure
- Import dependencies
- Game hooks and injections
- Code complexity
"""

import ast
import zipfile
from pathlib import Path
from typing import List, Set, Optional

from simanalysis.exceptions import ScriptError
from simanalysis.models import ScriptMetadata, ScriptModule


class ScriptAnalyzer:
    """
    Analyzer for Sims 4 .ts4script files.

    TS4Script files are ZIP archives containing Python code.
    The Sims 4 uses Python 3.7 for scripting.

    This analyzer extracts:
    - Script metadata (name, version, author)
    - Module list
    - Import dependencies
    - Game injection points (hooks)
    - Code complexity metrics

    Example:
        >>> analyzer = ScriptAnalyzer("my_script.ts4script")
        >>> metadata = analyzer.extract_metadata()
        >>> modules = analyzer.list_modules()
        >>> print(f"Found {len(modules)} modules")
    """

    # Common game hook patterns in Sims 4 mods
    HOOK_PATTERNS = [
        "inject_to",
        "wrap_function",
        "override",
        "inject",
        "event.register",
        "listener",
        "@inject_to",
        "@wrap",
    ]

    def __init__(self, script_path: Path | str) -> None:
        """
        Initialize script analyzer.

        Args:
            script_path: Path to .ts4script file

        Raises:
            FileNotFoundError: If script file doesn't exist
            ScriptError: If file is not a valid ZIP archive
        """
        self.path = Path(script_path)

        if not self.path.exists():
            raise FileNotFoundError(f"Script file not found: {self.path}")

        if not self.path.is_file():
            raise ScriptError(f"Path is not a file: {self.path}")

        # Verify it's a valid ZIP archive
        if not zipfile.is_zipfile(self.path):
            raise ScriptError(f"File is not a valid ZIP archive: {self.path}")

        self._metadata: Optional[ScriptMetadata] = None
        self._modules: Optional[List[ScriptModule]] = None

    def extract_metadata(self) -> ScriptMetadata:
        """
        Extract script metadata.

        Looks for metadata in:
        - __init__.py docstrings
        - metadata.txt file
        - README.md file
        - Inferred from filename

        Returns:
            ScriptMetadata with extracted information
        """
        name = self._extract_name()
        version = self._extract_version()
        author = self._extract_author()
        requires = self._extract_requirements()

        metadata = ScriptMetadata(
            name=name,
            version=version,
            author=author,
            requires=requires,
            python_version="3.7",  # Sims 4 uses Python 3.7
        )

        self._metadata = metadata
        return metadata

    def _extract_name(self) -> str:
        """Extract script name from various sources."""
        # Try to find name in metadata file
        with zipfile.ZipFile(self.path, "r") as zf:
            # Look for common metadata files
            for filename in ["metadata.txt", "README.md", "__init__.py"]:
                try:
                    content = zf.read(filename).decode("utf-8", errors="ignore")
                    # Look for "Name:" or "# Name:" patterns
                    for line in content.split("\n")[:20]:  # First 20 lines
                        if "name:" in line.lower():
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                return parts[1].strip().strip('"\'')
                except KeyError:
                    continue

        # Fallback to filename
        return self.path.stem

    def _extract_version(self) -> str:
        """Extract script version."""
        with zipfile.ZipFile(self.path, "r") as zf:
            # Look for version in metadata files
            for filename in ["metadata.txt", "README.md", "__init__.py"]:
                try:
                    content = zf.read(filename).decode("utf-8", errors="ignore")
                    for line in content.split("\n")[:20]:
                        if "version:" in line.lower():
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                return parts[1].strip().strip('"\'')
                except KeyError:
                    continue

        return "unknown"

    def _extract_author(self) -> str:
        """Extract script author."""
        with zipfile.ZipFile(self.path, "r") as zf:
            # Look for author in metadata files
            for filename in ["metadata.txt", "README.md", "__init__.py"]:
                try:
                    content = zf.read(filename).decode("utf-8", errors="ignore")
                    for line in content.split("\n")[:20]:
                        if "author:" in line.lower() or "creator:" in line.lower():
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                return parts[1].strip().strip('"\'')
                except KeyError:
                    continue

        return "unknown"

    def _extract_requirements(self) -> List[str]:
        """Extract script requirements/dependencies."""
        requires: List[str] = []

        with zipfile.ZipFile(self.path, "r") as zf:
            # Look for requirements
            if "requirements.txt" in zf.namelist():
                try:
                    content = zf.read("requirements.txt").decode("utf-8")
                    for line in content.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("#"):
                            requires.append(line)
                except Exception:
                    pass

        return requires

    def list_modules(self) -> List[ScriptModule]:
        """
        List all Python modules in the script.

        Returns:
            List of ScriptModule objects

        Raises:
            ScriptError: If modules cannot be read
        """
        modules: List[ScriptModule] = []

        try:
            with zipfile.ZipFile(self.path, "r") as zf:
                for filename in zf.namelist():
                    # Only process .py files (not .pyc)
                    if filename.endswith(".py"):
                        try:
                            module = self.analyze_module(filename)
                            modules.append(module)
                        except Exception as e:
                            # Skip modules that can't be analyzed
                            # (They might be bytecode-only or corrupted)
                            continue

        except Exception as e:
            raise ScriptError(f"Failed to list modules: {e}") from e

        self._modules = modules
        return modules

    def analyze_module(self, module_path: str) -> ScriptModule:
        """
        Analyze a specific Python module.

        Args:
            module_path: Path to module within ZIP

        Returns:
            ScriptModule with analyzed information

        Raises:
            ScriptError: If module cannot be analyzed
        """
        try:
            with zipfile.ZipFile(self.path, "r") as zf:
                # Read module source code
                source = zf.read(module_path).decode("utf-8", errors="ignore")

                # Parse with AST
                try:
                    tree = ast.parse(source)
                except SyntaxError:
                    # If parsing fails, return basic info
                    return ScriptModule(
                        name=module_path,
                        path=module_path,
                        imports=set(),
                        hooks=[],
                        complexity=0,
                    )

                # Extract information
                imports = self._extract_imports(tree)
                hooks = self.detect_hooks(tree, source)
                complexity = self.calculate_complexity(tree)

                return ScriptModule(
                    name=module_path,
                    path=module_path,
                    imports=imports,
                    hooks=hooks,
                    complexity=complexity,
                )

        except Exception as e:
            raise ScriptError(f"Failed to analyze module {module_path}: {e}") from e

    def _extract_imports(self, tree: ast.AST) -> Set[str]:
        """Extract import statements from AST."""
        imports: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        return imports

    def detect_hooks(self, tree: ast.AST, source: str) -> List[str]:
        """
        Detect game injection points (hooks).

        Args:
            tree: AST of the module
            source: Source code text

        Returns:
            List of detected hook patterns
        """
        hooks: List[str] = []

        # Check for common hook patterns in source
        for pattern in self.HOOK_PATTERNS:
            if pattern in source:
                hooks.append(pattern)

        # Check for decorator-based hooks
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        decorator_name = decorator.id
                        if any(hook in decorator_name for hook in ["inject", "wrap", "override"]):
                            hooks.append(f"@{decorator_name}")
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Name):
                            decorator_name = decorator.func.id
                            if any(hook in decorator_name for hook in ["inject", "wrap", "override"]):
                                hooks.append(f"@{decorator_name}")

        # Remove duplicates while preserving order
        seen = set()
        unique_hooks = []
        for hook in hooks:
            if hook not in seen:
                seen.add(hook)
                unique_hooks.append(hook)

        return unique_hooks

    def calculate_complexity(self, tree: ast.AST) -> int:
        """
        Calculate cyclomatic complexity of the module.

        This is a simplified complexity metric based on:
        - Number of functions
        - Number of classes
        - Number of conditionals (if, while, for)
        - Number of try/except blocks

        Args:
            tree: AST of the module

        Returns:
            Complexity score (higher = more complex)
        """
        complexity = 0

        for node in ast.walk(tree):
            # Functions and classes
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity += 1
            elif isinstance(node, ast.ClassDef):
                complexity += 2  # Classes are more complex

            # Control flow
            elif isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, (ast.Try, ast.ExceptHandler)):
                complexity += 1

            # Boolean operations add complexity
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

        return complexity

    @property
    def metadata(self) -> ScriptMetadata:
        """
        Get metadata (lazy loaded).

        Returns:
            ScriptMetadata
        """
        if self._metadata is None:
            self._metadata = self.extract_metadata()
        return self._metadata

    @property
    def modules(self) -> List[ScriptModule]:
        """
        Get modules (lazy loaded).

        Returns:
            List of ScriptModule
        """
        if self._modules is None:
            self._modules = self.list_modules()
        return self._modules
