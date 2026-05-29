"""Tolerant parser for Sims 4 lastException*.txt crash logs (Better-Exceptions or vanilla XML)."""
from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

from simanalysis.models import CrashReport, TracebackFrame

_REPORT_RE = re.compile(r"<report>(.*?)</report>", re.DOTALL)
_ADVICE_RE = re.compile(r"<Advice>(.*?)</Advice>", re.DOTALL)
_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\S+))?')
_EXC_RE = re.compile(r"\(([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\)")
_CREATOR_RE = re.compile(r"^\s*\[([^\]]+)\]")


def _tag(block: str, name: str) -> "str | None":
    m = re.search(rf"<{name}>(.*?)</{name}>", block, re.DOTALL)
    return html.unescape(m.group(1)).strip() if m else None


def parse_exception_file(path: "str | Path") -> list[CrashReport]:
    """Parse one lastException*.txt into deduped CrashReports (script exceptions only)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    advice_m = _ADVICE_RE.search(text)
    be_advice = html.unescape(advice_m.group(1)).strip() if advice_m else None

    reports: list[CrashReport] = []
    seen: set[str] = set()

    for block in _REPORT_RE.findall(text):
        data = _tag(block, "desyncdata") or ""
        if "Traceback" not in data:
            continue  # pure UI/desync, no script traceback -> out of v1 scope
        frames = [
            TracebackFrame(raw_path=p, line=int(ln), func=fn or None)
            for (p, ln, fn) in _FRAME_RE.findall(data)
        ]
        if not frames:
            continue

        lines = [ln for ln in data.splitlines() if ln.strip()]
        message = lines[0] if lines else ""
        exc_m = _EXC_RE.search(message) or _EXC_RE.search(data)
        cre_m = _CREATOR_RE.match(message)

        report = CrashReport(
            source_file=str(path),
            report_type=_tag(block, "type") or "unknown",
            message=message,
            frames=frames,
            exception_class=exc_m.group(1) if exc_m else None,
            creator_tag=cre_m.group(1) if cre_m else None,
            created=_tag(block, "createtime"),
            game_version=_tag(block, "buildsignature"),
            be_advice=be_advice,
        )
        report.signature = hashlib.sha1(
            (
                str(report.exception_class)
                + report.message
                + "|".join(f.raw_path for f in frames)
            ).encode("utf-8", "replace")
        ).hexdigest()

        if report.signature in seen:
            continue
        seen.add(report.signature)
        reports.append(report)

    return reports
