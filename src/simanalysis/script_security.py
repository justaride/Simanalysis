"""Static TS4Script security review signals.

This module inspects `.ts4script` archives as ZIP files and Python source text.
It never imports, executes, extracts, or decompiles mod code.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile, is_zipfile

NETWORK_IMPORTS = {
    "aiohttp",
    "asyncio.streams",
    "ftplib",
    "http",
    "http.client",
    "requests",
    "smtplib",
    "socket",
    "ssl",
    "urllib",
    "urllib.request",
    "websocket",
    "websockets",
}
SUBPROCESS_IMPORTS = {"subprocess"}
OBFUSCATION_IMPORTS = {"base64", "marshal"}
UNEXPECTED_BINARY_SUFFIXES = {
    ".bin",
    ".dll",
    ".dylib",
    ".exe",
    ".pyd",
    ".so",
}
_BASE64ISH_RE = re.compile(r"^[A-Za-z0-9+/=\s]{300,}$")


def _signal(
    signal_id: str,
    severity: str,
    message: str,
    *,
    path: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    signal: dict[str, Any] = {
        "id": signal_id,
        "severity": severity,
        "message": message,
    }
    if path is not None:
        signal["path"] = path
    if detail is not None:
        signal["detail"] = detail
    return signal


def _unsafe_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts


def _import_root(module: str) -> str:
    parts = module.split(".")
    return parts[0] if parts else module


def _is_imported(import_name: str, candidates: set[str]) -> bool:
    return import_name in candidates or _import_root(import_name) in candidates


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _module_signals(module_path: str, source: str) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            _signal(
                "python_parse_error",
                "medium",
                "Python source could not be parsed for static script-risk review.",
                path=module_path,
                detail=str(exc),
            )
        ]

    seen: set[tuple[str, str]] = set()

    def add(signal: dict[str, Any]) -> None:
        key = (str(signal["id"]), str(signal.get("path") or ""))
        if key not in seen:
            seen.add(key)
            signals.append(signal)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_imported(alias.name, NETWORK_IMPORTS):
                    add(
                        _signal(
                            "network_import",
                            "elevated",
                            "Script imports network-capable libraries; review intent.",
                            path=module_path,
                            detail=alias.name,
                        )
                    )
                if _is_imported(alias.name, SUBPROCESS_IMPORTS):
                    add(
                        _signal(
                            "subprocess_import",
                            "elevated",
                            "Script imports subprocess controls; review intent.",
                            path=module_path,
                            detail=alias.name,
                        )
                    )
                if _is_imported(alias.name, OBFUSCATION_IMPORTS):
                    add(
                        _signal(
                            "obfuscation_hint",
                            "elevated",
                            "Script imports modules often used to pack or decode code.",
                            path=module_path,
                            detail=alias.name,
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            if _is_imported(module, NETWORK_IMPORTS):
                add(
                    _signal(
                        "network_import",
                        "elevated",
                        "Script imports network-capable libraries; review intent.",
                        path=module_path,
                        detail=module,
                    )
                )
            if _is_imported(module, SUBPROCESS_IMPORTS):
                add(
                    _signal(
                        "subprocess_import",
                        "elevated",
                        "Script imports subprocess controls; review intent.",
                        path=module_path,
                        detail=module,
                    )
                )
            if _is_imported(module, OBFUSCATION_IMPORTS):
                add(
                    _signal(
                        "obfuscation_hint",
                        "elevated",
                        "Script imports modules often used to pack or decode code.",
                        path=module_path,
                        detail=module,
                    )
                )
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"eval", "exec", "compile"}:
                add(
                    _signal(
                        "dynamic_execution",
                        "elevated",
                        "Script uses dynamic code execution APIs; review intent.",
                        path=module_path,
                        detail=name,
                    )
                )
            if name in {
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.run",
                "os.system",
                "os.popen",
            }:
                add(
                    _signal(
                        "subprocess_call",
                        "elevated",
                        "Script invokes subprocess or shell APIs; review intent.",
                        path=module_path,
                        detail=name,
                    )
                )
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _BASE64ISH_RE.match(node.value)
        ):
            add(
                _signal(
                    "obfuscation_hint",
                    "elevated",
                    "Script contains a long encoded-looking string.",
                    path=module_path,
                )
            )

    return signals


def analyze_script_archive(path: Path | str) -> dict[str, Any]:
    """Return static script-risk signals for one `.ts4script` archive."""
    script_path = Path(path)
    if not is_zipfile(script_path):
        return {
            "status": "unreadable_archive",
            "path": str(script_path),
            "risk_level": "unknown",
            "module_count": 0,
            "elevated_signal_count": 0,
            "signals": [
                _signal(
                    "archive_unreadable",
                    "medium",
                    "Script archive could not be read as a ZIP file.",
                    path=script_path.name,
                )
            ],
            "executes_code": False,
        }

    try:
        with ZipFile(script_path) as archive:
            names = archive.namelist()
            unsafe_names = [name for name in names if _unsafe_member(name)]
            if unsafe_names:
                return {
                    "status": "blocked",
                    "path": str(script_path),
                    "risk_level": "elevated",
                    "module_count": 0,
                    "elevated_signal_count": len(unsafe_names),
                    "signals": [
                        _signal(
                            "archive_path_traversal",
                            "elevated",
                            "Script archive contains absolute or parent-directory paths.",
                            path=script_path.name,
                            detail=", ".join(unsafe_names),
                        )
                    ],
                    "executes_code": False,
                }

            signals: list[dict[str, Any]] = []
            module_count = 0
            for name in names:
                suffix = PurePosixPath(name).suffix.lower()
                if suffix in UNEXPECTED_BINARY_SUFFIXES:
                    signals.append(
                        _signal(
                            "unexpected_binary",
                            "elevated",
                            "Script archive contains an unexpected native/binary file.",
                            path=name,
                        )
                    )
                if suffix != ".py":
                    continue
                module_count += 1
                source = archive.read(name).decode("utf-8", errors="replace")
                signals.extend(_module_signals(name, source))
    except (BadZipFile, OSError) as exc:
        return {
            "status": "unreadable_archive",
            "path": str(script_path),
            "risk_level": "unknown",
            "module_count": 0,
            "elevated_signal_count": 0,
            "signals": [
                _signal(
                    "archive_unreadable",
                    "medium",
                    "Script archive could not be opened for static review.",
                    path=script_path.name,
                    detail=str(exc),
                )
            ],
            "executes_code": False,
        }

    elevated_signal_count = sum(1 for signal in signals if signal["severity"] == "elevated")
    return {
        "status": "reviewed",
        "path": str(script_path),
        "risk_level": "elevated" if elevated_signal_count else "low",
        "module_count": module_count,
        "elevated_signal_count": elevated_signal_count,
        "signals": signals,
        "executes_code": False,
    }


def summarize_script_security(root: Path | str) -> dict[str, Any]:
    """Summarize static script-risk signals for a Mods-like folder."""
    base = Path(root).expanduser().resolve()
    if not base.exists() or not base.is_dir():
        return {
            "status": "missing",
            "root_path": str(base),
            "script_count": 0,
            "risk_counts": {},
            "elevated_count": 0,
            "items": [],
            "executes_code": False,
        }

    items: list[dict[str, Any]] = []
    for script_path in sorted(
        base.rglob("*.ts4script"), key=lambda item: item.as_posix().casefold()
    ):
        if script_path.is_symlink() or not script_path.is_file():
            continue
        review = analyze_script_archive(script_path)
        items.append(
            {
                "name": script_path.name,
                "relative_path": script_path.relative_to(base).as_posix(),
                "path": str(script_path),
                "script_security": review,
            }
        )

    risk_counts = Counter(str(item["script_security"]["risk_level"]) for item in items)
    return {
        "status": "available",
        "root_path": str(base),
        "script_count": len(items),
        "risk_counts": dict(sorted(risk_counts.items())),
        "elevated_count": int(risk_counts.get("elevated", 0)),
        "items": items,
        "executes_code": False,
    }
