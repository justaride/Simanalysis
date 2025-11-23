"""Dependency detection for Sims 4 mods.

This module detects mod dependencies from various sources:
- Pack requirements in tuning XML
- Script imports
- Injection targets
- README/metadata files
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
import re
import zipfile

from simanalysis.models import Mod, ModType


class DependencyDetector:
    """Detect mod dependencies from various sources."""

    # Known popular mods and their import signatures
    KNOWN_MODS: Dict[str, str] = {
        "mccc": "MC Command Center",
        "mc_cmd_center": "MC Command Center",
        "basemental": "Basemental Drugs",
        "wonderfulwhims": "Wonderful Whims",
        "wickedwhims": "WickedWhims",
        "ui_cheats": "UI Cheats Extension",
        "better_exceptions": "Better Exceptions",
        "tmex": "TwistedMexi's Better BuildBuy",
        "go_to_school": "Go to School Mod",
        "slice_of_life": "Slice of Life",
        "extreme_violence": "Extreme Violence",
        "life_tragedies": "Life's Tragedies",
    }

    # Pack codes to full pack names
    PACK_NAMES: Dict[str, str] = {
        "EP01": "Get to Work",
        "EP02": "Get Together",
        "EP03": "City Living",
        "EP04": "Cats & Dogs",
        "EP05": "Seasons",
        "EP06": "Get Famous",
        "EP07": "Island Living",
        "EP08": "Discover University",
        "EP09": "Eco Lifestyle",
        "EP10": "Snowy Escape",
        "EP11": "Cottage Living",
        "EP12": "High School Years",
        "EP13": "Growing Together",
        "EP14": "Horse Ranch",
        "GP01": "Outdoor Retreat",
        "GP02": "Spa Day",
        "GP03": "Dine Out",
        "GP04": "Vampires",
        "GP05": "Parenthood",
        "GP06": "Jungle Adventure",
        "GP07": "StrangerVille",
        "GP08": "Realm of Magic",
        "GP09": "Journey to Batuu",
        "GP10": "Dream Home Decorator",
        "GP11": "My Wedding Stories",
        "GP12": "Werewolves",
        "SP01": "Luxury Party Stuff",
        "SP02": "Perfect Patio Stuff",
        "SP03": "Cool Kitchen Stuff",
        "SP04": "Spooky Stuff",
        "SP05": "Movie Hangout Stuff",
        "SP06": "Romantic Garden Stuff",
        "SP07": "Kids Room Stuff",
        "SP08": "Backyard Stuff",
        "SP09": "Vintage Glamour Stuff",
        "SP10": "Bowling Night Stuff",
        "SP11": "Fitness Stuff",
        "SP12": "Toddler Stuff",
        "SP13": "Laundry Day Stuff",
        "SP14": "My First Pet Stuff",
        "SP15": "Moschino Stuff",
        "SP16": "Tiny Living Stuff",
        "SP17": "Nifty Knitting Stuff",
        "SP18": "Paranormal Stuff",
        "SP19": "Throwback Fit Kit",
    }

    def detect_dependencies(self, mod: Mod) -> List[str]:
        """Detect all dependencies for a mod.

        Args:
            mod: Mod to analyze

        Returns:
            List of dependency names (may include pack names and mod names)

        Example:
            >>> detector = DependencyDetector()
            >>> deps = detector.detect_dependencies(my_mod)
            >>> print(deps)
            ['MC Command Center', 'Get to Work', 'Seasons']
        """
        dependencies: Set[str] = set()

        # From pack requirements in tuning
        dependencies.update(self._detect_pack_requirements(mod))

        # From script imports (for script mods)
        if mod.type in (ModType.SCRIPT, ModType.HYBRID):
            dependencies.update(self._detect_script_dependencies(mod))

        # From injection targets
        if mod.type in (ModType.SCRIPT, ModType.HYBRID):
            dependencies.update(self._detect_injection_dependencies(mod))

        # From README/metadata files
        if mod.type in (ModType.SCRIPT, ModType.HYBRID):
            dependencies.update(self._detect_readme_dependencies(mod))

        return sorted(list(dependencies))

    def _detect_pack_requirements(self, mod: Mod) -> Set[str]:
        """Detect pack requirements from tuning XML.

        Looks for patterns like:
        <T n="required_packs">EP01,GP02</T>
        <I n="required_packs" type="list">EP01,GP02</I>

        Args:
            mod: Mod to analyze

        Returns:
            Set of required pack names
        """
        pack_deps: Set[str] = set()

        # Check tuning data for pack requirements
        for tuning in mod.tunings:
            if hasattr(tuning, "pack_requirements") and tuning.pack_requirements:
                # pack_requirements is a Set[str]
                for code in tuning.pack_requirements:
                    code = code.strip()
                    if code in self.PACK_NAMES:
                        pack_deps.add(self.PACK_NAMES[code])

        return pack_deps

    def _detect_script_dependencies(self, mod: Mod) -> Set[str]:
        """Detect dependencies from Python imports.

        Looks for import patterns that match known mods:
        - import mccc_module
        - from basemental import drugs
        - import wonderfulwhims.core

        Args:
            mod: Mod to analyze

        Returns:
            Set of detected mod dependencies
        """
        dependencies: Set[str] = set()

        # Check script imports
        if not mod.scripts:
            return dependencies

        for script_module in mod.scripts:
            if not hasattr(script_module, "imports"):
                continue

            # imports is a Set[str]
            for import_module in script_module.imports:
                module_name = import_module.lower()

                # Check against known mods
                for key, mod_name in self.KNOWN_MODS.items():
                    if key in module_name:
                        dependencies.add(mod_name)
                        break

        return dependencies

    def _detect_injection_dependencies(self, mod: Mod) -> Set[str]:
        """Detect dependencies from injection decorators.

        Looks for patterns like:
        @inject_to(mccc.main, 'execute')
        @inject(target_class=wickedwhims.core)

        Args:
            mod: Mod to analyze

        Returns:
            Set of detected mod dependencies
        """
        dependencies: Set[str] = set()

        # Pattern to match injection decorators
        injection_patterns = [
            r"@inject_to\(([^,]+)",
            r"@inject\(([^)]+)\)",
            r"@wraps\(([^)]+)\)",
        ]

        # Check script files for injection patterns
        if mod.type not in (ModType.SCRIPT, ModType.HYBRID):
            return dependencies

        # Try to read script files from the mod
        try:
            if mod.path.suffix == ".ts4script":
                # It's a ZIP file
                with zipfile.ZipFile(mod.path, "r") as zf:
                    for file_info in zf.filelist:
                        if file_info.filename.endswith(".py"):
                            try:
                                content = zf.read(file_info.filename).decode("utf-8", errors="ignore")
                                dependencies.update(self._find_injection_targets(content, injection_patterns))
                            except Exception:
                                # Skip files that can't be read
                                continue
        except Exception:
            # Not a valid ZIP or can't read
            pass

        return dependencies

    def _find_injection_targets(self, content: str, patterns: List[str]) -> Set[str]:
        """Find injection targets in script content.

        Args:
            content: Python script content
            patterns: Regex patterns to search for

        Returns:
            Set of detected mod dependencies
        """
        dependencies: Set[str] = set()

        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                target = match.group(1).lower()

                # Check if target matches known mod
                for key, mod_name in self.KNOWN_MODS.items():
                    if key in target:
                        dependencies.add(mod_name)
                        break

        return dependencies

    def _detect_readme_dependencies(self, mod: Mod) -> Set[str]:
        """Detect dependencies from README or metadata files.

        Looks for patterns like:
        Requires: MC Command Center v2024.1+
        Dependencies: Wonderful Whims, Basemental Drugs
        Optional: UI Cheats Extension

        Args:
            mod: Mod to analyze

        Returns:
            Set of detected mod dependencies
        """
        dependencies: Set[str] = set()

        if mod.type not in (ModType.SCRIPT, ModType.HYBRID):
            return dependencies

        # Patterns to find dependency declarations
        dependency_patterns = [
            r"requires?:?\s*([^\n]+)",
            r"dependencies?:?\s*([^\n]+)",
            r"depends on:?\s*([^\n]+)",
            r"needs:?\s*([^\n]+)",
        ]

        try:
            if mod.path.suffix == ".ts4script":
                with zipfile.ZipFile(mod.path, "r") as zf:
                    # Look for README files
                    readme_files = [
                        f for f in zf.filelist
                        if any(name in f.filename.lower() for name in ["readme", "dependencies", "requirements"])
                    ]

                    for readme_file in readme_files:
                        try:
                            content = zf.read(readme_file.filename).decode("utf-8", errors="ignore")
                            dependencies.update(self._extract_dependencies_from_text(content, dependency_patterns))
                        except Exception:
                            continue
        except Exception:
            pass

        return dependencies

    def _extract_dependencies_from_text(self, text: str, patterns: List[str]) -> Set[str]:
        """Extract dependency names from text using patterns.

        Args:
            text: Text content to search
            patterns: Regex patterns to match

        Returns:
            Set of detected mod dependencies
        """
        dependencies: Set[str] = set()

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                deps_line = match.group(1)

                # Split by comma or 'and'
                dep_names = re.split(r",|\s+and\s+", deps_line)

                for dep in dep_names:
                    # Clean up and normalize
                    dep = dep.strip()
                    dep = re.sub(r"\s*v?[\d.]+\+?$", "", dep)  # Remove version numbers

                    # Check if it matches a known mod
                    dep_lower = dep.lower()
                    for key, mod_name in self.KNOWN_MODS.items():
                        if key in dep_lower or dep_lower in mod_name.lower():
                            dependencies.add(mod_name)
                            break

        return dependencies

    def detect_all_dependencies(self, mods: List[Mod]) -> Dict[str, List[str]]:
        """Detect dependencies for multiple mods.

        Args:
            mods: List of mods to analyze

        Returns:
            Dictionary mapping mod name to list of dependencies

        Example:
            >>> detector = DependencyDetector()
            >>> all_deps = detector.detect_all_dependencies(mods)
            >>> print(all_deps)
            {
                'CustomMod.package': ['MC Command Center', 'Seasons'],
                'AnotherMod.ts4script': ['Wonderful Whims']
            }
        """
        result: Dict[str, List[str]] = {}

        for mod in mods:
            dependencies = self.detect_dependencies(mod)
            if dependencies:  # Only include mods with dependencies
                result[mod.name] = dependencies

        return result
