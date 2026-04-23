"""Link extraction from the internal document tree."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.origin import resolve_url
from neuzelaar.document.dom import Document, Element, Node, NodeId, Text, walk


@dataclass(frozen=True, slots=True)
class DocumentLink:
    index: int
    node_id: NodeId
    text: str
    href: str
    resolved_url: str


def extract_links(document: Document) -> tuple[DocumentLink, ...]:
    links: list[DocumentLink] = []
    for node in walk(document):
        if not isinstance(node, Element) or node.tag.lower() != "a":
            continue
        href = node.attr("href")
        if not href:
            continue
        links.append(
            DocumentLink(
                index=len(links) + 1,
                node_id=node.id,
                text=_text_content(node) or href,
                href=href,
                resolved_url=resolve_url(document.url, href).normalized,
            )
        )
    return tuple(links)


def _text_content(node: Node) -> str:
    if isinstance(node, Text):
        return " ".join(node.data.split())
    children = getattr(node, "children", None)
    if not children:
        return ""
    return " ".join(part for child in children if (part := _text_content(child))).strip()
