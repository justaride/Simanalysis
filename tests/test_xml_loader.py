from __future__ import annotations

import pytest
from lxml import etree

from simanalysis.io.xml_loader import find_attr, find_text, parse_xml


def test_parse_and_query_xml() -> None:
    elem = parse_xml("<root><child attr='foo'>text</child><child>other</child></root>")
    assert find_text(elem, "./child") == ["text", "other"]
    assert find_attr(elem, "./child", "attr") == ["foo"]


def test_external_entities_blocked() -> None:
    xml = """<!DOCTYPE foo [<!ENTITY ext SYSTEM \'file:///etc/passwd\'>]><root>&ext;</root>"""
    with pytest.raises(etree.XMLSyntaxError):
        parse_xml(xml)
