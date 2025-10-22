"""Custom exceptions for Simanalysis."""


class SimanalysisError(Exception):
    """Base exception for all Simanalysis errors."""

    pass


class ParsingError(SimanalysisError):
    """Raised when a file cannot be parsed."""

    pass


class DBPFError(ParsingError):
    """Raised when a DBPF package file is invalid."""

    pass


class TuningError(ParsingError):
    """Raised when a tuning XML file is invalid."""

    pass


class ScriptError(ParsingError):
    """Raised when a script file is invalid."""

    pass


class ConflictDetectionError(SimanalysisError):
    """Raised when conflict detection fails."""

    pass


class AnalysisError(SimanalysisError):
    """Raised when analysis fails."""

    pass


class ReportGenerationError(SimanalysisError):
    """Raised when report generation fails."""

    pass
