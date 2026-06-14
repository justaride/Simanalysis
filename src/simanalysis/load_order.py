"""Resource.cfg parsing and conservative package load-order simulation."""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DEFAULT_RESOURCE_CFG_TEXT = """Priority 500
PackedFile *.package
PackedFile */*.package
PackedFile */*/*.package
PackedFile */*/*/*.package
PackedFile */*/*/*/*.package
PackedFile */*/*/*/*/*.package
DirectoryFiles unpackedmod autoupdate
"""


@dataclass(frozen=True)
class ResourceCfgPackedFileRule:
    """One PackedFile rule scoped by the active Resource.cfg priority."""

    pattern: str
    priority: int
    line_number: int
    sequence: int


@dataclass(frozen=True)
class ResourceCfg:
    """Parsed Resource.cfg content used for package load-order simulation."""

    path: Optional[Path]
    packed_files: tuple[ResourceCfgPackedFileRule, ...]
    directory_files: tuple[tuple[str, ...], ...] = ()
    warnings: tuple[str, ...] = ()
    used_default: bool = False


@dataclass(frozen=True)
class LoadedPackage:
    """A package matched by Resource.cfg with its simulated load position."""

    path: Path
    relative_path: str
    load_index: int
    priority: int
    rule_pattern: str
    rule_line_number: int


@dataclass(frozen=True)
class LoadOrderParticipant:
    """A conflict participant's load-order position."""

    path: Path
    mod_name: str
    relative_path: str
    load_index: int
    priority: int
    rule_pattern: str


@dataclass(frozen=True)
class LoadOrderWinner:
    """Winner verdict for a set of conflicting package paths."""

    winner_path: Optional[Path]
    winner_relative_path: Optional[str]
    winner_mod_name: Optional[str]
    confidence: str
    reason: str
    participants: tuple[LoadOrderParticipant, ...] = ()
    unmatched_relative_paths: tuple[str, ...] = ()


@dataclass(frozen=True)
class LoadOrderPlan:
    """Simulated package load order for a Mods folder."""

    mods_dir: Path
    resource_cfg: ResourceCfg
    entries: tuple[LoadedPackage, ...]
    unmatched_relative_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def explain_winner(self, packages: Iterable[Any]) -> LoadOrderWinner:
        """Explain the simulated winner among a set of package paths or Mod objects."""
        matched: list[LoadOrderParticipant] = []
        unmatched: list[str] = []

        for item in packages:
            path = _coerce_package_path(item)
            mod_name = _coerce_mod_name(item, path)
            entry = self.entry_for(path)
            if entry is None:
                unmatched.append(self.relative_path_for(path))
                continue

            matched.append(
                LoadOrderParticipant(
                    path=entry.path,
                    mod_name=mod_name,
                    relative_path=entry.relative_path,
                    load_index=entry.load_index,
                    priority=entry.priority,
                    rule_pattern=entry.rule_pattern,
                )
            )

        matched.sort(key=lambda participant: participant.load_index)
        if not matched:
            return LoadOrderWinner(
                winner_path=None,
                winner_relative_path=None,
                winner_mod_name=None,
                confidence="none",
                reason="no conflict participants matched Resource.cfg package rules",
                unmatched_relative_paths=tuple(sorted(set(unmatched), key=str.casefold)),
            )

        winner = matched[-1]
        confidence = (
            "partial"
            if unmatched
            else ("default" if self.resource_cfg.used_default else "configured")
        )

        return LoadOrderWinner(
            winner_path=winner.path,
            winner_relative_path=winner.relative_path,
            winner_mod_name=winner.mod_name,
            confidence=confidence,
            reason="winner inferred from Resource.cfg priority and path order",
            participants=tuple(matched),
            unmatched_relative_paths=tuple(sorted(set(unmatched), key=str.casefold)),
        )

    def entry_for(self, path: Path) -> Optional[LoadedPackage]:
        """Return the simulated load-order entry for a package path."""
        normalized = _normalize_absolute(path, self.mods_dir)
        for entry in self.entries:
            if _normalize_absolute(entry.path, self.mods_dir) == normalized:
                return entry
        return None

    def relative_path_for(self, path: Path) -> str:
        """Return a stable POSIX relative path for reporting."""
        absolute = _normalize_absolute(path, self.mods_dir)
        try:
            return absolute.relative_to(self.mods_dir).as_posix()
        except ValueError:
            return absolute.as_posix()


def parse_resource_cfg_text(
    text: str,
    *,
    path: Optional[Path] = None,
    used_default: bool = False,
    initial_priority: int = 500,
) -> ResourceCfg:
    """Parse Resource.cfg text into priority-scoped PackedFile rules."""
    packed_files: list[ResourceCfgPackedFileRule] = []
    directory_files: list[tuple[str, ...]] = []
    warnings: list[str] = []
    current_priority = initial_priority

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith(("#", "//")):
            continue

        parts = stripped.split()
        directive = parts[0].lower()
        args = parts[1:]

        if directive == "priority":
            if len(args) != 1:
                warnings.append(f"Line {line_number}: malformed Priority directive")
                continue
            try:
                current_priority = int(args[0])
            except ValueError:
                warnings.append(f"Line {line_number}: invalid Priority value: {args[0]}")
            continue

        if directive == "packedfile":
            if len(args) != 1:
                warnings.append(f"Line {line_number}: malformed PackedFile directive")
                continue
            packed_files.append(
                ResourceCfgPackedFileRule(
                    pattern=_normalize_rule_pattern(args[0]),
                    priority=current_priority,
                    line_number=line_number,
                    sequence=len(packed_files),
                )
            )
            continue

        if directive == "directoryfiles":
            directory_files.append(tuple(args))
            continue

        warnings.append(f"Line {line_number}: unsupported Resource.cfg directive: {parts[0]}")

    return ResourceCfg(
        path=path,
        packed_files=tuple(packed_files),
        directory_files=tuple(directory_files),
        warnings=tuple(warnings),
        used_default=used_default,
    )


