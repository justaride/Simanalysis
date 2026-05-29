import struct
from pathlib import Path

from simanalysis.analyzers.ui_crash_analyzer import UICrashAnalyzer, discover_disabled_roots
from simanalysis.models import UIExceptionReport

TARGET_KEY = 15023068382072182982


def _write_dbpf_package(path: Path, key: int, resource_type: int = 0x03E9D964) -> None:
    payload = b"resource"
    index = bytearray()
    index += struct.pack("<I", 0)  # mnIndexType: no constants
    index += struct.pack("<I", resource_type)
    index += struct.pack("<I", 0)
    index += struct.pack("<I", key >> 32)
    index += struct.pack("<I", key & 0xFFFFFFFF)
    index += struct.pack("<I", 96 + 4 + 32)
    index += struct.pack("<I", len(payload))
    index += struct.pack("<I", len(payload))
    index += struct.pack("<H", 0)
    index += struct.pack("<H", 1)

    header = bytearray(96)
    header[0:4] = b"DBPF"
    header[4:8] = struct.pack("<I", 2)
    header[8:12] = struct.pack("<I", 1)
    header[36:40] = struct.pack("<I", 1)
    header[44:48] = struct.pack("<I", len(index))
    header[64:68] = struct.pack("<I", 96)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(header)
        f.write(index)
        f.write(payload)


def _report(key: int | None = TARGET_KEY, signature: str = "sig") -> UIExceptionReport:
    message = "Error: Failed to locate category info"
    if key is not None:
        message += f" for interaction category with key: {key}"
    return UIExceptionReport(
        source_file="lastUIException.txt",
        report_type="desync",
        message=message,
        category_id="(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory",
        keys=[] if key is None else [key],
        signature=signature,
        source_files=["lastUIException.txt"],
    )


def test_build_resource_index_records_active_hit(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    pkg = mods / "Active.package"
    _write_dbpf_package(pkg, TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)

    hit = index[TARGET_KEY][0]
    assert hit.package_name == "Active.package"
    assert hit.status == "active"
    assert hit.resource_type == 0x03E9D964
    assert analyzer.index_errors == []


def test_disabled_only_hit_classifies_disabled(tmp_path: Path) -> None:
    (tmp_path / "Mods").mkdir()
    disabled = tmp_path / "_Quarantine_UI"
    _write_dbpf_package(disabled / "adeepindigo_base_generalpiemenus_v3-2.package", TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(tmp_path / "Mods", extra_roots=[disabled])
    result = analyzer.analyze([_report()], index)

    finding = result.findings[0]
    assert finding.status == "disabled"
    assert finding.hits[0].package_name == "adeepindigo_base_generalpiemenus_v3-2.package"
    assert result.summary["disabled_findings"] == 1


def test_discover_disabled_roots_scans_only_under_base(tmp_path: Path) -> None:
    sims_base = tmp_path / "The Sims 4"
    in_scope = sims_base / "_Quarantine_UI"
    out_of_scope = tmp_path / "_Disabled_Sibling"
    in_scope.mkdir(parents=True)
    out_of_scope.mkdir()

    roots = discover_disabled_roots(sims_base)

    assert roots == [in_scope]


def test_active_beats_disabled_for_same_key(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    disabled = tmp_path / "_Disabled_Old"
    _write_dbpf_package(mods / "Active.package", TARGET_KEY)
    _write_dbpf_package(disabled / "Old.package", TARGET_KEY)

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods, extra_roots=[disabled])
    result = analyzer.analyze([_report()], index)

    assert result.findings[0].status == "active"
    assert result.summary["active_findings"] == 1


def test_not_found_and_no_key_statuses(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)
    result = analyzer.analyze([_report(1234567890123, "missing"), _report(None, "nokey")], index)

    assert [f.status for f in result.findings] == ["not_found", "no_key"]
    assert result.summary["not_found_findings"] == 1
    assert result.summary["no_key_findings"] == 1


def test_duplicate_reports_are_collapsed(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    _write_dbpf_package(mods / "Active.package", TARGET_KEY)
    reports = [_report(signature="same"), _report(signature="same"), _report(signature="same")]

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)
    result = analyzer.analyze(reports, index)

    assert len(result.findings) == 1
    assert result.findings[0].report.occurrences == 3
    assert result.summary["occurrences"] == 3


def test_duplicate_reports_keep_unique_source_files(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    _write_dbpf_package(mods / "Active.package", TARGET_KEY)
    first = _report(signature="same")
    second = _report(signature="same")
    first.source_files = ["lastUIException.txt", "olderUIException.txt"]
    second.source_files = ["lastUIException.txt", "olderUIException.txt"]

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)
    result = analyzer.analyze([first, second], index)

    assert result.findings[0].report.occurrences == 2
    assert result.findings[0].report.source_files == [
        "lastUIException.txt",
        "olderUIException.txt",
    ]


def test_corrupt_package_is_recorded_not_raised(tmp_path: Path) -> None:
    mods = tmp_path / "Mods"
    mods.mkdir()
    (mods / "Bad.package").write_text("not dbpf", encoding="utf-8")

    analyzer = UICrashAnalyzer()
    index = analyzer.build_resource_index(mods)

    assert index == {}
    assert len(analyzer.index_errors) == 1
    assert "Bad.package" in analyzer.index_errors[0]
