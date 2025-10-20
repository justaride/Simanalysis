"""Helpers for extracting metadata from Sims 4 `.ts4script` archives."""
from __future__ import annotations

import marshal
import re
import types
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Set
from zipfile import ZipFile

PYTHON_MAGIC_VERSIONS = {
    b"\x16\r\r\n": "3.7",
    b"\x17\r\r\n": "3.7",
    b"\x33\r\r\n": "3.8",
    b"\x42\r\r\n": "3.9",
    b"\x50\r\r\n": "3.10",
}

FRAMEWORK_SIGNATURES = {
    "xml_injector": tuple(sig.encode("utf-8") for sig in ("xmlinjector", "xml_injector", "XmlInjector")),
    "mc_command_center": tuple(sig.encode("utf-8") for sig in ("mc_cmd_center", "mccc", "mc_woohoo")),
}

COMMAND_PATTERN = re.compile(rb"sims4\.commands\.Command")
INJECTION_PATTERN = re.compile(rb"injector", re.IGNORECASE)


@dataclass
class ScriptModMetadata:
    path: Path
    python_versions: Set[str] = field(default_factory=set)
    compilation_dates: List[datetime] = field(default_factory=list)
    detected_frameworks: Set[str] = field(default_factory=set)
    entry_points: Set[str] = field(default_factory=set)
    injection_signatures: Set[str] = field(default_factory=set)
    module_names: Set[str] = field(default_factory=set)
    file_count: int = 0


def analyze_script_mod(path: Path) -> ScriptModMetadata:
    path = Path(path)
    metadata = ScriptModMetadata(path=path)

    with ZipFile(path, "r") as archive:
        file_count = 0
        for info in archive.infolist():
            if info.is_dir():
                continue
            file_count += 1
            module_name = _module_name_from_zipinfo(info)
            if module_name:
                metadata.module_names.add(module_name)
            if not info.filename.lower().endswith((".pyc", ".pyo")):
                data = archive.read(info.filename)
                _scan_text_for_frameworks(data, metadata)
                continue

            data = archive.read(info.filename)
            _extract_bytecode_metadata(data, metadata)

        metadata.file_count = file_count

    return metadata


def _module_name_from_zipinfo(info) -> str:
    name = info.filename
    if name.startswith("__MACOSX/"):
        return ""
    if name.endswith("/__init__.pyc"):
        name = name[: -len("/__init__.pyc")]
    name = name.replace("/", ".")
    return name.rsplit(".", 1)[0]


def _scan_text_for_frameworks(data: bytes, metadata: ScriptModMetadata) -> None:
    lower = data.lower()
    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        if any(signature in lower for signature in signatures):
            metadata.detected_frameworks.add(framework)


def _extract_bytecode_metadata(data: bytes, metadata: ScriptModMetadata) -> None:
    if len(data) < 16:
        return

    magic = data[:4]
    python_version = PYTHON_MAGIC_VERSIONS.get(magic)
    if python_version:
        metadata.python_versions.add(python_version)

    timestamp_bytes = data[8:12]
    timestamp = int.from_bytes(timestamp_bytes, "little", signed=False)
    if timestamp:
        metadata.compilation_dates.append(datetime.fromtimestamp(timestamp))

    if COMMAND_PATTERN.search(data):
        metadata.entry_points.add("sims4.commands.Command")
    if INJECTION_PATTERN.search(data):
        metadata.injection_signatures.add("injector")

    lower_data = data.lower()
    for framework, signatures in FRAMEWORK_SIGNATURES.items():
        if any(signature in lower_data for signature in signatures):
            metadata.detected_frameworks.add(framework)

    try:
        code = marshal.loads(data[16:])
    except Exception:
        return

    for name in _walk_code_objects(code):
        if name.startswith("sims4.commands"):
            metadata.entry_points.add(name)


def _walk_code_objects(code: types.CodeType) -> Iterator[str]:
    yield from code.co_names
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _walk_code_objects(const)


def analyze_scripts(paths: Iterable[Path]) -> List[ScriptModMetadata]:
    return [analyze_script_mod(path) for path in paths]
