"""Analyzer for detecting missing meshes and dependencies."""

import logging
import struct

from simanalysis.models import ConflictType, DBPFResource, Mod, ModConflict, Severity
from simanalysis.parsers.dbpf import DBPFReader

logger = logging.getLogger(__name__)


class MeshAnalyzer:
    """
    Analyzes mods for missing mesh dependencies.

    Uses signature scanning to find references to Model and Geometry resources
    within CAS Parts and Object Definitions.
    """

    # Resource Types
    TYPE_CAS_PART = 0x034AEECB
    TYPE_OBJECT_DEF = 0xC0DB5AE7

    # Target Mesh Types
    TYPE_GEOM = 0x015A1849  # CAS Geometry
    TYPE_MODEL = 0x01661233  # Object Model

    # Signatures to scan for (Little Endian)
    # We look for the Type ID, then assume Group (4) + Instance (8) follow.
    SIG_GEOM = struct.pack("<I", TYPE_GEOM)
    SIG_MODEL = struct.pack("<I", TYPE_MODEL)

    def analyze(self, mods: list[Mod]) -> list[ModConflict]:
        """
        Analyze mods for missing mesh dependencies.

        Args:
            mods: List of mods to analyze.

        Returns:
            List of conflicts (missing dependencies).
        """
        provided_meshes: set[int] = set()
        required_meshes: list[tuple[Mod, int, int]] = []  # (SourceMod, MeshType, MeshInstance)

        # Pass 1: Indexing
        for mod in mods:
            try:
                reader = DBPFReader(mod.path)

                # 1. Index Provided Meshes
                # We only care about the Instance ID for matching
                for res in reader.get_resources_by_type(self.TYPE_GEOM):
                    provided_meshes.add(res.instance)
                for res in reader.get_resources_by_type(self.TYPE_MODEL):
                    provided_meshes.add(res.instance)

                # 2. Index Required Meshes (Scan CASP and OBJ)
                # Scan CAS Parts
                for res in reader.get_resources_by_type(self.TYPE_CAS_PART):
                    self._scan_dependencies(
                        mod, reader, res, self.SIG_GEOM, self.TYPE_GEOM, required_meshes
                    )

                # Scan Object Definitions
                for res in reader.get_resources_by_type(self.TYPE_OBJECT_DEF):
                    self._scan_dependencies(
                        mod, reader, res, self.SIG_MODEL, self.TYPE_MODEL, required_meshes
                    )

            except Exception as e:
                logger.warning(f"Error analyzing meshes in {mod.name}: {e}")
                continue

        # Pass 2: Resolution
        conflicts = []

        # Cache to avoid duplicate reports
        reported_missing: set[tuple[str, int]] = set()  # (ModName, MissingInstance)

        for source_mod, mesh_type, mesh_instance in required_meshes:
            if mesh_instance not in provided_meshes:
                # Potential missing mesh!

                # Filter out likely Base Game IDs
                # Heuristic: Base game IDs often have specific Groups or low Instance values?
                # For now, we'll report everything but mark it as "Potential"
                # A better heuristic might be needed.

                # Deduplicate
                if (source_mod.name, mesh_instance) in reported_missing:
                    continue
                reported_missing.add((source_mod.name, mesh_instance))

                mesh_type_name = "CAS Geometry" if mesh_type == self.TYPE_GEOM else "Object Model"

                conflicts.append(
                    ModConflict(
                        id=f"MISSING_MESH_{source_mod.hash}_{mesh_instance}",
                        severity=Severity.HIGH,
                        type=ConflictType.DEPENDENCY_MISSING,
                        affected_mods=[source_mod.name],
                        description=f"Missing {mesh_type_name} dependency.",
                        details={
                            "missing_resource_type": mesh_type,
                            "missing_resource_instance": mesh_instance,
                            "hex_instance": f"0x{mesh_instance:016X}",
                        },
                        resolution="Download the original mesh for this recolor.",
                    )
                )

        return conflicts

    def _scan_dependencies(
        self,
        mod: Mod,
        reader: DBPFReader,
        resource: DBPFResource,
        signature: bytes,
        target_type: int,
        results: list[tuple[Mod, int, int]],
    ) -> None:
        """Scan a resource for a specific TGI signature."""
        try:
            data = reader.get_resource(resource)

            # Simple signature scan
            # Look for Type (4 bytes)
            # If found, read next 12 bytes (Group + Instance)

            offset = 0
            while True:
                try:
                    index = data.index(signature, offset)

                    # We found the Type. Check if we have enough bytes for Group + Instance
                    if index + 16 <= len(data):
                        # Format: Type (4) + Group (4) + Instance (8)
                        # We already matched Type.
                        # group = struct.unpack("<I", data[index+4:index+8])[0]
                        instance = struct.unpack("<Q", data[index + 8 : index + 16])[0]

                        results.append((mod, target_type, instance))

                    offset = index + 1
                except ValueError:
                    # Signature not found
                    break

        except Exception as e:
            logger.debug(f"Failed to scan resource in {mod.name}: {e}")
