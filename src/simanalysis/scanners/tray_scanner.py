"""Scanner for discovering Sims 4 tray files (Households, Lots, Rooms)."""

import struct
from pathlib import Path
from typing import Dict, List, Optional, Set

from simanalysis.exceptions import SimanalysisError


class TrayItem:
    """Represents a Sims 4 Tray Item (Household, Lot, Room)."""

    def __init__(
        self,
        name: str,
        files: List[Path],
        type: str,
        creation_time: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ):
        self.name = name
        self.files = files
        self.type = type  # 'Household', 'Lot', 'Room', or 'Unknown'
        self.creation_time = creation_time
        self.metadata = metadata or {}
        self.size = sum(f.stat().st_size for f in files if f.exists())

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response."""
        return {
            "name": self.name,
            "type": self.type,
            "file_count": len(self.files),
            "size": self.size,
            "creation_time": self.creation_time,
            "metadata": self.metadata,
            "files": [str(f.name) for f in self.files],
        }


class TrayScanner:
    """
    Scanner for discovering Sims 4 tray items.
    
    Groups related files (trayitem, blueprint, bpi, etc.) into logical items.
    """

    def __init__(self) -> None:
        self.items_scanned = 0
        self.errors_encountered: List[tuple[Path, str]] = []

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = False,  # Tray folder is usually flat
        progress_callback: Optional["Callable[[int, int, str], None]"] = None,
    ) -> List[TrayItem]:
        """
        Scan directory for tray items.

        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories (default False for Tray)
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of discovered TrayItems
        """
        if not directory.exists():
            raise SimanalysisError(f"Directory not found: {directory}")

        self.items_scanned = 0
        self.errors_encountered = []
        
        tray_item_files = list(directory.glob("*.trayitem"))
        total_files = len(tray_item_files)
        
        items: List[TrayItem] = []
        
        for i, tray_file in enumerate(tray_item_files, 1):
            if progress_callback:
                progress_callback(i, total_files, tray_file.name)
                
            try:
                item = self._parse_tray_item(tray_file, directory)
                if item:
                    items.append(item)
                    self.items_scanned += 1
            except Exception as e:
                self.errors_encountered.append((tray_file, str(e)))
                
        return items

    def _parse_tray_item(self, tray_file: Path, directory: Path) -> Optional[TrayItem]:
        """
        Parse a .trayitem file and find associated files.
        """
        try:
            with open(tray_file, "rb") as f:
                content = f.read()
            
            # Extract name from binary content
            name = self._extract_name(content, tray_file.stem)
            
            # Find all associated files (same base name)
            base_name = tray_file.stem
            associated_files = list(directory.glob(f"{base_name}*"))
            
            # Determine type based on associated files and content
            item_type = self._determine_type(associated_files, content)
            
            # Creation time from file stats
            creation_time = tray_file.stat().st_mtime
            
            return TrayItem(
                name=name,
                files=associated_files,
                type=item_type,
                creation_time=creation_time
            )
            
        except Exception as e:
            raise SimanalysisError(f"Failed to parse tray item {tray_file}: {e}")

    def _extract_name(self, content: bytes, fallback: str) -> str:
        """
        Extract the human-readable name from tray item binary content.
        
        Tray items contain UTF-16 encoded strings. We'll search for readable text.
        """
        try:
            # Try to find UTF-16 encoded strings (Sims 4 uses UTF-16LE)
            # Look for sequences that might be names
            decoded_parts = []
            
            # Search for null-terminated UTF-16 strings
            i = 0
            while i < len(content) - 1:
                # Check if we have a potential UTF-16 character
                if content[i] != 0 and content[i+1] == 0:
                    # Start of potential UTF-16 string
                    string_bytes = bytearray()
                    j = i
                    while j < len(content) - 1:
                        if content[j] == 0 and content[j+1] == 0:
                            # Null terminator
                            break
                        if content[j+1] == 0:
                            string_bytes.append(content[j])
                            j += 2
                        else:
                            break
                    
                    if len(string_bytes) > 2:  # Only consider strings > 2 chars
                        try:
                            text = string_bytes.decode('utf-8', errors='ignore')
                            # Filter out binary junk, keep only printable strings
                            if text.isprintable() and len(text.strip()) >= 3:
                                decoded_parts.append(text.strip())
                        except:
                            pass
                    i = j + 2
                else:
                    i += 1
            
            # Return the longest reasonable string found (likely the name)
            if decoded_parts:
                # Filter out common metadata strings
                filtered = [p for p in decoded_parts if p not in ['Tray', 'Item', 'Sim', 'Lot', 'Room']]
                if filtered:
                    return max(filtered, key=len)[:50]  # Limit to 50 chars
            
            return fallback
            
        except Exception:
            return fallback

    def _determine_type(self, associated_files: List[Path], content: bytes) -> str:
        """
        Determine the type of tray item based on associated files.
        """
        exts = {f.suffix.lower() for f in associated_files}
        
        # Household items have .hhi (Household Info) files
        if ".hhi" in exts:
            return "Household"
        
        # Lots and Rooms have .blueprint files
        if ".blueprint" in exts:
            # Try to determine if it's a lot or room
            # Rooms are usually smaller and may have different indicators
            # For now, we'll call them Lots (most common)
            return "Lot"
        
        # Check for room-specific indicators
        if ".rmi" in exts:
            return "Room"
        
        # Fallback: check file type code in tray item header
        # The first few bytes often contain type info
        if len(content) > 4:
            try:
                # Read potential type marker (varies by game version)
                type_code = struct.unpack('<I', content[0:4])[0]
                
                # Common type codes (may need adjustment)
                if type_code == 0x00000001:
                    return "Household"
                elif type_code == 0x00000002:
                    return "Lot"
                elif type_code == 0x00000003:
                    return "Room"
            except:
                pass
        
        return "Tray Item"  # More specific than just "Unknown"
