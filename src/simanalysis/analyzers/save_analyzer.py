"""Analyzer for matching save file CC references to installed mods."""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from simanalysis import __version__
from simanalysis.scanners.save_scanner import SaveScanner, SaveData, ResourceKey
from simanalysis.scanners.mod_scanner import ModScanner, Mod


@dataclass
class ModFile:
    """Information about a mod file."""
    path: Path
    name: str
    size: int
    resource_count: int
    is_used: bool
    matching_resources: Set[ResourceKey]


class SaveAnalysisResult:
    """Result of analyzing a save file against installed mods."""
    
    def __init__(
        self,
        save_data: SaveData,
        mods_directory: str,
        scan_duration: float,
    ):
        self.save_data = save_data
        self.mods_directory = mods_directory
        self.scan_duration = scan_duration
        self.timestamp = datetime.now()
        self.version = __version__
        
        # Analysis results
        self.used_mods: List[ModFile] = []
        self.unused_mods: List[ModFile] = []
        self.missing_resources: Set[ResourceKey] = set()
        
        # Statistics
        self.total_mods = 0
        self.total_used_size = 0
        self.total_unused_size = 0
        self.coverage_percentage = 0.0  # % of save refs that were matched


class SaveAnalyzer:
    """
    Analyzer for Sims 4 save files.
    
    Matches CC references in a save file to actual mod files
    to determine which mods are actually used.
    """
    
    def __init__(self) -> None:
        self.save_scanner = SaveScanner()
        self.mod_scanner = ModScanner(parse_tunings=False, calculate_hashes=False)
    
    def analyze_save(
        self,
        save_path: Path,
        mods_path: Path,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> SaveAnalysisResult:
        """
        Analyze a save file and match to installed mods.
        
        Args:
            save_path: Path to the .save file
            mods_path: Path to Mods folder
            progress_callback: Optional callback(stage, current, total)
            
        Returns:
            SaveAnalysisResult with matched mods
        """
        start_time = time.time()
        
        # Step 1: Parse save file
        if progress_callback:
            progress_callback("Scanning save file", 0, 3)
        
        save_data = self.save_scanner.scan_save_file(save_path)
        
        # Step 2: Scan mods folder
        if progress_callback:
            progress_callback("Scanning Mods folder", 1, 3)
        
        mods = self.mod_scanner.scan_directory(mods_path, recursive=True)
        
        # Step 3: Build resource index from mods
        if progress_callback:
            progress_callback("Matching resources", 2, 3)
        
        # Map: Resource Key -> List of mod files containing it
        resource_to_mods: Dict[ResourceKey, List[Mod]] = {}
        
        for mod in mods:
            for resource_key in mod.resources:
                if resource_key not in resource_to_mods:
                    resource_to_mods[resource_key] = []
                resource_to_mods[resource_key].append(mod)
        
        # Step 4: Match save resources to mods
        used_mod_paths: Set[Path] = set()
        matched_resources: Set[ResourceKey] = set()
        
        for resource_key in save_data.referenced_resources:
            if resource_key in resource_to_mods:
                # Found matching mod(s)
                matched_resources.add(resource_key)
                for mod in resource_to_mods[resource_key]:
                    used_mod_paths.add(mod.path)
        
        # Step 5: Calculate missing resources
        missing_resources = save_data.referenced_resources - matched_resources
        
        # Step 6: Build result
        result = SaveAnalysisResult(
            save_data=save_data,
            mods_directory=str(mods_path),
            scan_duration=time.time() - start_time,
        )
        
        # Categorize mods as used or unused
        for mod in mods:
            matching_res = set()
            for res_key in save_data.referenced_resources:
                if res_key in mod.resources:
                    matching_res.add(res_key)
            
            mod_file = ModFile(
                path=mod.path,
                name=mod.name,
                size=mod.size,
                resource_count=len(mod.resources),
                is_used=mod.path in used_mod_paths,
                matching_resources=matching_res,
            )
            
            if mod_file.is_used:
                result.used_mods.append(mod_file)
                result.total_used_size += mod_file.size
            else:
                result.unused_mods.append(mod_file)
                result.total_unused_size += mod_file.size
        
        result.total_mods = len(mods)
        result.missing_resources = missing_resources
        
        # Calculate coverage
        if save_data.total_resources > 0:
            result.coverage_percentage = (
                len(matched_resources) / save_data.total_resources * 100
            )
        
        if progress_callback:
            progress_callback("Complete", 3, 3)
        
        return result
    
    def get_summary(self, result: SaveAnalysisResult) -> Dict:
        """Get summary statistics from analysis result."""
        return {
            "save_name": result.save_data.save_name,
            "save_size_mb": result.save_data.save_size / 1024 / 1024,
            "total_resources": result.save_data.total_resources,
            "total_mods": result.total_mods,
            "used_mods": len(result.used_mods),
            "unused_mods": len(result.unused_mods),
            "used_size_mb": result.total_used_size / 1024 / 1024,
            "unused_size_mb": result.total_unused_size / 1024 / 1024,
            "missing_resources": len(result.missing_resources),
            "coverage_percentage": round(result.coverage_percentage, 1),
            "scan_duration": result.scan_duration,
        }