def read_resource_cfg(mods_dir: Path) -> ResourceCfg:
    """Read root Mods/Resource.cfg or fall back to bundled default patterns."""
    cfg_path = Path(mods_dir).expanduser() / "Resource.cfg"
    if cfg_path.exists():
        return parse_resource_cfg_text(
            cfg_path.read_text(encoding="utf-8", errors="replace"),
            path=cfg_path,
        )

    cfg = parse_resource_cfg_text(DEFAULT_RESOURCE_CFG_TEXT, path=cfg_path, used_default=True)
    return ResourceCfg(
        path=cfg.path,
        packed_files=cfg.packed_files,
        directory_files=cfg.directory_files,
        warnings=("Mods/Resource.cfg not found; using bundled default Sims 4 patterns",),
        used_default=True,
    )


def simulate_package_load_order(
    mods_dir: Path,
    package_paths: Iterable[Path],
    *,
    resource_cfg: Optional[ResourceCfg] = None,
) -> LoadOrderPlan:
    """Simulate package load order from Resource.cfg PackedFile rules.

    The simulator is intentionally conservative: it reports a deterministic
    Resource.cfg-based order and labels confidence instead of claiming exact
    engine behavior when files are unmatched or only default rules were used.
    """
    mods_root = Path(mods_dir).expanduser().resolve(strict=False)
    cfg = resource_cfg if resource_cfg is not None else read_resource_cfg(mods_root)
    entries: list[LoadedPackage] = []
    unmatched: list[str] = []
    warnings = list(cfg.warnings)

    for package_path in package_paths:
        absolute = _normalize_absolute(Path(package_path), mods_root)
        relative_path = _relative_posix(absolute, mods_root)
        if relative_path is None:
            warnings.append(f"Package path is outside Mods folder: {absolute}")
            unmatched.append(absolute.as_posix())
            continue

        if absolute.suffix.lower() != ".package":
            warnings.append(f"Skipping non-package path in load-order simulation: {relative_path}")
            continue

        rule = _best_matching_rule(relative_path, cfg.packed_files)
        if rule is None:
            unmatched.append(relative_path)
            continue

        entries.append(
            LoadedPackage(
                path=absolute,
                relative_path=relative_path,
                load_index=-1,
                priority=rule.priority,
                rule_pattern=rule.pattern,
                rule_line_number=rule.line_number,
            )
        )

    entries.sort(
        key=lambda entry: (
            entry.priority,
            _rule_sequence(entry.rule_pattern, entry.rule_line_number, cfg.packed_files),
            entry.relative_path.casefold(),
            entry.relative_path,
        )
    )
    indexed_entries = tuple(
        LoadedPackage(
            path=entry.path,
            relative_path=entry.relative_path,
            load_index=index,
            priority=entry.priority,
            rule_pattern=entry.rule_pattern,
            rule_line_number=entry.rule_line_number,
        )
        for index, entry in enumerate(entries)
    )

    return LoadOrderPlan(
        mods_dir=mods_root,
        resource_cfg=cfg,
        entries=indexed_entries,
        unmatched_relative_paths=tuple(sorted(set(unmatched), key=str.casefold)),
        warnings=tuple(warnings),
    )


def _best_matching_rule(
    relative_path: str,
    rules: tuple[ResourceCfgPackedFileRule, ...],
) -> Optional[ResourceCfgPackedFileRule]:
    matches = [rule for rule in rules if _packed_file_match(rule.pattern, relative_path)]
    if not matches:
        return None
    return max(matches, key=lambda rule: (rule.priority, rule.sequence))


def _packed_file_match(pattern: str, relative_path: str) -> bool:
    regex = _packed_file_pattern_regex(pattern)
    return re.fullmatch(regex, relative_path, flags=re.IGNORECASE) is not None


def _packed_file_pattern_regex(pattern: str) -> str:
    pieces: list[str] = []
    for char in pattern:
        if char == "*":
            pieces.append("[^/]*")
        elif char == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(char))
    return "".join(pieces)


def _rule_sequence(
    pattern: str,
    line_number: int,
    rules: tuple[ResourceCfgPackedFileRule, ...],
) -> int:
    for rule in rules:
        if rule.pattern == pattern and rule.line_number == line_number:
            return rule.sequence
    return len(rules)


def _normalize_rule_pattern(pattern: str) -> str:
    return pattern.strip().replace("\\", "/").lstrip("./")


def _normalize_absolute(path: Path, mods_dir: Path) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        expanded = mods_dir / expanded
    return expanded.resolve(strict=False)


def _relative_posix(path: Path, mods_dir: Path) -> Optional[str]:
    try:
        return path.relative_to(mods_dir).as_posix()
    except ValueError:
        return None


def _coerce_package_path(item: Any) -> Path:
    path = getattr(item, "path", item)
    return Path(path)


def _coerce_mod_name(item: Any, path: Path) -> str:
    name = getattr(item, "name", None)
    return str(name) if name else path.name
