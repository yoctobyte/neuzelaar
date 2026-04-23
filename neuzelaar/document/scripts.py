"""Active script discovery from the internal document tree."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.document.dom import Document, Element, NodeId, Text, walk


@dataclass(frozen=True, slots=True)
class ScriptRequest:
    node_id: NodeId
    source: str
    url: str | None
    inline: bool


def extract_scripts(document: Document) -> tuple[ScriptRequest, ...]:
    requests: list[ScriptRequest] = []
    for node in walk(document):
        if not isinstance(node, Element) or node.tag.lower() != "script":
            continue
        source_url = node.attr("src")
        if source_url:
            requests.append(ScriptRequest(node_id=node.id, source="", url=source_url, inline=False))
            continue
        source = "".join(_text_children(node)).strip()
        if source:
            requests.append(ScriptRequest(node_id=node.id, source=source, url=None, inline=True))
    return tuple(requests)


def _text_children(node: Element) -> list[str]:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, Text):
            parts.append(child.data)
    return parts
