"""HTML resource handling."""

from __future__ import annotations

from neuzelaar.core.fetch.resource import Resource
from neuzelaar.document.dom import Text, NodeId, walk
from neuzelaar.engines.html.html5lib_adapter import parse_html


# Safety cap: truncate DOM trees exceeding this many nodes to prevent
# layout and rendering from being overwhelmed by massive HTML.
MAX_DOM_NODES = 20_000


def handle_html(resource: Resource):
    encoding = resource.encoding or "utf-8"
    html = resource.body.decode(encoding, errors="replace")
    document = parse_html(html, url=resource.final_url)

    node_count = sum(1 for _ in walk(document))
    if node_count > MAX_DOM_NODES:
        # Truncate: keep only the first MAX_DOM_NODES children from the
        # root's children list, then append a notice.
        _truncate_tree(document, MAX_DOM_NODES)

    return document


def _truncate_tree(document, limit: int) -> None:
    """Remove nodes beyond the limit and append a truncation notice."""

    def trim(node, remaining: int) -> tuple[int, bool]:
        children = getattr(node, "children", None)
        if not children:
            return remaining, False

        kept = []
        truncated = False
        for child in children:
            if remaining <= 0:
                truncated = True
                break
            kept.append(child)
            remaining -= 1
            remaining, child_truncated = trim(child, remaining)
            if child_truncated:
                truncated = True
                break

        node.children = kept
        if truncated:
            node.children.append(
                Text(
                    id=NodeId("truncated"),
                    data=f"[content truncated: document had more than {limit} nodes]",
                    parent=node,
                )
            )
        return remaining, truncated

    if limit <= 1:
        document.children = [
            Text(
                id=NodeId("truncated"),
                data=f"[content truncated: document had more than {limit} nodes]",
                parent=document,
            )
        ]
        return

    trim(document, limit - 1)
