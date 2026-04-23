"""Minimal block text layout for early visual rendering."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.document.dom import Document, Element, Node, Text


@dataclass(frozen=True, slots=True)
class LayoutText:
    x: int
    y: int
    text: str


@dataclass(frozen=True, slots=True)
class LayoutImage:
    x: int
    y: int
    label: str


LayoutItem = LayoutText | LayoutImage


@dataclass(frozen=True, slots=True)
class LayoutResult:
    width: int
    height: int
    items: tuple[LayoutItem, ...]


def layout_document(document: Document, *, width: int = 800) -> LayoutResult:
    cursor_y = 16
    items: list[LayoutItem] = []
    if document.title:
        items.append(LayoutText(16, cursor_y, document.title))
        cursor_y += 28
    cursor_y = _layout_node(document, items, x=16, y=cursor_y)
    return LayoutResult(width=width, height=max(cursor_y + 16, 64), items=tuple(items))


def _layout_node(node: Node, items: list[LayoutItem], *, x: int, y: int) -> int:
    if isinstance(node, Text):
        text = " ".join(node.data.split())
        if text:
            items.append(LayoutText(x, y, text))
            return y + 22
        return y

    if isinstance(node, Element):
        tag = node.tag.lower()
        if tag in {"script", "style", "head", "title"}:
            return y
        if tag in {"h1", "h2", "h3"}:
            text = _collect_text(node)
            if text:
                items.append(LayoutText(x, y, text))
                return y + 30
            return y
        if tag == "img":
            label = node.attr("alt") or node.attr("src") or "image"
            items.append(LayoutImage(x, y, label))
            return y + 44
        if tag == "li":
            text = _collect_text(node)
            if text:
                items.append(LayoutText(x, y, f"- {text}"))
                return y + 22
            return y

    children = getattr(node, "children", None)
    if not children:
        return y
    for child in children:
        y = _layout_node(child, items, x=x, y=y)
    if isinstance(node, Element) and node.tag.lower() in {"p", "div", "section", "ul", "ol"}:
        y += 8
    return y


def _collect_text(node: Node) -> str:
    if isinstance(node, Text):
        return " ".join(node.data.split())
    children = getattr(node, "children", None)
    if not children:
        return ""
    return " ".join(part for child in children if (part := _collect_text(child)))
