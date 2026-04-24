"""Tests for safety limits across the Neuzelaar pipeline."""

from neuzelaar.document.bfc import MAX_LAYOUT_ITEMS, layout_block
from neuzelaar.document.box import Box, BoxKind
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child, walk
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import Color, DisplayList, DrawText, FillRect, Rect
from neuzelaar.render.software import MAX_RASTER_HEIGHT, rasterize
from neuzelaar.core.handlers.html_handler import MAX_DOM_NODES, _truncate_tree


def test_rasterizer_clamps_height():
    """A display list taller than MAX_RASTER_HEIGHT should produce a
    frame clamped to the limit."""
    tall_height = MAX_RASTER_HEIGHT + 5000
    ops = (
        FillRect(Rect(0, 0, 100, tall_height), Color(255, 255, 255)),
        DrawText(10, 10, "visible", Color(0, 0, 0), 16),
        # This op is below the cap and should be skipped (no crash).
        DrawText(10, MAX_RASTER_HEIGHT + 100, "invisible", Color(0, 0, 0), 16),
    )
    display_list = DisplayList(width=100, height=tall_height, ops=ops)
    frame = rasterize(display_list)

    assert frame.height == MAX_RASTER_HEIGHT
    assert frame.width == 100
    assert len(frame.pixels) == 100 * MAX_RASTER_HEIGHT * 4


def test_rasterizer_allows_normal_height():
    """A display list within limits should pass through unchanged."""
    ops = (FillRect(Rect(0, 0, 200, 400), Color(255, 255, 255)),)
    display_list = DisplayList(width=200, height=400, ops=ops)
    frame = rasterize(display_list)

    assert frame.height == 400
    assert frame.width == 200


def test_layout_item_budget_stops_emission():
    """Layout should stop emitting items after MAX_LAYOUT_ITEMS."""
    # Build a box tree with way more inline children than the budget.
    root = Box(kind=BoxKind.BLOCK, style=ComputedStyle())
    for i in range(MAX_LAYOUT_ITEMS + 500):
        child = Box(kind=BoxKind.TEXT, style=ComputedStyle(), text=f"line {i}")
        root.children.append(child)

    height, items = layout_block(root, viewport_width=800)

    assert len(items) <= MAX_LAYOUT_ITEMS


def test_dom_node_cap_truncation():
    """DOM trees exceeding MAX_DOM_NODES should be truncated."""
    # Create a document with more nodes than the limit.
    document = Document(id=NodeId("doc"), url="https://test.example/")
    body = Element(id=NodeId("body"), tag="body")
    append_child(document, body)
    # Add many children.
    for i in range(100):
        div = Element(id=NodeId(f"div{i}"), tag="div")
        append_child(body, div)
        for j in range(250):
            text = Text(id=NodeId(f"t{i}_{j}"), data=f"text {i}-{j}")
            append_child(div, text)

    original_count = sum(1 for _ in walk(document))
    assert original_count > 20_000

    _truncate_tree(document, 500)

    truncated_count = sum(1 for _ in walk(document))
    assert truncated_count <= 510  # some margin for the notice node

    # The last text node should be the truncation notice.
    all_nodes = list(walk(document))
    last_texts = [n for n in all_nodes if isinstance(n, Text) and "truncated" in n.data]
    assert len(last_texts) >= 1
