"""Script namespace conflict detector for Sims 4 script mods."""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath

from simanalysis.detectors.base import ConflictDetector
from simanalysis.models import ConflictType, Mod, ModConflict, ModType


class ScriptConflictDetector(ConflictDetector):
    """Detect potentially conflicting script namespace families without executing code."""

    def detect(self, mods: list[Mod]) -> list[ModConflict]:
        families: dict[str, list[Mod]] = defaultdict(list)
        for mod in mods:
            for family in self._script_families(mod):
                families[family].append(mod)

        conflicts: list[ModConflict] = []
        for family, family_mods in sorted(families.items()):
            unique_mods = self._unique_mods(family_mods)
            if len(unique_mods) < 2 or self._all_known_hashes_identical(unique_mods):
                continue
            conflicts.append(self._create_script_family_conflict(family, unique_mods))
        return conflicts

    def _script_families(self, mod: Mod) -> set[str]:
        if mod.type not in {ModType.SCRIPT, ModType.HYBRID}:
            return set()
        families: set[str] = set()
        for module in mod.scripts:
            family = self._module_family(module.path or module.name)
            if family:
                families.add(family)
        return families

    def _module_family(self, module_path: str) -> str | None:
        normalized = module_path.replace("\\", "/").strip("/")
        if not normalized:
            return None
        path = PurePosixPath(normalized)
        first_part = path.parts[0]
        if first_part == "__init__.py":
            return path.stem
        if first_part.endswith(".py"):
            return PurePosixPath(first_part).stem
        return first_part

    def _unique_mods(self, mods: list[Mod]) -> list[Mod]:
        unique: dict[str, Mod] = {}
        for mod in mods:
            unique[str(mod.path)] = mod
        return list(unique.values())

    def _all_known_hashes_identical(self, mods: list[Mod]) -> bool:
        hashes = {mod.hash for mod in mods if mod.hash}
        return len(hashes) == 1 and all(mod.hash for mod in mods)

    def _create_script_family_conflict(self, family: str, mods: list[Mod]) -> ModConflict:
        affected_mods = [mod.name for mod in mods]
        module_paths_by_mod = {
            mod.name: sorted(
                module.path for module in mod.scripts if self._module_family(module.path) == family
            )
            for mod in mods
        }
        description = (
            f"Multiple script mods publish Python modules under the '{family}' namespace. "
            "This can be intentional, but it should be reviewed for the active profile."
        )
        details = {
            "conflict_kind": "script_family_mismatch",
            "review_status": "needs_compatibility_review",
            "script_family": family,
            "mod_count": len(mods),
            "affected_mod_names": affected_mods,
            "module_paths_by_mod": module_paths_by_mod,
            "hashes": {mod.name: mod.hash for mod in mods},
            "executes_code": False,
            "recommendation": {
                "action": "review_script_family_compatibility",
                "confidence": "medium",
                "profile_aware": True,
                "message": (
                    "Shared script namespaces may be intentional library/plugin layouts or "
                    "incompatible script families; review versions and creator guidance before "
                    "changing files."
                ),
            },
        }
        return self.create_conflict(
            conflict_type=ConflictType.NAMESPACE_COLLISION,
            affected_mods=affected_mods,
            description=description,
            identifier=f"script_family_{family}",
            resolution=(
                "Review the active profile, script versions, and creator compatibility notes. "
                "Do not delete scripts solely from this signal."
            ),
            details=details,
            is_core_resource=False,
        )
