"""Scanner for discovering and categorizing Sims 4 mods."""

import hashlib
from pathlib import Path
from typing import Callable, Optional

from simanalysis.exceptions import SimanalysisError
from simanalysis.formats.types import STBL, is_tuning_type
from simanalysis.models import Mod, ModType, StringTableData
from simanalysis.parsers.dbpf import DBPFReader
from simanalysis.parsers.script import ScriptAnalyzer
from simanalysis.parsers.stbl import STBLParser
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
        parse_string_tables: bool = True,
        calculate_hashes: bool = True,
    ) -> None:
        """
        Initialize mod scanner.

        Args:
            parse_tunings: Whether to parse XML tunings from packages
            parse_scripts: Whether to analyze script files
            parse_string_tables: Whether to parse STBL string table resources
            calculate_hashes: Whether to calculate file hashes
        """
        self.parse_tunings = parse_tunings
        self.parse_scripts = parse_scripts
        self.parse_string_tables = parse_string_tables
        self.calculate_hashes = calculate_hashes
        self.mods_scanned = 0
        self.errors_encountered: list[tuple[Path, str]] = []

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
        extensions: Optional[set[str]] = None,
        progress_callback: Optional["Callable[[int, int, str], None]"] = None,
    ) -> list[Mod]:
        """
        Scan directory for mods.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            extensions: File extensions to scan (default: .package, .ts4script)
            progress_callback: Optional callback (current, total, filename)

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

        mods: list[Mod] = []
        self.mods_scanned = 0
        self.errors_encountered = []

        # Find all mod files
        if progress_callback:
            progress_callback(0, 0, "Discovering files...")

        files = self._find_mod_files(directory, recursive, extensions)
        total_files = len(files)

        # Batch processing configuration
        batch_size = 50

        import time

        # Scan each file
        for i, file_path in enumerate(files, 1):
            # Yield to other threads every batch
            if i % batch_size == 0:
                time.sleep(0.01)

            if progress_callback:
                progress_callback(i, total_files, file_path.name)

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

    def _find_mod_files(self, directory: Path, recursive: bool, extensions: set[str]) -> list[Path]:
        """
        Find all mod files in directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories
            extensions: File extensions to find

        Returns:
            List of file paths
        """
        files: list[Path] = []

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

            # Parse STBL string tables if enabled
            string_tables = []
            if self.parse_string_tables:
                string_tables = self._extract_string_tables(reader)

            # Detect pack requirements from tunings
            pack_requirements: set[str] = set()
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
                string_tables=string_tables,
                pack_requirements=pack_requirements,
            )

            return mod

        except Exception as e:
            # Log error but return minimal mod for graceful degradation
            self.errors_encountered.append((file_path, f"Package parse error: {e}"))
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

                    except Exception:  # nosec B110 - skip modules that fail to parse
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
                version=metadata.version,
                author=metadata.author,
                requires=list(set(requires)),  # Deduplicate
            )

            return mod

        except Exception as e:
            # Log error but return minimal mod for graceful degradation
            self.errors_encountered.append((file_path, f"Script parse error: {e}"))
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

    def _extract_tunings(self, reader: DBPFReader) -> list:
        """
        Extract tuning data from DBPF package.

        Args:
            reader: DBPF reader instance

        Returns:
            List of TuningData objects
        """
        tunings = []
        parser = TuningParser()

        for resource in reader.resources:
            if is_tuning_type(resource.type):
                try:
                    # Get resource data
                    data = reader.get_resource(resource)

                    # Parse XML
                    tuning = parser.parse(data)
                    tunings.append(tuning)

                except Exception:  # nosec B110 - skip resources that fail to parse
                    # Skip resources that fail to parse
                    pass

        return tunings

    def _extract_string_tables(self, reader: DBPFReader) -> list[StringTableData]:
        """
        Extract STBL string tables from a DBPF package.

        Args:
            reader: DBPF reader instance

        Returns:
            List of parsed STBL resources, including degraded parse statuses
        """
        string_tables: list[StringTableData] = []

        for resource in reader.get_resources_by_type(int(STBL)):
            try:
                data = reader.get_resource(resource)
                table = STBLParser.parse(data)
            except Exception as e:  # nosec B110 - keep package scans non-fatal
                table = StringTableData(
                    version=0,
                    parse_status="malformed",
                    warnings=[f"Failed to read STBL resource: {e}"],
                )

            table.resource_group = resource.group
            table.resource_instance = resource.instance
            string_tables.append(table)

        return string_tables

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
            "error_details": [(str(path), msg) for path, msg in self.errors_encountered],
        }
