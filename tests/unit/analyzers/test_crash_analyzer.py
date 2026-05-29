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
    assert mod.kind == "mod"
    assert mod.mod_name == "CoolMod.ts4script"
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


def test_norm_preserves_dot_prefixed_dirs():
    from simanalysis.analyzers.crash_analyzer import _norm

    assert _norm(r".\Mods\Thing.ts4script\x.py") == "mods/thing.ts4script/x.py"
    assert _norm(".hidden/mod.py") == ".hidden/mod.py"  # leading-dot dir kept intact


def test_installed_mod_with_game_like_subpath_is_attributed_not_game():
    # A mod whose internal package mirrors the game tree (contains '/server/') must
    # still be attributed to the mod, not silently classified as base-game.
    index = {"wickedwhims/server/main.py": "WickedWhims.ts4script"}
    fr = TracebackFrame(raw_path=r"F:\proj\wickedwhims\server\main.py")
    CrashAnalyzer().classify_frame(fr, index)
    assert fr.kind == "mod"
    assert fr.mod_name == "WickedWhims.ts4script"


def test_classify_frame_explicit_ts4script_path():
    fr = TracebackFrame(raw_path=r".\Mods\Delimaci_TeenParamedicCareer.ts4script\career\x.py")
    CrashAnalyzer().classify_frame(fr, {})
    assert fr.kind == "mod"
    assert fr.mod_name == "delimaci_teenparamediccareer.ts4script"  # derived from normalized path
    assert fr.module_path == "career/x.py"


def test_classify_frame_longest_suffix_wins():
    index = {"thing.py": "Generic.ts4script", "coolmod/sub/thing.py": "CoolMod.ts4script"}
    fr = TracebackFrame(raw_path=r"F:\proj\coolmod\sub\thing.py")
    CrashAnalyzer().classify_frame(fr, index)
    assert fr.mod_name == "CoolMod.ts4script"  # more-specific (longer) key wins


def test_build_module_index_skips_corrupt_archive(tmp_path: Path):
    (tmp_path / "Bad.ts4script").write_text("definitely not a zip", encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "Good.ts4script", "w") as zf:
        zf.writestr("goodmod/x.py", "x = 1\n")
    index = CrashAnalyzer().build_module_index(tmp_path)  # must not raise
    assert index["goodmod/x.py"] == "Good.ts4script"
    assert all("Bad" not in name for name in index.values())


def test_confidence_high_then_medium_for_secondary_mod():
    index = {"moda/a.py": "ModA.ts4script", "modb/b.py": "ModB.ts4script"}
    rep = _report(r"y\modb\b.py", r"y\moda\a.py")  # deepest (last) frame = ModA
    pad = [_report(r"Core\sims4\utils.py"), _report(r"Core\sims4\utils.py")]  # dilute fraction
    result = CrashAnalyzer().analyze([rep, *pad], index)
    sus = result.findings[0].suspects
    assert [s.mod_name for s in sus] == ["ModA.ts4script", "ModB.ts4script"]
    assert sus[0].confidence == "high"
    assert sus[1].confidence == "medium"


def test_curated_framework_only_crash_is_low_confidence():
    # BetterExceptions is curated -> a framework even as a minority (stat rule wouldn't fire),
    # but 'down-weighted != excluded': still the suspect when it's the only mod frame.
    index = {"betterexceptions/be.py": "BetterExceptions.ts4script"}
    fw_only = CrashReport(
        source_file="x",
        report_type="desync",
        message="boom (E)",
        frames=[TracebackFrame(raw_path=r"x\betterexceptions\be.py")],
    )
    pad = [_report(r"Core\sims4\utils.py") for _ in range(3)]
    result = CrashAnalyzer().analyze([fw_only, *pad], index)
    sus = result.findings[0].suspects
    assert sus
    assert sus[0].mod_name == "BetterExceptions.ts4script"
    assert sus[0].confidence == "low"
