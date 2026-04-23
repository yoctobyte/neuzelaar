"""Adapter from html5lib's etree output to Neuzelaar's internal document tree."""

from __future__ import annotations

from itertools import count
from xml.etree import ElementTree

import html5lib

from neuzelaar.document.dom import Document, Element, Node, NodeId, Text, append_child, walk


def parse_html(html: str, *, url: str) -> Document:
    parser = html5lib.HTMLParser(
        tree=html5lib.getTreeBuilder("etree"),
        namespaceHTMLElements=False,
    )
    root = parser.parse(html)
    ids = count()
    document = Document(id=_node_id(ids), url=url)
    _convert_element(root, document, ids)
    document.title = _extract_title(document)
    return document


def _convert_element(source: ElementTree.Element, parent: Document | Element, ids) -> Element:
    element = Element(
        id=_node_id(ids),
        tag=_strip_namespace(source.tag).lower(),
        attrs={_strip_namespace(key).lower(): value for key, value in source.attrib.items()},
    )
    append_child(parent, element)
    if source.text:
        append_child(element, Text(id=_node_id(ids), data=source.text))
    for child in list(source):
        _convert_element(child, element, ids)
        if child.tail:
            append_child(element, Text(id=_node_id(ids), data=child.tail))
    return element


def _extract_title(document: Document) -> str:
    for node in walk(document):
        if isinstance(node, Element) and node.tag == "title":
            return "".join(_text_content(node)).strip()
    return ""


def _text_content(node: Node) -> list[str]:
    if isinstance(node, Text):
        return [node.data]
    children = getattr(node, "children", None)
    if not children:
        return []
    result: list[str] = []
    for child in children:
        result.extend(_text_content(child))
    return result


def _strip_namespace(value: str) -> str:
    return value.rsplit("}", 1)[-1] if "}" in value else value


def _node_id(ids) -> NodeId:
    return NodeId(f"n{next(ids)}")
