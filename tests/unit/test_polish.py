"""Tests for polish-pass features: z-index ordering, right/bottom for
absolute positioning."""

from neuzelaar.document.bfc import TextPlacement, layout_block
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import compute_styles


def test_higher_z_index_paints_after_lower() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    rel = Element(id=NodeId("r"), tag="div", attrs={"style": "position: relative; height: 200px"})
    bottom = Element(
        id=NodeId("b"),
        tag="div",
        attrs={"style": "position: absolute; top: 0; left: 0; z-index: 1"},
    )
    top = Element(
        id=NodeId("t"),
        tag="div",
        attrs={"style": "position: absolute; top: 0; left: 0; z-index: 5"},
    )
    append_child(document, body)
    append_child(body, rel)
    # Document-order is bottom then top, but z-index says top should
    # paint last regardless.
    append_child(rel, bottom)
    append_child(bottom, Text(id=NodeId("bt"), data="behind"))
    append_child(rel, top)
    append_child(top, Text(id=NodeId("tt"), data="front"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    text_placements = [p for p in placements if isinstance(p, TextPlacement)]
    behind_idx = next(i for i, p in enumerate(text_placements) if p.text == "behind")
    front_idx = next(i for i, p in enumerate(text_placements) if p.text == "front")
    assert behind_idx < front_idx


def test_zindex_inverts_document_order_when_lower_z_comes_later() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    rel = Element(id=NodeId("r"), tag="div", attrs={"style": "position: relative; height: 200px"})
    early_high = Element(
        id=NodeId("e"),
        tag="div",
        attrs={"style": "position: absolute; top: 0; left: 0; z-index: 10"},
    )
    late_low = Element(
        id=NodeId("l"),
        tag="div",
        attrs={"style": "position: absolute; top: 0; left: 0; z-index: 2"},
    )
    append_child(document, body)
    append_child(body, rel)
    append_child(rel, early_high)
    append_child(early_high, Text(id=NodeId("eh"), data="early-high"))
    append_child(rel, late_low)
    append_child(late_low, Text(id=NodeId("ll"), data="late-low"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    text_placements = [p for p in placements if isinstance(p, TextPlacement)]
    eh_idx = next(i for i, p in enumerate(text_placements) if p.text == "early-high")
    ll_idx = next(i for i, p in enumerate(text_placements) if p.text == "late-low")
    # Lower z-index paints first even though it's later in document order.
    assert ll_idx < eh_idx


def test_absolute_right_offset_pins_box_to_right_edge_of_cb() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    rel = Element(id=NodeId("r"), tag="div", attrs={"style": "position: relative; width: 300px; height: 100px"})
    pinned = Element(
        id=NodeId("p"),
        tag="div",
        attrs={"style": "position: absolute; right: 20px; top: 10px; width: 50px"},
    )
    append_child(document, body)
    append_child(body, rel)
    append_child(rel, pinned)
    append_child(pinned, Text(id=NodeId("pt"), data="pinned"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=600)

    pinned_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "pinned")
    # CB width 300, box width 50, right 20 -> x = 0 (CB left) + 300 - 20 - 50 = 230.
    assert pinned_text.x == 230
