"""Data models for Simanalysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ModType(Enum):
    """Type of mod."""

    PACKAGE = "package"
    SCRIPT = "script"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class Severity(Enum):
    """Conflict severity level."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConflictType(Enum):
    """Type of conflict detected."""

    TUNING_OVERLAP = "TUNING_OVERLAP"
    RESOURCE_DUPLICATE = "RESOURCE_DUPLICATE"
    SCRIPT_INJECTION = "SCRIPT_INJECTION"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    NAMESPACE_COLLISION = "NAMESPACE_COLLISION"


@dataclass
class DBPFHeader:
    """DBPF file header information."""

    magic: bytes
    major_version: int
    minor_version: int
    user_version: int
    index_count: int
    index_offset: int
    index_size: int
    file_size: int = 0

    def __post_init__(self) -> None:
        """Validate header data."""
        if self.magic != b"DBPF":
            raise ValueError(f"Invalid DBPF magic: {self.magic!r}")
        if self.major_version != 2:
            raise ValueError(f"Unsupported DBPF version: {self.major_version}")


@dataclass
class DBPFResource:
    """Individual resource entry in DBPF package."""

    type: int  # Resource type (4 bytes)
    group: int  # Resource group (4 bytes)
    instance: int  # Resource instance (8 bytes)
    offset: int  # File offset
    size: int  # Resource size
    compressed_size: int = 0  # Compressed size (0 = not compressed)

    @property
    def key(self) -> tuple[int, int, int]:
        """Get resource key tuple (Type, Group, Instance)."""
        return (self.type, self.group, self.instance)

    @property
    def is_compressed(self) -> bool:
        """Check if resource is compressed."""
        return self.compressed_size > 0 and self.compressed_size != self.size


@dataclass
class TracebackFrame:
    """One frame of a crash traceback."""

    raw_path: str
    module_path: Optional[str] = None  # normalized package-relative tail, if attributed
    line: Optional[int] = None
    func: Optional[str] = None
    kind: str = "unknown"  # "game" | "mod" | "unknown"
    mod_name: Optional[str] = None  # set when kind == "mod"
    mod_status: Optional[str] = None  # "active" | "disabled" | "not_installed", set with mod_name


@dataclass
class CrashReport:
    """A single parsed crash (one <report> block)."""

    source_file: str
    report_type: str
    message: str
    frames: list[TracebackFrame] = field(default_factory=list)
    exception_class: Optional[str] = None
    creator_tag: Optional[str] = None
    created: Optional[str] = None
    game_version: Optional[str] = None
    be_advice: Optional[str] = None
    signature: str = ""  # dedupe key


@dataclass
class Suspect:
    """A mod implicated in a crash, with confidence."""

    mod_name: str
    confidence: str  # "high" | "medium" | "low"
    reason: str
    evidence: list[TracebackFrame] = field(default_factory=list)
    status: str = "active"  # "active" | "disabled" | "not_installed"


@dataclass
class CrashFinding:
    """One analyzed crash and its ranked suspects (empty => base-game/unattributable)."""

    report: CrashReport
    suspects: list[Suspect] = field(default_factory=list)


@dataclass
class CrashAnalysisResult:
    """Whole-library crash analysis output."""

    summary: dict = field(default_factory=dict)
    ranked_mods: list[dict] = field(default_factory=list)
    findings: list[CrashFinding] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class TuningData:
    """Parsed tuning file data."""

    instance_id: int
    tuning_name: str
    tuning_class: str
    module: str
    modified_attributes: dict[str, Any] = field(default_factory=dict)
    references: set[int] = field(default_factory=set)
    pack_requirements: set[str] = field(default_factory=set)


@dataclass
class ScriptMetadata:
    """Script mod metadata."""

    name: str
    version: str = "unknown"
    author: str = "unknown"
    requires: list[str] = field(default_factory=list)
    python_version: str = "3.7"


@dataclass
class ScriptModule:
    """Individual Python module in script."""

    name: str
    path: str
    imports: set[str] = field(default_factory=set)
    hooks: list[str] = field(default_factory=list)
    complexity: int = 0


