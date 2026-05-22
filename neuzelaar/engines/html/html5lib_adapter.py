"""Adapter from html5lib's etree output to Neuzelaar's internal document tree."""

from __future__ import annotations

from itertools import count
from typing import Callable
from xml.etree import ElementTree

import html5lib

from neuzelaar.document.dom import Comment, Document, Element, Node, NodeId, Text, append_child, walk


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


def parse_html_fragment(
    html: str,
    *,
    parent: Element | Document,
    mint_id: Callable[[], NodeId],
) -> list[Node]:
    """Parse ``html`` as an HTML fragment and return Nodes parented to ``parent``.

    ``mint_id`` is the host's id allocator — letting the caller decide
    the prefix means mutation-time fragments don't have to share a
    namespace with parse-time ids. Nodes' ``parent`` field is set but
    they are NOT appended to ``parent.children`` — the caller decides
    where they go (innerHTML replaces children, appendChild appends one).
    """
    parser = html5lib.HTMLParser(
        tree=html5lib.getTreeBuilder("etree"),
        namespaceHTMLElements=False,
    )
    parsed_root = parser.parseFragment(html)

    def convert(source: ElementTree.Element, parent_node: Element | Document) -> Node:
        tag = source.tag
        if tag is ElementTree.Comment or (callable(tag) and getattr(tag, "__name__", None) == "Comment"):
            new_comment = Comment(id=mint_id(), data=source.text or "")
            new_comment.parent = parent_node
            return new_comment

        tag_str = _strip_namespace(tag)
        if not isinstance(tag_str, str):
            tag_str = "unknown"
        attrs = {
            (_strip_namespace(k) if isinstance(k, str) else k).lower(): v
            for k, v in source.attrib.items()
        }
        new_element = Element(id=mint_id(), tag=tag_str.lower(), attrs=attrs)
        new_element.parent = parent_node
        if source.text:
            new_element.children.append(
                Text(id=mint_id(), parent=new_element, data=source.text)
            )
        for child in list(source):
            child_node = convert(child, new_element)
            new_element.children.append(child_node)
            if child.tail:
                new_element.children.append(
                    Text(id=mint_id(), parent=new_element, data=child.tail)
                )
        return new_element

    nodes: list[Node] = []
    if parsed_root.text:
        nodes.append(Text(id=mint_id(), parent=parent, data=parsed_root.text))
    for child in list(parsed_root):
        nodes.append(convert(child, parent))
        if child.tail:
            nodes.append(Text(id=mint_id(), parent=parent, data=child.tail))
    return nodes


def _convert_element(source: ElementTree.Element, parent: Document | Element, ids) -> Node:
    tag = source.tag
    if tag is ElementTree.Comment or (callable(tag) and getattr(tag, "__name__", None) == "Comment"):
        comment = Comment(id=_node_id(ids), data=source.text or "")
        append_child(parent, comment)
        return comment

    tag_str = _strip_namespace(tag)
    if not isinstance(tag_str, str):
        tag_str = "unknown"
    element = Element(
        id=_node_id(ids),
        tag=tag_str.lower(),
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


def _strip_namespace(value) -> str | object:
    if not isinstance(value, str):
        return value
    return value.rsplit("}", 1)[-1] if "}" in value else value


def _node_id(ids) -> NodeId:
    return NodeId(f"n{next(ids)}")
