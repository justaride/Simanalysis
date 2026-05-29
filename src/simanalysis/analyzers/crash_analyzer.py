"""Attribute Sims 4 crashes to the most-likely culprit .ts4script and rank across a library."""
from __future__ import annotations

from pathlib import Path

from simanalysis.models import (
    CrashAnalysisResult,
    CrashFinding,
    CrashReport,
    Suspect,
    TracebackFrame,
)
from simanalysis.parsers.script import ScriptAnalyzer

# Base-game path roots (lowercased, '/'-separated) — never a mod.
GAME_PREFIXES = ("core/sims4", "core/", "server/", "gamedata", "widgets", "olympus", "sims4/")
# Mods that hook broadly and appear in most stacks; not the per-crash culprit.
CURATED_FRAMEWORKS = ("betterexceptions", "xmlinjector", "xml injector")
# A mod implicated in >= this fraction of attributable crashes is treated as a framework.
FRAMEWORK_CRASH_FRACTION = 0.5


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./").lstrip("/").lower()


class CrashAnalyzer:
    def __init__(self, framework_fraction: float = FRAMEWORK_CRASH_FRACTION) -> None:
        self.framework_fraction = framework_fraction

    def build_module_index(self, mods_dir: "str | Path") -> dict[str, str]:
        """Map each installed .ts4script's internal module path -> the .ts4script filename."""
        index: dict[str, str] = {}
        for ts4 in Path(mods_dir).rglob("*.ts4script"):
            try:
                for module_path in ScriptAnalyzer(ts4).module_paths:
                    index[_norm(module_path)] = ts4.name
            except Exception:
                continue  # corrupt/non-zip archive — skip
        return index

    def classify_frame(self, frame: TracebackFrame, index: dict[str, str]) -> None:
        norm = _norm(frame.raw_path)
        if any(norm.startswith(g) or f"/{g}" in norm for g in GAME_PREFIXES):
            frame.kind = "game"
            return
        if ".ts4script/" in norm:
            frame.kind = "mod"
            frame.module_path = norm
            frame.mod_name = norm.split(".ts4script/")[0].split("/")[-1] + ".ts4script"
            return
        best: "str | None" = None
        for key in index:
            if norm == key or norm.endswith("/" + key):
                if best is None or len(key) > len(best):
                    best = key
        if best is not None:
            frame.kind = "mod"
            frame.module_path = best
            frame.mod_name = index[best]
            return
        frame.kind = "unknown"

    def analyze(
        self, reports: list[CrashReport], index: dict[str, str]
    ) -> CrashAnalysisResult:
        for r in reports:
            for f in r.frames:
                self.classify_frame(f, index)

        total = len(reports) or 1
        mod_in_crash: dict[str, int] = {}
        attributable = 0
        for r in reports:
            mods = {f.mod_name for f in r.frames if f.kind == "mod" and f.mod_name}
            if mods:
                attributable += 1
            for m in mods:
                mod_in_crash[m] = mod_in_crash.get(m, 0) + 1

        frameworks: set[str] = set()
        for m, count in mod_in_crash.items():
            ml = m.lower()
            if any(cf in ml for cf in CURATED_FRAMEWORKS) or (count / total) > self.framework_fraction:
                frameworks.add(m)

        findings: list[CrashFinding] = []
        top_counts: dict[str, int] = {}
        base_game_only = 0

        for r in reports:
            mod_frames = [f for f in r.frames if f.kind == "mod" and f.mod_name]
            if not mod_frames:
                base_game_only += 1
                findings.append(CrashFinding(report=r))
                continue
            ordered = list(reversed(mod_frames))  # most-recent-call-last => deepest first
            non_fw = [f for f in ordered if f.mod_name not in frameworks]
            picked = non_fw if non_fw else ordered

            suspects: list[Suspect] = []
            seen: set[str] = set()
            for i, f in enumerate(picked):
                if f.mod_name in seen:
                    continue
                seen.add(f.mod_name)
                if f.mod_name in frameworks:
                    conf = "low"
                elif i == 0 and f.module_path in index:
                    conf = "high"
                else:
                    conf = "medium"
                suspects.append(
                    Suspect(
                        mod_name=f.mod_name,
                        confidence=conf,
                        reason=f"implicated at: {f.raw_path}",
                        evidence=[f],
                    )
                )
            if suspects:
                top_counts[suspects[0].mod_name] = top_counts.get(suspects[0].mod_name, 0) + 1
            findings.append(CrashFinding(report=r, suspects=suspects))

        ranked = sorted(
            [
                {"mod": m, "top_suspect_count": top_counts[m], "crash_count": mod_in_crash.get(m, 0)}
                for m in top_counts
            ],
            key=lambda d: (d["top_suspect_count"], d["crash_count"]),
            reverse=True,
        )
        summary = {
            "reports": len(reports),
            "attributable": attributable,
            "base_game_only": base_game_only,
            "frameworks_downweighted": sorted(frameworks),
            "game_versions": sorted({r.game_version for r in reports if r.game_version}),
        }
        return CrashAnalysisResult(summary=summary, ranked_mods=ranked, findings=findings)