@dataclass
class Mod:
    """Represents a single mod."""

    name: str
    path: Path
    type: ModType
    size: int
    hash: Optional[str]

    # Parsed data
    resources: list[DBPFResource] = field(default_factory=list)
    tunings: list[TuningData] = field(default_factory=list)
    scripts: list[ScriptModule] = field(default_factory=list)

    # Metadata
    version: Optional[str] = None
    author: Optional[str] = None
    requires: list[str] = field(default_factory=list)
    pack_requirements: set[str] = field(default_factory=set)

    @property
    def tuning_ids(self) -> set[int]:
        """Get all tuning instance IDs in this mod."""
        return {tuning.instance_id for tuning in self.tunings}

    @property
    def resource_keys(self) -> set[tuple[int, int, int]]:
        """Get all resource keys (Type, Group, Instance) in this mod."""
        return {resource.key for resource in self.resources}


@dataclass
class ModConflict:
    """Represents a detected conflict."""

    id: str
    severity: Severity
    type: ConflictType
    affected_mods: list[str]
    description: str
    resolution: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance analysis metrics."""

    total_mods: int
    total_size_mb: float
    total_resources: int
    total_tunings: int
    total_scripts: int
    estimated_load_time_seconds: float
    estimated_memory_mb: float
    complexity_score: float  # 0-100


@dataclass
class AnalysisMetadata:
    """Metadata about the analysis run."""

    timestamp: datetime
    version: str
    mod_directory: str
    analysis_duration_seconds: float
    total_mods_analyzed: int


@dataclass
class AnalysisResult:
    """Complete analysis results."""

    metadata: AnalysisMetadata
    mods: list[Mod]
    conflicts: list[ModConflict]
    dependencies: dict[str, list[str]]
    performance: PerformanceMetrics
    recommendations: list[str]
    warnings: list[str] = field(default_factory=list)

    def get_conflicts(
        self,
        severity: Optional[Severity] = None,
        type: Optional[ConflictType] = None,
    ) -> list[ModConflict]:
        """Filter conflicts by severity and/or type."""
        filtered = self.conflicts

        if severity:
            filtered = [c for c in filtered if c.severity == severity]

        if type:
            filtered = [c for c in filtered if c.type == type]

        return filtered

    @property
    def critical_conflicts(self) -> list[ModConflict]:
        """Get all critical conflicts."""
        return self.get_conflicts(severity=Severity.CRITICAL)

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical conflicts."""
        return len(self.critical_conflicts) > 0


# Resource type constants
RESOURCE_TYPE_XML_TUNING = 0x545238C9
RESOURCE_TYPE_SIMDATA = 0x0333406C
RESOURCE_TYPE_SCRIPT = 0xD382BF57
RESOURCE_TYPE_STRING = 0x220557DA
RESOURCE_TYPE_IMAGE = 0x2F7D0004
RESOURCE_TYPE_MESH = 0x01661233

# Pack prefixes
PACK_PREFIXES = {
    "EP01": "Get to Work",
    "EP02": "Get Together",
    "EP03": "City Living",
    "EP04": "Cats & Dogs",
    "EP05": "Seasons",
    "EP06": "Get Famous",
    "EP07": "Island Living",
    "EP08": "Discover University",
    "EP09": "Eco Lifestyle",
    "EP10": "Snowy Escape",
    "EP11": "Cottage Living",
    "EP12": "High School Years",
    "EP13": "Growing Together",
    "EP14": "Horse Ranch",
    "EP15": "For Rent",
    "GP01": "Outdoor Retreat",
    "GP02": "Spa Day",
    "GP03": "Dine Out",
    "GP04": "Vampires",
    "GP05": "Parenthood",
    "GP06": "Jungle Adventure",
    "GP07": "StrangerVille",
    "GP08": "Realm of Magic",
    "GP09": "Star Wars: Journey to Batuu",
    "GP10": "Dream Home Decorator",
    "GP11": "My Wedding Stories",
    "GP12": "Werewolves",
    "SP01": "Luxury Party Stuff",
    "SP02": "Perfect Patio Stuff",
    "SP03": "Cool Kitchen Stuff",
    "SP04": "Spooky Stuff",
    # ... (many more stuff packs)
}
