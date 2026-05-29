from pathlib import Path

from simanalysis.parsers.exception_log import parse_exception_file

BE_XML = (
    '<?xml version="1.0" ?><root>\n'
    "<BetterExceptions><Advice>This is likely due to bad tuning.</Advice></BetterExceptions>"
    "<report><version>2</version><type>desync</type>"
    "<createtime>2026-05-25 21:17:18</createtime>"
    "<buildsignature>Local.1.124.55.1230</buildsignature>"
    "<categoryid>injector.py:26</categoryid>"
    "<desyncdata>[cjiang] Error occurred within the tag (UnavailablePackSafeResourceError)&#13;&#10;"
    "Traceback (most recent call last):&#13;&#10;"
    '  File "Core\\sims4\\utils.py", line 179, in wrapper&#13;&#10;'
    '  File "E:\\x\\NisaK\\utilities\\nisa_injector.py", line 25, in _inject&#13;&#10;'
    '  File "F:\\y\\modcool\\thing.py", line 7, in run&#13;&#10;'
    "</desyncdata></report>"
    "<report><type>desync</type>"
    "<desyncdata>[cjiang] Error occurred within the tag (UnavailablePackSafeResourceError)&#13;&#10;"
    "Traceback (most recent call last):&#13;&#10;"
    '  File "Core\\sims4\\utils.py", line 179, in wrapper&#13;&#10;'
    '  File "E:\\x\\NisaK\\utilities\\nisa_injector.py", line 25, in _inject&#13;&#10;'
    '  File "F:\\y\\modcool\\thing.py", line 7, in run&#13;&#10;'
    "</desyncdata></report>"
    "<report><type>desync</type><desyncdata>Error: no category&#13;&#10;</desyncdata></report>"
    "</root>"
)


def test_parses_be_xml_dedupes_and_skips_non_traceback(tmp_path: Path):
    f = tmp_path / "lastException_1.txt"
    f.write_text(BE_XML, encoding="utf-8")

    reports = parse_exception_file(f)

    assert len(reports) == 1  # duplicate deduped, no-traceback skipped
    r = reports[0]
    assert r.report_type == "desync"
    assert r.exception_class == "UnavailablePackSafeResourceError"
    assert r.creator_tag == "cjiang"
    assert r.created == "2026-05-25 21:17:18"
    assert r.game_version == "Local.1.124.55.1230"
    assert r.be_advice == "This is likely due to bad tuning."
    assert [fr.line for fr in r.frames] == [179, 25, 7]
    assert r.frames[1].func == "_inject"
    assert "nisa_injector.py" in r.frames[1].raw_path
    assert r.signature  # set


def test_malformed_file_does_not_raise(tmp_path: Path):
    f = tmp_path / "lastException_bad.txt"
    f.write_text("<root><report><desyncdata>Traceback (most recent", encoding="utf-8")
    assert parse_exception_file(f) == []  # truncated/unterminated -> nothing, no exception
