"""Scanner for Sims 4 save files to extract CC references."""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from simanalysis.exceptions import SimanalysisError
from simanalysis.parsers.dbpf import DBPFReader


# Resource key: (Type, Group, Instance)
ResourceKey = Tuple[int, int, int]


class SaveData:
    """Data extracted from a Sims 4 save file."""
    
    def __init__(
        self,
        save_path: Path,
        save_name: str,
        save_size: int,
    ):
        self.save_path = save_path
        self.save_name = save_name
        self.save_size = save_size
        
        # All resources referenced in the save
        self.referenced_resources: Set[ResourceKey] = set()
        
        # Resources organized by type
        self.cas_resources: Set[ResourceKey] = set()  # CAS (Create-A-Sim) items
        self.build_buy_resources: Set[ResourceKey] = set()  # Build/Buy mode items
        self.other_resources: Set[ResourceKey] = set()
        
        # Metadata
        self.total_resources = 0
        self.game_version: Optional[str] = None
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "save_name": self.save_name,
            "save_size": self.save_size,
            "total_resources": self.total_resources,
            "cas_count": len(self.cas_resources),
            "build_buy_count": len(self.build_buy_resources),
            "other_count": len(self.other_resources),
            "game_version": self.game_version,
        }


class SaveScanner:
    """
    Scanner for Sims 4 save files.
    
    Parses save files (which are DBPF packages) and extracts
    all CC resource references.
    """
    
    # Resource type IDs for different categories
    # These are common Sims 4 resource types
    CAS_TYPES = {
        0x034AEECB,  # CAS Part (clothing, hair, etc.)
        0x0355E0A6,  # Skin tone
        0x0354796A,  # Makeup
    }
    
    BUILD_BUY_TYPES = {
        0x515CA4CD,  # Object catalog
        0x319E4F1D,  # Object definition
        0xC0DB5AE7,  # Build/Buy catalog
    }
    
    def __init__(self) -> None:
        self.errors_encountered: List[Tuple[Path, str]] = []
    
    def scan_save_file(self, save_path: Path) -> SaveData:
        """
        Scan a Sims 4 save file and extract CC references.
        
        Args:
            save_path: Path to the .save file
            
        Returns:
            SaveData with extracted resource references
            
        Raises:
            SimanalysisError: If save file is invalid or can't be parsed
        """
        if not save_path.exists():
            raise SimanalysisError(f"Save file not found: {save_path}")
        
        if save_path.suffix.lower() not in ['.save', '.ver0', '.ver1', '.ver2']:
            raise SimanalysisError(f"Invalid save file extension: {save_path.suffix}")
        
        save_name = save_path.stem
        save_size = save_path.stat().st_size
        
        save_data = SaveData(
            save_path=save_path,
            save_name=save_name,
            save_size=save_size,
        )
        
        try:
            # Parse the save file as a DBPF package
            reader = DBPFReader(save_path)
            
            # Extract all resource keys
            for resource in reader.resources:
                # Create resource key tuple (Type, Group, Instance)
                resource_key = (resource.type, resource.group, resource.instance)
                
                # Add to referenced resources
                save_data.referenced_resources.add(resource_key)
                save_data.total_resources += 1
                
                # Categorize by type
                if resource.type in self.CAS_TYPES:
                    save_data.cas_resources.add(resource_key)
                elif resource.type in self.BUILD_BUY_TYPES:
                    save_data.build_buy_resources.add(resource_key)
                else:
                    save_data.other_resources.add(resource_key)
            
            # Try to extract game version from header if available
            # (This is optional metadata that may be in the DBPF header)
            save_data.game_version = self._extract_game_version(reader)
            
            return save_data
            
        except Exception as e:
            raise SimanalysisError(f"Failed to parse save file {save_path}: {e}")
    
    def _extract_game_version(self, reader: DBPFReader) -> Optional[str]:
        """
        Try to extract game version from save file.
        
        This is a best-effort attempt - may not always be available.
        """
        # This would require deeper parsing of save file metadata
        # For now, return None - can be enhanced later
        return None
