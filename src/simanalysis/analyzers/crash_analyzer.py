"""Attribute Sims 4 crashes to the most-likely culprit .ts4script and rank across a library."""

from __future__ import annotations

import zipfile
from pathlib import Path

from simanalysis.models import (
    CrashAnalysisResult,
    CrashFinding,
    CrashReport,
    Suspect,
    TracebackFrame,
)

# Leading path segments that mark a base-game module (never a mod).
GAME_ROOTS = ("core", "server", "gamedata", "widgets", "olympus", "sims4")
# Mods that hook broadly and appear in most stacks; not the per-crash culprit.
CURATED_FRAMEWORKS = ("betterexceptions", "xmlinjector", "xml injector")
# A mod is treated as a broadly-hooking framework (and down-weighted as a per-crash
# culprit) when it is implicated in MORE THAN FRAMEWORK_CRASH_FRACTION of all crash reports
# AND is the deepest (culprit) frame in fewer than FRAMEWORK_DEEPEST_FRACTION of its crashes
# — i.e. a frequent pass-through hook, not the thing actually crashing. (Tunable; see Task 7.)
FRAMEWORK_CRASH_FRACTION = 0.5
FRAMEWORK_DEEPEST_FRACTION = 0.3


def _norm(p: str) -> str:
    s = p.replace("\\", "/")
    if s.startswith("./"):
        s = s[2:]  # drop a leading './' (NOT lstrip, which strips '.'/'/' chars, mangling dot-dirs)
    return s.lstrip("/").lower()


class CrashAnalyzer:
    def __init__(
        self,
        framework_fraction: float = FRAMEWORK_CRASH_FRACTION,
        framework_deepest_fraction: float = FRAMEWORK_DEEPEST_FRACTION,
    ) -> None:
        self.framework_fraction = framework_fraction
        self.framework_deepest_fraction = framework_deepest_fraction

    def build_module_index(self, mods_dir: str | Path) -> dict[str, str]:
        """Map each installed .ts4script's internal module path -> the .ts4script filename.

        Sims 4 scripts ship COMPILED modules (.pyc); traceback frames cite the original
        .py source path, so .pyc entries are normalized to .py before indexing.
        """
        index: dict[str, str] = {}
        for ts4 in Path(mods_dir).rglob("*.ts4script"):
            try:
                with zipfile.ZipFile(ts4) as zf:
                    names = zf.namelist()
            except Exception:
                continue  # corrupt/non-zip archive — skip
            for name in names:
                if name.endswith(".pyc"):
                    index[_norm(name[:-1])] = ts4.name  # 'module.pyc' -> 'module.py'
                elif name.endswith(".py"):
                    index[_norm(name)] = ts4.name
        return index

    def classify_frame(self, frame: TracebackFrame, index: dict[str, str]) -> None:
        norm = _norm(frame.raw_path)
        # 1. Explicit in-archive path (…/<name>.ts4script/<module>) — the strongest signal.
        if ".ts4script/" in norm:
            head, tail = norm.split(".ts4script/", 1)
            frame.kind = "mod"
            frame.module_path = tail
            frame.mod_name = head.split("/")[-1] + ".ts4script"
            return
        # 2. Known installed mod: frame path ends with an indexed module path (longest wins).
        #    Checked BEFORE the game heuristic so an installed mod whose own package mirrors
        #    the game tree (e.g. '.../server/...') is never shadowed as base-game.
        best: str | None = None
        for key in index:
            if (norm == key or norm.endswith("/" + key)) and (best is None or len(key) > len(best)):
                best = key
        if best is not None:
            frame.kind = "mod"
            frame.module_path = best
            frame.mod_name = index[best]
            return
        # 3. Base-game module: a known game root as the LEADING path segment (anchored, so a
        #    '/server/' deeper in a mod's own path no longer false-matches as base-game).
        if norm.split("/", 1)[0] in GAME_ROOTS:
            frame.kind = "game"
            return
        frame.kind = "unknown"

    def analyze(self, reports: list[CrashReport], index: dict[str, str]) -> CrashAnalysisResult:
        for r in reports:
            for f in r.frames:
                self.classify_frame(f, index)

        total = len(reports) or 1
        mod_in_crash: dict[str, int] = {}
        deepest_count: dict[str, int] = {}
        attributable = 0
        for r in reports:
            mod_frames = [f for f in r.frames if f.kind == "mod" and f.mod_name]
            mods = {f.mod_name for f in mod_frames if f.mod_name}
            if mods:
                attributable += 1
            for m in mods:
                mod_in_crash[m] = mod_in_crash.get(m, 0) + 1
            if mod_frames:  # deepest mod frame = this crash's culprit candidate
                deepest = mod_frames[-1].mod_name
                if deepest:
                    deepest_count[deepest] = deepest_count.get(deepest, 0) + 1

        frameworks: set[str] = set()
        for m, count in mod_in_crash.items():
            ml = m.lower()
            frequent = (count / total) > self.framework_fraction
            rarely_deepest = (deepest_count.get(m, 0) / count) < self.framework_deepest_fraction
            if any(cf in ml for cf in CURATED_FRAMEWORKS) or (frequent and rarely_deepest):
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
                mod_name: str = f.mod_name  # type: ignore[assignment]  # picked only has mod frames
                if mod_name in seen:
                    continue
                seen.add(mod_name)
                if mod_name in frameworks:
                    conf = "low"
                elif i == 0 and f.module_path in index:
                    conf = "high"
                else:
                    conf = "medium"
                suspects.append(
                    Suspect(
                        mod_name=mod_name,
                        confidence=conf,
                        reason=f"implicated at: {f.raw_path}",
                        evidence=[f],
                    )
                )
            if suspects:
                top_counts[suspects[0].mod_name] = top_counts.get(suspects[0].mod_name, 0) + 1
            findings.append(CrashFinding(report=r, suspects=suspects))

        ranked: list[dict] = sorted(
            [
                {
                    "mod": m,
                    "top_suspect_count": top_counts[m],
                    "crash_count": mod_in_crash.get(m, 0),
                }
                for m in top_counts
            ],
            key=lambda d: (-d["top_suspect_count"], -d["crash_count"], d["mod"]),
        )
        summary = {
            "reports": len(reports),
            "attributable": attributable,
            "base_game_only": base_game_only,
            "frameworks_downweighted": sorted(frameworks),
            "game_versions": sorted({r.game_version for r in reports if r.game_version}),
        }
        return CrashAnalysisResult(summary=summary, ranked_mods=ranked, findings=findings)
