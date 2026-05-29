from types import SimpleNamespace

from simanalysis import serialization


def _v(value):
    return SimpleNamespace(value=value)


def test_mod_result_to_dict_shape():
    mod = SimpleNamespace(
        name="A.package",
        path="/x/A.package",
        type=_v("package"),
        size=123,
        author=None,
        version=None,
    )
    conflict = SimpleNamespace(
        id="c1",
        severity=_v("high"),
        type=_v("tuning"),
        description="d",
        affected_mods=["A.package"],
        resolution="r",
    )
    perf = SimpleNamespace(
        total_size_mb=1.0,
        total_resources=2,
        total_tunings=3,
        total_scripts=4,
        estimated_load_time_seconds=5.0,
        estimated_memory_mb=6.0,
        complexity_score=7,
    )
    result = SimpleNamespace(mods=[mod], conflicts=[conflict], performance=perf)
    analyzer = SimpleNamespace(
        get_summary=lambda r: {"ok": True},
        get_recommendations=lambda r: ["rec"],
    )

    out = serialization.mod_result_to_dict(analyzer, result)

    assert out["summary"] == {"ok": True}
    assert out["recommendations"] == ["rec"]
    assert out["mods"][0] == {
        "name": "A.package",
        "path": "/x/A.package",
        "type": "package",
        "size": 123,
        "author": "Unknown",
        "version": "Unknown",
        "conflicts": 1,
    }
    assert out["conflicts"][0]["severity"] == "high"
    assert out["performance"]["complexity_score"] == 7


def test_tray_result_to_dict_shape():
    item = SimpleNamespace(to_dict=lambda: {"name": "Family.trayitem", "kind": "household"})
    result = SimpleNamespace(items=[item])
    analyzer = SimpleNamespace(get_summary=lambda r: {"count": 1})
    out = serialization.tray_result_to_dict(analyzer, result)
    assert out == {
        "summary": {"count": 1},
        "items": [{"name": "Family.trayitem", "kind": "household"}],
    }


def test_save_result_to_dict_shape_and_unused_cap():
    used = SimpleNamespace(
        name="U.package", path="/m/U.package", size=10, resource_count=3, matching_resources=[1, 2]
    )
    unused = [
        SimpleNamespace(name=f"X{i}.package", path=f"/m/X{i}.package", size=i, resource_count=i)
        for i in range(150)
    ]
    save_data = SimpleNamespace(to_dict=lambda: {"slot": "Save_1"})
    result = SimpleNamespace(save_data=save_data, used_mods=[used], unused_mods=unused)
    analyzer = SimpleNamespace(get_summary=lambda r: {"ok": True})

    out = serialization.save_result_to_dict(analyzer, result)

    assert out["summary"] == {"ok": True}
    assert out["save_info"] == {"slot": "Save_1"}
    assert out["used_mods"][0] == {
        "name": "U.package",
        "path": "/m/U.package",
        "size": 10,
        "resource_count": 3,
        "matching_resources": 2,
    }
    assert len(out["unused_mods"]) == 100  # capped at 100
    assert out["unused_mods"][0] == {
        "name": "X0.package",
        "path": "/m/X0.package",
        "size": 0,
        "resource_count": 0,
    }


def test_crash_result_to_dict_shape():
    from simanalysis import serialization
    from simanalysis.models import (
        CrashAnalysisResult,
        CrashFinding,
        CrashReport,
        Suspect,
        TracebackFrame,
    )

    frame = TracebackFrame(
        raw_path="x/moda/a.py", line=7, func="run", kind="mod", mod_name="ModA.ts4script"
    )
    report = CrashReport(
        source_file="l.txt",
        report_type="desync",
        message="boom (ValueError)",
        frames=[frame],
        exception_class="ValueError",
    )
    finding = CrashFinding(
        report=report,
        suspects=[
            Suspect(mod_name="ModA.ts4script", confidence="high", reason="r", evidence=[frame])
        ],
    )
    result = CrashAnalysisResult(
        summary={"reports": 1},
        ranked_mods=[{"mod": "ModA.ts4script", "top_suspect_count": 1, "crash_count": 1}],
        findings=[finding],
    )
    out = serialization.crash_result_to_dict(result)
    assert out["summary"] == {"reports": 1}
    assert out["ranked_mods"][0]["mod"] == "ModA.ts4script"
    f0 = out["findings"][0]
    assert f0["exception_class"] == "ValueError"
    assert f0["suspects"][0] == {
        "mod": "ModA.ts4script",
        "confidence": "high",
        "status": "active",
        "reason": "r",
        "evidence": ["x/moda/a.py"],
    }
