from types import SimpleNamespace

from simanalysis import serialization


def _v(value):
    return SimpleNamespace(value=value)


def test_mod_result_to_dict_shape():
    mod = SimpleNamespace(
        name="A.package", path="/x/A.package", type=_v("package"),
        size=123, author=None, version=None,
    )
    conflict = SimpleNamespace(
        id="c1", severity=_v("high"), type=_v("tuning"),
        description="d", affected_mods=["A.package"], resolution="r",
    )
    perf = SimpleNamespace(
        total_size_mb=1.0, total_resources=2, total_tunings=3, total_scripts=4,
        estimated_load_time_seconds=5.0, estimated_memory_mb=6.0, complexity_score=7,
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
        "name": "A.package", "path": "/x/A.package", "type": "package",
        "size": 123, "author": "Unknown", "version": "Unknown", "conflicts": 1,
    }
    assert out["conflicts"][0]["severity"] == "high"
    assert out["performance"]["complexity_score"] == 7
