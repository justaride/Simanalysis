from pathlib import Path

from simanalysis.parsers.ui_exception_log import parse_ui_exception_file

UI_XML = (
    '<?xml version="1.0" ?><root>'
    "<report><version>2</version><sessionid>abc123</sessionid><type>desync</type>"
    "<createtime>2026-05-29 12:32:36</createtime>"
    "<buildsignature>Local.Unknown.Unknown.1.124.63.1220-1.300.000.241.Release</buildsignature>"
    "<categoryid>(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory</categoryid>"
    "<desyncid>abc123</desyncid>"
    "<desyncdata>Error: Failed to locate category info for interaction category with key: 15023068382072182982&#13;&#10;"
    "&#9;at gamedata.Gameplay.InteractionMenu::InteractionCategory/Create()&#13;&#10;"
    "&#9;at widgets.Gameplay.PieMenu::PieMenuMain/HandlePieMenuCreate()&#13;&#10;"
    "Modded: True&#13;&#10;"
    "</desyncdata></report>"
    "<report><type>desync</type><categoryid>widgets.NoKey</categoryid>"
    "<desyncdata>Error: UI failed without a resource key&#13;&#10;"
    "&#9;at widgets.GameTray.controls::HUDCheatSheet/InitializeCheatSheetItemList()&#13;&#10;"
    "Modded: False&#13;&#10;"
    "</desyncdata></report>"
    "</root>"
)


def test_parse_ui_exception_file_extracts_key_stack_and_metadata(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_1.txt"
    log.write_text(UI_XML, encoding="utf-8")

    reports = parse_ui_exception_file(log)

    assert len(reports) == 2
    r0 = reports[0]
    assert r0.source_file == str(log)
    assert r0.report_type == "desync"
    assert r0.created == "2026-05-29 12:32:36"
    assert r0.game_version == "Local.Unknown.Unknown.1.124.63.1220-1.300.000.241.Release"
    assert r0.category_id == "(AS)gamedata.Gameplay.InteractionMenu::InteractionCategory"
    assert r0.session_id == "abc123"
    assert r0.desync_id == "abc123"
    assert r0.modded is True
    assert r0.keys == [15023068382072182982]
    assert "Failed to locate category info" in r0.message
    assert len(r0.stack) == 2
    assert r0.stack[0].namespace == "gamedata.Gameplay.InteractionMenu::InteractionCategory"
    assert r0.stack[0].function == "Create"
    assert r0.signature
    assert r0.source_files == [str(log)]


def test_parse_ui_exception_file_allows_no_key_reports(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_1.txt"
    log.write_text(UI_XML, encoding="utf-8")

    reports = parse_ui_exception_file(log)

    r1 = reports[1]
    assert r1.keys == []
    assert r1.category_id == "widgets.NoKey"
    assert r1.modded is False
    assert r1.stack[0].function == "InitializeCheatSheetItemList"


def test_parse_ui_exception_file_malformed_returns_empty(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_bad.txt"
    log.write_text("<root><report><desyncdata>Error", encoding="utf-8")

    assert parse_ui_exception_file(log) == []


def test_parse_ui_exception_file_skips_empty_closed_report(tmp_path: Path) -> None:
    log = tmp_path / "lastUIException_empty.txt"
    log.write_text("<root><report><type>desync</type></report></root>", encoding="utf-8")

    assert parse_ui_exception_file(log) == []
