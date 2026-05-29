import zipfile
from pathlib import Path

from simanalysis.analyzers.crash_analyzer import CrashAnalyzer
from simanalysis.models import CrashReport, TracebackFrame


def _report(*frame_paths: str) -> CrashReport:
    return CrashReport(
        source_file="x.txt",
        report_type="desync",
        message="boom (ValueError)",
        frames=[TracebackFrame(raw_path=p) for p in frame_paths],
    )


def test_build_module_index_from_ts4script(tmp_path: Path):
    ts = tmp_path / "CoolMod.ts4script"
    with zipfile.ZipFile(ts, "w") as zf:
        zf.writestr("coolmod/sub/thing.py", "x = 1\n")
        zf.writestr("coolmod/__init__.py", "")
    index = CrashAnalyzer().build_module_index(tmp_path)
    assert index["coolmod/sub/thing.py"] == "CoolMod.ts4script"


def test_classify_frame_game_mod_unknown():
    a = CrashAnalyzer()
    index = {"coolmod/sub/thing.py": "CoolMod.ts4script"}
    game = TracebackFrame(raw_path=r"Core\sims4\utils.py")
    mod = TracebackFrame(raw_path=r"F:\proj\coolmod\sub\thing.py")
    unk = TracebackFrame(raw_path=r"C:\whatever\mystery.py")
    a.classify_frame(game, index)
    a.classify_frame(mod, index)
    a.classify_frame(unk, index)
    assert game.kind == "game"
    assert mod.kind == "mod" and mod.mod_name == "CoolMod.ts4script"
    assert unk.kind == "unknown"


def test_analyze_ranks_and_downweights_framework():
    index = {
        "injector/hook.py": "Injector.ts4script",
        "moda/a.py": "ModA.ts4script",
        "modb/b.py": "ModB.ts4script",
    }
    reports = [
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\moda\a.py"),
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\modb\b.py"),
        _report(r"Core\sims4\utils.py", r"x\injector\hook.py", r"y\moda\a.py"),
        _report(r"Core\sims4\utils.py"),  # base-game only
    ]
    result = CrashAnalyzer().analyze(reports, index)

    assert result.ranked_mods[0]["mod"] == "ModA.ts4script"
    assert result.ranked_mods[0]["top_suspect_count"] == 2
    assert "Injector.ts4script" not in [m["mod"] for m in result.ranked_mods]
    assert result.summary["base_game_only"] == 1
    assert result.summary["attributable"] == 3
    assert result.findings[-1].suspects == []
    assert result.findings[0].suspects[0].mod_name == "ModA.ts4script"
    assert result.findings[0].suspects[0].confidence == "high"
