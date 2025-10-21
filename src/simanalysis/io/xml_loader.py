"""XML parsing helpers with hardened defaults."""

from __future__ import annotations

from typing import Any, Iterable

from lxml import etree

_SECURE_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    load_dtd=False,
)


def parse_xml(xml_str: str) -> etree._Element:
    """Parse XML string into an element tree using secure defaults."""

    return etree.fromstring(xml_str.encode("utf-8"), parser=_SECURE_PARSER)


def _ensure_list(value: Any) -> Iterable[Any]:
    if isinstance(value, list):
        return value
    return [value]


def find_text(elem: etree._Element, xpath: str, ns: dict[str, str] | None = None) -> list[str]:
    """Return text contents for nodes matching ``xpath``."""

    results = elem.xpath(xpath, namespaces=ns)
    texts: list[str] = []
    for item in _ensure_list(results):
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, etree._Element):
            if item.text is not None:
                texts.append(item.text)
    return texts


def find_attr(
    elem: etree._Element, xpath: str, attr: str, ns: dict[str, str] | None = None
) -> list[str]:
    """Return attribute values for nodes matching ``xpath``."""

    nodes = elem.xpath(xpath, namespaces=ns)
    values: list[str] = []
    for node in _ensure_list(nodes):
        if isinstance(node, etree._Element):
            value = node.get(attr)
            if value is not None:
                values.append(value)
    return values
