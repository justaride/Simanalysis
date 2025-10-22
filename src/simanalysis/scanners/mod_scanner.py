"""Scanner for discovering and categorizing Sims 4 mods."""

import hashlib
from pathlib import Path
from typing import List, Optional, Set

from simanalysis.exceptions import SimanalysisError
from simanalysis.models import Mod, ModType
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.script import ScriptAnalyzer
from simanalysis.parsers.tuning import TuningParser


class ModScanner:
    """
    Scanner for discovering and analyzing Sims 4 mods.

    Recursively scans directories for .package and .ts4script files,
    parses their contents, and returns Mod objects ready for analysis.

    Example:
        >>> scanner = ModScanner()
        >>> mods = scanner.scan_directory(Path("/Mods"))
        >>> print(f"Found {len(mods)} mods")
        >>> print(f"{len([m for m in mods if m.type == ModType.PACKAGE])} packages")
    """

    def __init__(
        self,
        parse_tunings: bool = True,
        parse_scripts: bool = True,
        calculate_hashes: bool = True,
    ) -> None:
        """
        Initialize mod scanner.

        Args:
            parse_tunings: Whether to parse XML tunings from packages
            parse_scripts: Whether to analyze script files
            calculate_hashes: Whether to calculate file hashes
        """
        self.parse_tunings = parse_tunings
        self.parse_scripts = parse_scripts
        self.calculate_hashes = calculate_hashes
        self.mods_scanned = 0
        self.errors_encountered: List[tuple[Path, str]] = []

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[Set[str]] = None,
    ) -> List[Mod]:
        """
        Scan directory for mods.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan (default: .package, .ts4script)

        Returns:
            List of discovered mods

        Raises:
            SimanalysisError: If directory doesn't exist or isn't accessible
        """
        if not directory.exists():
            raise SimanalysisError(f"Directory not found: {directory}")

        if not directory.is_dir():
            raise SimanalysisError(f"Not a directory: {directory}")

        # Default extensions
        if extensions is None:
            extensions = {".package", ".ts4script"}

        mods: List[Mod] = []
        self.mods_scanned = 0
        self.errors_encountered = []

        # Find all mod files
        files = self._find_mod_files(directory, recursive, extensions)

        # Scan each file
        for file_path in files:
            try:
                mod = self.scan_file(file_path)
                if mod:
                    mods.append(mod)
                    self.mods_scanned += 1
            except Exception as e:
                self.errors_encountered.append((file_path, str(e)))

        return mods

    def scan_file(self, file_path: Path) -> Optional[Mod]:
        """
        Scan a single mod file.

        Args:
            file_path: Path to mod file

        Returns:
            Mod object or None if file couldn't be parsed
        """
        if not file_path.exists():
            return None

        # Determine mod type
        if file_path.suffix.lower() == ".package":
            return self._scan_package(file_path)
        elif file_path.suffix.lower() == ".ts4script":
            return self._scan_script(file_path)
        else:
            return None

    def _find_mod_files(
        self, directory: Path, recursive: bool, extensions: Set[str]
    ) -> List[Path]:
        """
        Find all mod files in directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            extensions: File extensions to find

        Returns:
            List of file paths
        """
        files: List[Path] = []

        if recursive:
            for ext in extensions:
                files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in extensions:
                files.extend(directory.glob(f"*{ext}"))

        return sorted(files)

    def _scan_package(self, file_path: Path) -> Optional[Mod]:
        """
        Scan a .package file.

        Args:
            file_path: Path to package file

        Returns:
            Mod object or None
        """
        try:
            # Read DBPF package
            reader = DBPFReader(file_path)

            # Get basic info
            size = file_path.stat().st_size
            file_hash = self._calculate_hash(file_path) if self.calculate_hashes else None

            # Get resources
            resources = reader.resources

            # Parse tunings if enabled
            tunings = []
            if self.parse_tunings:
                tunings = self._extract_tunings(reader)

            # Detect pack requirements from tunings
            pack_requirements: Set[str] = set()
            for tuning in tunings:
                pack_requirements.update(tuning.pack_requirements)

            # Create mod
            mod = Mod(
                name=file_path.name,
                path=file_path,
                type=ModType.PACKAGE,
                size=size,
                hash=file_hash,
                resources=resources,
                tunings=tunings,
                scripts=[],
                pack_requirements=pack_requirements,
            )

            return mod

        except Exception:
            # Return minimal mod on parse error
            return Mod(
                name=file_path.name,
                path=file_path,
                type=ModType.PACKAGE,
                size=file_path.stat().st_size,
                hash=None,
                resources=[],
                tunings=[],
                scripts=[],
            )

    def _scan_script(self, file_path: Path) -> Optional[Mod]:
        """
        Scan a .ts4script file.

        Args:
            file_path: Path to script file

        Returns:
            Mod object or None
        """
        try:
            # Analyze script
            analyzer = ScriptAnalyzer(file_path)

            # Get basic info
            size = file_path.stat().st_size
            file_hash = self._calculate_hash(file_path) if self.calculate_hashes else None

            # Get metadata
            metadata = analyzer.metadata

            # Analyze modules if enabled
            scripts = []
            requires = []
            if self.parse_scripts:
                module_paths = analyzer.module_paths
                for module_path in module_paths:
                    try:
                        script_module = analyzer.analyze_module(module_path)
                        scripts.append(script_module)

                        # Collect requirements
                        if hasattr(script_module, "imports"):
                            for imp in script_module.imports:
                                # Look for common dependency patterns
                                if "sims4communitylib" in imp.lower():
                                    requires.append("Sims4CommunityLibrary")

                    except Exception:
                        # Skip modules that fail to parse
                        pass

            # Create mod
            mod = Mod(
                name=file_path.name,
                path=file_path,
                type=ModType.SCRIPT,
                size=size,
                hash=file_hash,
                resources=[],
                tunings=[],
                scripts=scripts,
                version=metadata.get("version"),
                author=metadata.get("author"),
                requires=list(set(requires)),  # Deduplicate
            )

            return mod

        except Exception:
            # Return minimal mod on parse error
            return Mod(
                name=file_path.name,
                path=file_path,
                type=ModType.SCRIPT,
                size=file_path.stat().st_size,
                hash=None,
                resources=[],
                tunings=[],
                scripts=[],
            )

    def _extract_tunings(self, reader: DBPFReader) -> List:
        """
        Extract tuning data from DBPF package.

        Args:
            reader: DBPF reader instance

        Returns:
            List of TuningData objects
        """
        tunings = []
        parser = TuningParser()

        # Find XML tuning resources (type 0x62766556 or 0x220557DA)
        xml_types = {0x62766556, 0x220557DA}

        for resource in reader.resources:
            if resource.type in xml_types:
                try:
                    # Get resource data
                    data = reader.get_resource(resource)

                    # Parse XML
                    tuning = parser.parse(data)
                    tunings.append(tuning)

                except Exception:
                    # Skip resources that fail to parse
                    pass

        return tunings

    def _calculate_hash(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string
        """
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            # Read in chunks for memory efficiency
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()

    def get_scan_summary(self) -> dict:
        """
        Get summary of last scan.

        Returns:
            Dictionary with scan statistics
        """
        return {
            "mods_scanned": self.mods_scanned,
            "errors_encountered": len(self.errors_encountered),
            "error_details": self.errors_encountered,
        }
