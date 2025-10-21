"""Simanalysis package exports."""

from importlib import metadata

from .analyzer import AnalysisResult, ModAnalyzer, ModConflict

try:
    __version__ = metadata.version("simanalysis")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback during dev installs
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "AnalysisResult",
    "ModAnalyzer",
    "ModConflict",
]
