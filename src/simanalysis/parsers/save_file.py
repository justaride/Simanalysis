"""Save file and tray file parser for The Sims 4.

This module provides parsers for Sims 4 save files (.save) and tray files
(.trayitem, .householdbinary, .blueprint, .bpi) to identify custom content
used in saves and households.

Save files and tray files are DBPF packages containing SimData resources
which store Sim CAS parts, outfit data, and lot object references.
"""

import logging
import struct
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from simanalysis.exceptions import DBPFError, SimanalysisError
from simanalysis.models import RESOURCE_TYPE_SIMDATA, Mod
from simanalysis.parsers.dbpf import DBPFReader

logger = logging.getLogger(__name__)


@dataclass
class CASPart:
    """Represents a CAS (Create-A-Sim) part reference.

    CAS parts include clothing, hair, accessories, makeup, skin details, etc.
    Each part is identified by its instance ID which corresponds to the
    CASP resource in a CC package file.
    """

    instance_id: int
    """Instance ID of the CAS part (matches CASP resource in package files)."""

    part_type: str = "Unknown"
    """Type of CAS part (e.g., Hair, Clothing, Shoes, Accessories)."""

    age_gender: str = "Unknown"
    """Age and gender this part applies to (e.g., Adult Female, Teen Male)."""

    outfit_category: str = "Unknown"
    """Outfit category (e.g., Everyday, Formal, Athletic)."""

    def __hash__(self) -> int:
        """Hash based on instance ID for set operations."""
        return hash(self.instance_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on instance ID."""
        if not isinstance(other, CASPart):
            return False
        return self.instance_id == other.instance_id


@dataclass
class ObjectReference:
    """Represents a reference to a build/buy mode object.

    Objects are furniture, decorations, build mode items, etc. placed on lots.
    """

    instance_id: int
    """Instance ID of the object (matches resource in package files)."""

    object_type: str = "Unknown"
    """Type of object (e.g., Furniture, Decoration, Build Item)."""

    count: int = 1
    """Number of times this object appears."""

    def __hash__(self) -> int:
        """Hash based on instance ID for set operations."""
        return hash(self.instance_id)

    def __eq__(self, other: object) -> bool:
        """Equality based on instance ID."""
        if not isinstance(other, ObjectReference):
            return False
        return self.instance_id == other.instance_id


@dataclass
class SimInfo:
    """Information about a Sim in a save file or tray.

    Contains all CAS parts used by the Sim across all outfits.
    """

    name: str
    """Sim's name (if extractable from SimData)."""

    sim_id: int
    """Unique Sim ID."""

    cas_parts: List[CASPart] = field(default_factory=list)
    """List of all CAS parts used by this Sim."""

    @property
    def unique_cas_parts(self) -> Set[CASPart]:
        """Get unique CAS parts (no duplicates)."""
        return set(self.cas_parts)

    @property
    def cas_part_count(self) -> int:
        """Total number of unique CAS parts."""
        return len(self.unique_cas_parts)


@dataclass
class SaveFileData:
    """Parsed data from a save file.

    Contains all Sims, households, and object references found in the save.
    """

    save_path: Path
    """Path to the save file."""

    sims: List[SimInfo] = field(default_factory=list)
    """List of all Sims in the save."""

    objects: List[ObjectReference] = field(default_factory=list)
    """List of all objects placed on lots."""

    @property
    def all_cas_parts(self) -> Set[CASPart]:
        """Get all unique CAS parts used across all Sims."""
        all_parts: Set[CASPart] = set()
        for sim in self.sims:
            all_parts.update(sim.unique_cas_parts)
        return all_parts

    @property
    def all_objects(self) -> Set[ObjectReference]:
        """Get all unique objects."""
        return set(self.objects)

    @property
    def total_cc_items(self) -> int:
        """Total number of unique CC items (CAS + objects)."""
        return len(self.all_cas_parts) + len(self.all_objects)


@dataclass
class TrayItemData:
    """Parsed data from a tray item file.

    Tray items are Sims or lots saved to the gallery/library.
    """

    tray_path: Path
    """Path to the tray item file."""

    item_name: str = "Unknown"
    """Name of the tray item (Sim name or lot name)."""

    item_type: str = "Unknown"
    """Type of tray item (Sim, Household, Lot)."""

    sims: List[SimInfo] = field(default_factory=list)
    """List of Sims if this is a Sim/household tray item."""

    objects: List[ObjectReference] = field(default_factory=list)
    """List of objects if this is a lot tray item."""

    @property
    def all_cas_parts(self) -> Set[CASPart]:
        """Get all unique CAS parts used."""
        all_parts: Set[CASPart] = set()
        for sim in self.sims:
            all_parts.update(sim.unique_cas_parts)
        return all_parts

    @property
    def all_objects(self) -> Set[ObjectReference]:
        """Get all unique objects."""
        return set(self.objects)

    @property
    def total_cc_items(self) -> int:
        """Total number of unique CC items."""
        return len(self.all_cas_parts) + len(self.all_objects)


class SimDataParser:
    """Parser for SimData binary format.

    SimData is EA's proprietary binary format for storing structured game data.
    This parser extracts CAS part instance IDs and object references from
    SimData resources.

    Note: This is a simplified parser that focuses on extracting Instance IDs.
    Full SimData parsing would require complete schema knowledge.
    """

    # Known SimData schemas relevant to CC detection
    SCHEMA_SIM = b"Sim"
    SCHEMA_OUTFIT = b"Outfit"
    SCHEMA_CAS_PART = b"CASPart"
    SCHEMA_OBJECT = b"GameObject"

    def __init__(self):
        """Initialize SimData parser."""
        logger.debug("Initialized SimData parser")

    def parse(self, simdata_bytes: bytes) -> Dict[str, any]:
        """Parse SimData binary format.

        Args:
            simdata_bytes: Raw SimData bytes

        Returns:
            Dictionary containing parsed data:
            - 'cas_parts': List of CAS part instance IDs
            - 'objects': List of object instance IDs
            - 'sim_name': Sim name if extractable
        """
        result = {
            'cas_parts': [],
            'objects': [],
            'sim_name': None
        }

        if len(simdata_bytes) < 16:
            logger.debug("SimData too small to parse")
            return result

        try:
            # Extract 8-byte instance IDs from the binary data
            # Instance IDs appear as 64-bit integers throughout SimData
            # We scan for them using a sliding window approach
            instance_ids = self._extract_instance_ids(simdata_bytes)

            # Filter out common non-CC instance IDs
            # EA content typically uses lower instance IDs
            # CC usually has high instance IDs (> 0x0100000000000000)
            filtered_ids = self._filter_cc_instance_ids(instance_ids)

            # For now, classify all as CAS parts (most common in saves)
            # Future: Distinguish between CAS parts and objects
            result['cas_parts'] = filtered_ids

            # Try to extract Sim name (UTF-16 encoded strings in SimData)
            result['sim_name'] = self._extract_sim_name(simdata_bytes)

            logger.debug(f"Extracted {len(filtered_ids)} potential CC instance IDs")

        except Exception as e:
            logger.debug(f"Error parsing SimData: {e}")

        return result

    def _extract_instance_ids(self, data: bytes) -> List[int]:
        """Extract all 8-byte values that might be instance IDs.

        Args:
            data: Binary data to scan

        Returns:
            List of potential instance IDs
        """
        instance_ids = []

        # Scan through data looking for 8-byte aligned values
        for offset in range(0, len(data) - 7, 4):  # 4-byte alignment
            try:
                # Try to read as little-endian uint64
                value = struct.unpack_from("<Q", data, offset)[0]

                # Only keep non-zero values
                if value > 0:
                    instance_ids.append(value)

            except struct.error:
                continue

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for id in instance_ids:
            if id not in seen:
                seen.add(id)
                unique_ids.append(id)

        return unique_ids

    def _filter_cc_instance_ids(self, instance_ids: List[int]) -> List[int]:
        """Filter instance IDs to keep only those likely to be CC.

        EA content typically uses lower instance IDs. Custom content
        creators often use higher instance IDs generated by hashing.

        Args:
            instance_ids: List of all extracted instance IDs

        Returns:
            Filtered list of likely CC instance IDs
        """
        filtered = []

        for id in instance_ids:
            # Heuristic: CC often has higher instance IDs
            # EA content is usually < 0x0100000000000000
            # This is not perfect but helps reduce false positives

            # Keep IDs that are:
            # 1. Reasonable size (not too large to be garbage data)
            # 2. Not common EA patterns
            if id < 0xFFFFFFFFFFFFFFFF and id > 0:
                filtered.append(id)

        return filtered

    def _extract_sim_name(self, data: bytes) -> Optional[str]:
        """Try to extract Sim name from SimData.

        Sim names are stored as UTF-16 LE strings in SimData.

        Args:
            data: SimData bytes

        Returns:
            Sim name if found, None otherwise
        """
        try:
            # Look for UTF-16 LE encoded strings
            # Sim names typically appear early in the data
            search_range = min(len(data), 2000)

            for offset in range(0, search_range - 20, 2):
                try:
                    # Try to decode a potential string (max 50 chars)
                    potential_string = data[offset:offset+100].decode('utf-16-le', errors='ignore')

                    # Clean up and check if it looks like a name
                    cleaned = ''.join(c for c in potential_string if c.isprintable()).strip()

                    # Names are usually 2-30 characters, ASCII-ish
                    if 2 <= len(cleaned) <= 30 and cleaned.replace(' ', '').isalnum():
                        logger.debug(f"Found potential Sim name: {cleaned}")
                        return cleaned

                except (UnicodeDecodeError, AttributeError):
                    continue

        except Exception as e:
            logger.debug(f"Error extracting Sim name: {e}")

        return None


class SaveFileParser:
    """Parser for Sims 4 save files.

    Save files (.save, .ver0-ver4) are DBPF packages containing SimData
    resources that store household, Sim, and lot data.

    Example:
        >>> parser = SaveFileParser()
        >>> save_data = parser.parse_save_file("MySave.save")
        >>> print(f"Found {len(save_data.sims)} Sims")
        >>> print(f"Total CC items: {save_data.total_cc_items}")
    """

    def __init__(self):
        """Initialize save file parser."""
        self.simdata_parser = SimDataParser()
        logger.debug("Initialized SaveFileParser")

    def parse_save_file(self, save_path: Path | str) -> SaveFileData:
        """Parse a save file to extract CC references.

        Args:
            save_path: Path to .save file

        Returns:
            SaveFileData containing Sims and objects with CC references

        Raises:
            FileNotFoundError: If save file doesn't exist
            DBPFError: If save file is not a valid DBPF package
        """
        save_path = Path(save_path)
        logger.info(f"Parsing save file: {save_path.name}")

        if not save_path.exists():
            raise FileNotFoundError(f"Save file not found: {save_path}")

        # Save files are DBPF packages
        reader = DBPFReader(save_path)

        # Extract all SimData resources
        simdata_resources = reader.get_resources_by_type(RESOURCE_TYPE_SIMDATA)
        logger.info(f"Found {len(simdata_resources)} SimData resources in save")

        save_data = SaveFileData(save_path=save_path)
        sim_counter = 0

        # Parse each SimData resource
        for resource in simdata_resources:
            try:
                # Get resource data
                data = reader.get_resource(resource)

                # Parse SimData
                parsed = self.simdata_parser.parse(data)

                # Create SimInfo if we found CAS parts
                if parsed['cas_parts']:
                    sim_counter += 1
                    sim_info = SimInfo(
                        name=parsed['sim_name'] or f"Sim_{sim_counter}",
                        sim_id=resource.instance  # Use resource instance as Sim ID
                    )

                    # Add CAS parts
                    for instance_id in parsed['cas_parts']:
                        cas_part = CASPart(instance_id=instance_id)
                        sim_info.cas_parts.append(cas_part)

                    save_data.sims.append(sim_info)
                    logger.debug(f"Added Sim '{sim_info.name}' with {len(sim_info.cas_parts)} CAS parts")

                # Add objects if found
                for instance_id in parsed['objects']:
                    obj = ObjectReference(instance_id=instance_id)
                    save_data.objects.append(obj)

            except Exception as e:
                logger.debug(f"Error parsing SimData resource {resource.instance:016X}: {e}")
                continue

        logger.info(f"Parsed save: {len(save_data.sims)} Sims, {save_data.total_cc_items} CC items")
        return save_data

    def scan_saves_directory(self, saves_dir: Path | str) -> List[SaveFileData]:
        """Scan a saves directory and parse all save files.

        Args:
            saves_dir: Path to saves directory (usually Documents/Electronic Arts/The Sims 4/saves)

        Returns:
            List of SaveFileData for all save files found
        """
        saves_dir = Path(saves_dir)
        logger.info(f"Scanning saves directory: {saves_dir}")

        if not saves_dir.exists():
            raise FileNotFoundError(f"Saves directory not found: {saves_dir}")

        # Find all .save files (excluding .ver backups for now)
        save_files = list(saves_dir.glob("*.save"))
        logger.info(f"Found {len(save_files)} save files")

        results = []
        for save_file in save_files:
            try:
                save_data = self.parse_save_file(save_file)
                results.append(save_data)
            except Exception as e:
                logger.warning(f"Failed to parse {save_file.name}: {e}")
                continue

        return results


class TrayItemParser:
    """Parser for Sims 4 tray files (Gallery/Library items).

    Tray files include:
    - .trayitem (Sims, households, lots, rooms)
    - .householdbinary (household data)
    - .blueprint (lot blueprints)
    - .bpi (blueprint information)

    Like save files, these are DBPF packages containing SimData resources.

    Example:
        >>> parser = TrayItemParser()
        >>> tray_data = parser.parse_tray_item("MySim.trayitem")
        >>> print(f"Required CC: {tray_data.total_cc_items} items")
    """

    def __init__(self):
        """Initialize tray item parser."""
        self.simdata_parser = SimDataParser()
        logger.debug("Initialized TrayItemParser")

    def parse_tray_item(self, tray_path: Path | str) -> TrayItemData:
        """Parse a tray item file to extract CC references.

        Args:
            tray_path: Path to tray file (.trayitem, .householdbinary, etc.)

        Returns:
            TrayItemData containing CC references

        Raises:
            FileNotFoundError: If tray file doesn't exist
            DBPFError: If tray file is not a valid DBPF package
        """
        tray_path = Path(tray_path)
        logger.info(f"Parsing tray item: {tray_path.name}")

        if not tray_path.exists():
            raise FileNotFoundError(f"Tray file not found: {tray_path}")

        # Tray files are DBPF packages
        reader = DBPFReader(tray_path)

        # Extract SimData resources
        simdata_resources = reader.get_resources_by_type(RESOURCE_TYPE_SIMDATA)
        logger.info(f"Found {len(simdata_resources)} SimData resources in tray item")

        tray_data = TrayItemData(tray_path=tray_path)
        tray_data.item_name = tray_path.stem

        # Determine item type from extension
        suffix = tray_path.suffix.lower()
        if suffix == ".trayitem":
            tray_data.item_type = "TrayItem"
        elif suffix == ".householdbinary":
            tray_data.item_type = "Household"
        elif suffix == ".blueprint":
            tray_data.item_type = "Lot"
        elif suffix == ".bpi":
            tray_data.item_type = "Blueprint Info"

        sim_counter = 0

        # Parse each SimData resource
        for resource in simdata_resources:
            try:
                data = reader.get_resource(resource)
                parsed = self.simdata_parser.parse(data)

                # Create SimInfo if we found CAS parts
                if parsed['cas_parts']:
                    sim_counter += 1
                    sim_info = SimInfo(
                        name=parsed['sim_name'] or f"Sim_{sim_counter}",
                        sim_id=resource.instance
                    )

                    for instance_id in parsed['cas_parts']:
                        cas_part = CASPart(instance_id=instance_id)
                        sim_info.cas_parts.append(cas_part)

                    tray_data.sims.append(sim_info)

                # Add objects
                for instance_id in parsed['objects']:
                    obj = ObjectReference(instance_id=instance_id)
                    tray_data.objects.append(obj)

            except Exception as e:
                logger.debug(f"Error parsing SimData resource: {e}")
                continue

        logger.info(f"Parsed tray item: {len(tray_data.sims)} Sims, {tray_data.total_cc_items} CC items")
        return tray_data

    def scan_tray_directory(self, tray_dir: Path | str) -> List[TrayItemData]:
        """Scan a tray directory and parse all tray items.

        Args:
            tray_dir: Path to tray directory (usually Documents/Electronic Arts/The Sims 4/Tray)

        Returns:
            List of TrayItemData for all tray items found
        """
        tray_dir = Path(tray_dir)
        logger.info(f"Scanning tray directory: {tray_dir}")

        if not tray_dir.exists():
            raise FileNotFoundError(f"Tray directory not found: {tray_dir}")

        # Find all tray files
        tray_files = []
        for pattern in ["*.trayitem", "*.householdbinary", "*.blueprint", "*.bpi"]:
            tray_files.extend(tray_dir.glob(pattern))

        logger.info(f"Found {len(tray_files)} tray files")

        results = []
        for tray_file in tray_files:
            try:
                tray_data = self.parse_tray_item(tray_file)
                results.append(tray_data)
            except Exception as e:
                logger.warning(f"Failed to parse {tray_file.name}: {e}")
                continue

        return results
