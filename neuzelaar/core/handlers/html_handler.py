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
    """Remove nodes beyond the limit and append a truncation notice.

    Walks depth-first with an explicit stack. As soon as the node count
    reaches the limit, the children list of the current parent is
    truncated and a notice is appended.
    """
    count = [0]
    found = [False]

    def _walk_and_prune(node) -> None:
        if found[0]:
            return
        count[0] += 1
        if count[0] >= limit:
            found[0] = True
            return
        children = getattr(node, "children", None)
        if not children:
            return
        i = 0
        while i < len(children) and not found[0]:
            _walk_and_prune(children[i])
            if found[0]:
                # Truncate: keep children[0..i] (the child that triggered
                # the limit is kept but its own children were pruned by
                # the recursive call), drop the rest.
                del children[i + 1 :]
                children.append(
                    Text(
                        id=NodeId("truncated"),
                        data=f"[content truncated: document had more than {limit} nodes]",
                    )
                )
                return
            i += 1

    _walk_and_prune(document)
