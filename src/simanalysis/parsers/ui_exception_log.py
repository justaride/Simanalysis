"""Tolerant parser for Sims 4 lastUIException*.txt UI/desync logs."""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from simanalysis.models import UIExceptionReport, UIStackFrame

_REPORT_RE = re.compile(r"<report>(.*?)</report>", re.DOTALL)
_STACK_RE = re.compile(r"^\s*at\s+(.+?)\s*$", re.IGNORECASE)
_KEY_RE = re.compile(r"\b(?:key|resource)\s*:?\s*(\d{10,20})\b", re.IGNORECASE)
_MODDED_RE = re.compile(r"\bModded:\s*(True|False)\b", re.IGNORECASE)


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def _parse_stack_line(line: str) -> UIStackFrame | None:
    m = _STACK_RE.match(line)
    if not m:
        return None
    raw = m.group(1).strip()
    namespace = raw
    function: str | None = None
    if "/" in raw:
        namespace, function_part = raw.rsplit("/", 1)
        function = function_part.removesuffix("()")
    return UIStackFrame(raw=raw, namespace=namespace or None, function=function or None)


def _extract_modded(data: str) -> bool | None:
    m = _MODDED_RE.search(data)
    if not m:
        return None
    return m.group(1).lower() == "true"


def _signature(
    category_id: str | None,
    message: str,
    keys: list[int],
    stack: list[UIStackFrame],
) -> str:
    stack_sig = "|".join(frame.raw for frame in stack)
    payload = f"{category_id or ''}|{message}|{','.join(str(k) for k in keys)}|{stack_sig}"
    return hashlib.sha1(
        payload.encode("utf-8", "replace"),
        usedforsecurity=False,
    ).hexdigest()


def parse_ui_exception_file(path: str | Path) -> list[UIExceptionReport]:
    """Parse one lastUIException*.txt into UIExceptionReport objects."""
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    report_blocks = _REPORT_RE.findall(text)
    if "<report" in text and not report_blocks:
        raise ValueError("unterminated <report> in UI exception log")

    reports: list[UIExceptionReport] = []
    for block in report_blocks:
        data = _tag(block, "desyncdata") or ""
        if not data.strip():
            continue
        lines = [ln.strip() for ln in data.splitlines() if ln.strip()]
        message = lines[0] if lines else ""
        stack = [frame for line in lines if (frame := _parse_stack_line(line)) is not None]
        keys = list(dict.fromkeys(int(m) for m in _KEY_RE.findall(data)))
        category_id = _tag(block, "categoryid")

        report = UIExceptionReport(
            source_file=str(source),
            report_type=_tag(block, "type") or "unknown",
            message=message,
            category_id=category_id,
            keys=keys,
            stack=stack,
            created=_tag(block, "createtime"),
            game_version=_tag(block, "buildsignature"),
            session_id=_tag(block, "sessionid"),
            desync_id=_tag(block, "desyncid"),
            modded=_extract_modded(data),
            source_files=[str(source)],
        )
        report.signature = _signature(category_id, message, keys, stack)
        reports.append(report)

    return reports
