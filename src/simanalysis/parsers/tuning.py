"""XML Tuning parser for Sims 4 tuning modifications.

Sims 4 uses XML files to define and modify game behavior (tunings).
This module provides tools to parse these XML files and extract metadata.

Tuning files define objects, interactions, buffs, traits, and more.
"""

import re
from typing import Dict, Any, Set, Optional
from lxml import etree

from simanalysis.exceptions import TuningError
from simanalysis.models import TuningData, PACK_PREFIXES


class TuningParser:
    """
    Parser for Sims 4 XML tuning files.

    Tuning files are XML documents that define game objects, behaviors,
    and modifications. This parser extracts:
    - Instance ID (unique identifier)
    - Tuning name and class
    - Module path
    - Modified attributes
    - References to other tunings
    - Pack requirements

    Example:
        >>> parser = TuningParser()
        >>> xml_data = b'<I c="Buff" i="buff" m="buffs.buff" ...>'
        >>> tuning = parser.parse(xml_data)
        >>> print(tuning.tuning_name)
        'buff'
    """

    def parse(self, xml_data: bytes) -> TuningData:
        """
        Parse XML tuning data.

        Args:
            xml_data: Raw XML data as bytes

        Returns:
            TuningData with parsed information

        Raises:
            TuningError: If XML is invalid or missing required fields
        """
        try:
            # Parse XML
            root = etree.fromstring(xml_data)

            # Extract basic metadata
            instance_id = self.get_instance_id(root)
            tuning_name = self.get_tuning_name(root)
            tuning_class = self.get_tuning_class(root)
            module = self.get_module(root)

            # Extract modifications and references
            modified_attributes = self.extract_modifications(root)
            references = self.find_references(root)
            pack_requirements = self.detect_pack_requirements(root)

            return TuningData(
                instance_id=instance_id,
                tuning_name=tuning_name,
                tuning_class=tuning_class,
                module=module,
                modified_attributes=modified_attributes,
                references=references,
                pack_requirements=pack_requirements,
            )

        except etree.XMLSyntaxError as e:
            raise TuningError(f"Invalid XML syntax: {e}") from e
        except Exception as e:
            raise TuningError(f"Failed to parse tuning: {e}") from e

    def get_instance_id(self, root: etree._Element) -> int:
        """
        Extract tuning instance ID.

        The instance ID is the unique identifier for this tuning,
        typically stored in the 's' attribute of the root element.

        Args:
            root: XML root element

        Returns:
            Instance ID as integer

        Raises:
            TuningError: If instance ID not found or invalid
        """
        # Try 's' attribute (most common)
        instance_str = root.get("s")

        if instance_str is None:
            # Try 'i' attribute (alternative)
            instance_str = root.get("i")

        if instance_str is None:
            raise TuningError("Instance ID not found in tuning XML")

        try:
            # Instance ID can be decimal or hex
            if instance_str.startswith("0x") or instance_str.startswith("0X"):
                return int(instance_str, 16)
            else:
                return int(instance_str)
        except ValueError as e:
            raise TuningError(f"Invalid instance ID format: {instance_str}") from e

    def get_tuning_name(self, root: etree._Element) -> str:
        """
        Extract tuning name.

        Args:
            root: XML root element

        Returns:
            Tuning name (defaults to "unknown" if not found)
        """
        # Try 'i' attribute (name identifier)
        name = root.get("i")

        if name is None:
            # Try 'n' attribute (alternative)
            name = root.get("n")

        if name is None:
            # Try tag name as fallback
            name = root.tag

        return name or "unknown"

    def get_tuning_class(self, root: etree._Element) -> str:
        """
        Extract tuning class/type.

        Args:
            root: XML root element

        Returns:
            Tuning class (e.g., "Buff", "Trait", "Object")
        """
        # Try 'c' attribute (class)
        tuning_class = root.get("c")

        if tuning_class is None:
            # Try tag name as fallback
            tuning_class = root.tag

        return tuning_class or "unknown"

    def get_module(self, root: etree._Element) -> str:
        """
        Extract module path.

        Args:
            root: XML root element

        Returns:
            Module path (e.g., "buffs.buff_tuning")
        """
        # Try 'm' attribute (module)
        module = root.get("m")

        return module or "unknown"

    def extract_modifications(self, root: etree._Element) -> Dict[str, Any]:
        """
        Extract modified attributes from tuning.

        Args:
            root: XML root element

        Returns:
            Dictionary of modified attributes
        """
        modifications: Dict[str, Any] = {}

        # Walk through all elements and collect attribute modifications
        for element in root.iter():
            # Get element name
            name = element.get("n")

            if name:
                # Store the text content or attribute value
                if element.text and element.text.strip():
                    modifications[name] = element.text.strip()
                else:
                    # Check for value in attributes
                    for attr_name in ["t", "c", "m", "p"]:
                        attr_value = element.get(attr_name)
                        if attr_value:
                            modifications[name] = attr_value
                            break

        return modifications

    def find_references(self, root: etree._Element) -> Set[int]:
        """
        Find references to other tunings.

        References are tuning IDs that this tuning depends on or refers to.
        They can appear in various attributes (typically 't' for type references).

        Args:
            root: XML root element

        Returns:
            Set of referenced tuning instance IDs
        """
        references: Set[int] = set()

        # Look for common reference patterns
        for element in root.iter():
            # Check 't' attribute (type/tuning reference)
            ref = element.get("t")
            if ref:
                # Extract tuning ID if it looks like a reference
                tuning_id = self._extract_tuning_id(ref)
                if tuning_id:
                    references.add(tuning_id)

            # Check for instance references in text
            if element.text:
                tuning_id = self._extract_tuning_id(element.text)
                if tuning_id:
                    references.add(tuning_id)

        return references

    def _extract_tuning_id(self, text: str) -> Optional[int]:
        """
        Extract tuning ID from text if it looks like a tuning reference.

        Args:
            text: Text to search for tuning ID

        Returns:
            Tuning ID if found, None otherwise
        """
        # Look for hex numbers that could be tuning IDs
        # Sims 4 tuning IDs are typically 32-bit hex numbers
        hex_pattern = r"(?:0x)?([0-9A-Fa-f]{8})"
        match = re.search(hex_pattern, text)

        if match:
            try:
                return int(match.group(1), 16)
            except ValueError:
                return None

        return None

    def detect_pack_requirements(self, root: etree._Element) -> Set[str]:
        """
        Detect required game packs from tuning.

        Pack requirements can be inferred from:
        - Module paths (e.g., "EP01" prefix)
        - Object references
        - Attribute values

        Args:
            root: XML root element

        Returns:
            Set of pack codes (e.g., {"EP01", "GP03"})
        """
        packs: Set[str] = set()

        # Get all text content
        all_text = etree.tostring(root, encoding="unicode", method="text")

        # Search for pack prefixes
        for pack_code in PACK_PREFIXES.keys():
            # Look for pack code in the XML
            # Common patterns: EP01:..., EP01/..., EP01.module
            pattern = rf"\b{pack_code}[:\\/\.]"
            if re.search(pattern, all_text):
                packs.add(pack_code)

        # Check module path
        module = self.get_module(root)
        if module:
            for pack_code in PACK_PREFIXES.keys():
                if pack_code.lower() in module.lower():
                    packs.add(pack_code)

        return packs

    def parse_tuning_file(self, xml_data: bytes) -> TuningData:
        """
        Alias for parse() method.

        Args:
            xml_data: Raw XML data as bytes

        Returns:
            TuningData with parsed information
        """
        return self.parse(xml_data)
