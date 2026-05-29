"""
Simanalysis - Derrick: The PhD in Simology

Surgical analysis of The Sims 4 mods and custom content.
"""

from simanalysis.__version__ import (
    __author__,
    __description__,
    __license__,
    __title__,
    __version__,
    __version_info__,
)
from simanalysis.exceptions import (
    AnalysisError,
    ConflictDetectionError,
    DBPFError,
    ParsingError,
    ReportGenerationError,
    ScriptError,
    SimanalysisError,
    TuningError,
)
from simanalysis.models import (
    AnalysisMetadata,
    AnalysisResult,
    ConflictType,
    DBPFHeader,
    DBPFResource,
    Mod,
    ModConflict,
    ModType,
    PerformanceMetrics,
    ScriptMetadata,
    ScriptModule,
    Severity,
    TuningData,
)

__all__ = [
    "AnalysisError",
    "AnalysisMetadata",
    "AnalysisResult",
    "ConflictDetectionError",
    "ConflictType",
    "DBPFError",
    "DBPFHeader",
    "DBPFResource",
    "Mod",
    "ModConflict",
    # Models
    "ModType",
    "ParsingError",
    "PerformanceMetrics",
    "ReportGenerationError",
    "ScriptError",
    "ScriptMetadata",
    "ScriptModule",
    "Severity",
    # Exceptions
    "SimanalysisError",
    "TuningData",
    "TuningError",
    "__author__",
    "__description__",
    "__license__",
    "__title__",
    # Version info
    "__version__",
    "__version_info__",
]
