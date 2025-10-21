"""Core immutable resource models for Simanalysis."""

from __future__ import annotations

from pathlib import Path
from typing import Set

from pydantic import BaseModel, ConfigDict, Field


class ResourceKey(BaseModel):
    """Identifier for a DBPF resource entry."""

    model_config = ConfigDict(frozen=True)

    type_id: int
    group_id: int
    instance_id: int

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"{self.type_id:08X}:{self.group_id:08X}:{self.instance_id:08X}"

    @classmethod
    def from_hex(cls, raw: str) -> "ResourceKey":
        """Create a :class:`ResourceKey` from a ``TTTTTTTT:GGGGGGGG:IIIIIIII`` string."""

        parts = raw.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid resource key format: {raw!r}")
        try:
            type_id, group_id, instance_id = (int(part, 16) for part in parts)
        except ValueError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Resource key components must be hexadecimal: {raw!r}") from exc
        return cls(type_id=type_id, group_id=group_id, instance_id=instance_id)


class ResourceEntry(BaseModel):
    """Metadata describing a resource stored inside a package."""

    model_config = ConfigDict(frozen=True)

    key: ResourceKey
    resource_type: str | None = None
    size: int
    path_in_package: str | None = None


class PackageIndex(BaseModel):
    """Representation of all entries inside a package archive."""

    model_config = ConfigDict(frozen=True)

    package_path: Path
    entries: list[ResourceEntry] = Field(default_factory=list)
    sha256: str


class TuningNode(BaseModel):
    """Normalized view of an extracted tuning XML definition."""

    model_config = ConfigDict(frozen=True)

    tuning_id: str
    tuning_type: str
    references: Set[str] = Field(default_factory=set)
    raw_xml: str


def normalize_tuning_id(raw: str) -> str:
    """Normalize tuning identifiers by removing whitespace and lowercasing."""

    return "".join(raw.split()).lower()
