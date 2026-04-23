"""Semantic text renderer for headless and console output."""

from __future__ import annotations

from neuzelaar.document.dom import Document, Element, Node, Text


BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "body",
    "div",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}


def render_text(document: Document) -> str:
    lines: list[str] = []
    if document.title:
        lines.append(f"# {document.title}")
        lines.append("")
    _render_node(document, lines, indent=0)
    return "\n".join(line.rstrip() for line in lines if line.strip()).strip()


def _render_node(node: Node, lines: list[str], indent: int) -> None:
    if isinstance(node, Text):
        text = " ".join(node.data.split())
        if text:
            lines.append(f"{'  ' * indent}{text}")
        return
    if isinstance(node, Element):
        if node.tag in {"script", "style", "head", "title"}:
            return
        if node.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = _collect_text(node)
            if text:
                level = int(node.tag[1])
                lines.append(f"{'#' * level} {text}")
            return
        if node.tag == "a":
            text = _collect_text(node) or node.attr("href") or ""
            href = node.attr("href")
            if href:
                lines.append(f"{'  ' * indent}{text} <{href}>")
            elif text:
                lines.append(f"{'  ' * indent}{text}")
            return
        if node.tag == "img":
            alt = node.attr("alt") or node.attr("src") or "image"
            lines.append(f"{'  ' * indent}[image: {alt}]")
            return

    children = getattr(node, "children", None)
    if not children:
        return
    child_indent = indent + 1 if isinstance(node, Element) and node.tag in {"ul", "ol"} else indent
    for child in children:
        if isinstance(node, Element) and node.tag == "li":
            text = _collect_text(node)
            if text:
                lines.append(f"{'  ' * indent}- {text}")
                return
        _render_node(child, lines, child_indent)
    if isinstance(node, Element) and node.tag in BLOCK_TAGS:
        lines.append("")


def _collect_text(node: Node) -> str:
    if isinstance(node, Text):
        return " ".join(node.data.split())
    children = getattr(node, "children", None)
    if not children:
        return ""
    return " ".join(part for child in children if (part := _collect_text(child)))
