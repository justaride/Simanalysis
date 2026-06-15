"""Conflict detection for Sims 4 mods."""

from simanalysis.detectors.base import (
    ConflictDetector,
    ConflictResolutions,
    SeverityRules,
)
from simanalysis.detectors.resource_conflicts import ResourceConflictDetector
from simanalysis.detectors.script_conflicts import ScriptConflictDetector
from simanalysis.detectors.tuning_conflicts import TuningConflictDetector

__all__ = [
    "ConflictDetector",
    "ConflictResolutions",
    "ResourceConflictDetector",
    "ScriptConflictDetector",
    "SeverityRules",
    "TuningConflictDetector",
]
