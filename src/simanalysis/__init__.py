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
    # Version info
    "__version__",
    "__version_info__",
    "__title__",
    "__description__",
    "__author__",
    "__license__",
    # Exceptions
    "SimanalysisError",
    "ParsingError",
    "DBPFError",
    "TuningError",
    "ScriptError",
    "ConflictDetectionError",
    "AnalysisError",
    "ReportGenerationError",
    # Models
    "ModType",
    "Severity",
    "ConflictType",
    "DBPFHeader",
    "DBPFResource",
    "TuningData",
    "ScriptMetadata",
    "ScriptModule",
    "Mod",
    "ModConflict",
    "PerformanceMetrics",
    "AnalysisMetadata",
    "AnalysisResult",
]
