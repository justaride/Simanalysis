"""Tolerant parser for Sims 4 lastCrash*.txt native crash logs."""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import re
from pathlib import Path


_REPORT_RE = re.compile(r"<report>(.*?)</report>", re.DOTALL)
_MODDED_RE = re.compile(r"\bModded:\s*(True|False)\b", re.IGNORECASE)
_CURRENT_GAME_STATE_RE = re.compile(
    r"\bCurrent\s+Game\s+State:\s*([^\r\n<]+)",
    re.IGNORECASE,
)


@dataclass
class NativeCrashReport:
    """A native lastCrash report that is not attributed to a mod."""

    source_file: str
    created: str | None = None
    category_id: str | None = None
    build_signature: str | None = None
    modded: bool | None = None
    current_game_state: str | None = None
    stack_snippet: list[str] = field(default_factory=list)


def _tag(block: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def _extract_modded(data: str) -> bool | None:
    m = _MODDED_RE.search(data)
    if not m:
        return None
    return m.group(1).lower() == "true"


def _extract_current_game_state(block: str, data: str) -> str | None:
    tag_value = _tag(block, "currentgamestate") or _tag(block, "current_game_state")
    if tag_value:
        return tag_value
    m = _CURRENT_GAME_STATE_RE.search(data)
    return html.unescape(m.group(1)).strip() if m else None


def _stack_snippet(data: str) -> list[str]:
    lines = []
    for raw_line in data.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _MODDED_RE.search(line) or _CURRENT_GAME_STATE_RE.search(line):
            continue
        lines.append(line)
        if len(lines) >= 5:
            break
    return lines


def parse_native_crash_file(path: str | Path) -> list[NativeCrashReport]:
    """Parse one lastCrash*.txt into unattributed native crash reports."""
    source = Path(path)
    text = source.read_text(encoding="utf-8", errors="replace")
    report_blocks = _REPORT_RE.findall(text)
    if "<report" in text and not report_blocks:
        raise ValueError("unterminated <report> in native crash log")

    reports: list[NativeCrashReport] = []
    for block in report_blocks:
        data = _tag(block, "desyncdata") or ""
        reports.append(
            NativeCrashReport(
                source_file=str(source),
                created=_tag(block, "createtime"),
                category_id=_tag(block, "categoryid"),
                build_signature=_tag(block, "buildsignature"),
                modded=_extract_modded(data),
                current_game_state=_extract_current_game_state(block, data),
                stack_snippet=_stack_snippet(data),
            )
        )
    return reports
