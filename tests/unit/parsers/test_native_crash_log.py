from pathlib import Path

import pytest

from simanalysis.parsers.native_crash_log import parse_native_crash_file


NATIVE_CRASH_XML = (
    '<?xml version="1.0" ?><root>'
    "<report>"
    "<type>crash</type>"
    "<createtime>2026-06-16 22:19:10</createtime>"
    "<categoryid>gameplay.vehicle.NativeCrash</categoryid>"
    "<buildsignature>Local.1.124.55.1230</buildsignature>"
    "<currentgamestate>Live_Mode</currentgamestate>"
    "<desyncdata>"
    "Modded: True&#13;&#10;"
    "Exception raised while updating autonomy&#13;&#10;"
    "  0x00007ff6 Sims4_x64.exe!UnknownFunction&#13;&#10;"
    "  0x00007ff6 Simulation.dll!Tick"
    "</desyncdata>"
    "</report>"
    "</root>"
)


def test_parse_native_crash_extracts_unattributed_fields(tmp_path: Path) -> None:
    crash = tmp_path / "lastCrash.txt"
    crash.write_text(NATIVE_CRASH_XML, encoding="utf-8")

    reports = parse_native_crash_file(crash)

    assert len(reports) == 1
    report = reports[0]
    assert report.source_file == str(crash)
    assert report.created == "2026-06-16 22:19:10"
    assert report.category_id == "gameplay.vehicle.NativeCrash"
    assert report.build_signature == "Local.1.124.55.1230"
    assert report.modded is True
    assert report.current_game_state == "Live_Mode"
    assert report.stack_snippet == [
        "Exception raised while updating autonomy",
        "0x00007ff6 Sims4_x64.exe!UnknownFunction",
        "0x00007ff6 Simulation.dll!Tick",
    ]


def test_parse_native_crash_rejects_unterminated_report(tmp_path: Path) -> None:
    crash = tmp_path / "lastCrash_bad.txt"
    crash.write_text("<root><report><desyncdata>Native crash", encoding="utf-8")

    with pytest.raises(ValueError, match="unterminated <report>"):
        parse_native_crash_file(crash)
