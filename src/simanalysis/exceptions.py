"""Custom exceptions for Simanalysis."""


class SimanalysisError(Exception):
    """Base exception for all Simanalysis errors."""


class ParsingError(SimanalysisError):
    """Raised when a file cannot be parsed."""


class DBPFError(ParsingError):
    """Raised when a DBPF package file is invalid."""


class TuningError(ParsingError):
    """Raised when a tuning XML file is invalid."""


class ScriptError(ParsingError):
    """Raised when a script file is invalid."""


class ConflictDetectionError(SimanalysisError):
    """Raised when conflict detection fails."""


class AnalysisError(SimanalysisError):
    """Raised when analysis fails."""


class ReportGenerationError(SimanalysisError):
    """Raised when report generation fails."""
