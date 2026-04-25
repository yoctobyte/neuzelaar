from neuzelaar.document.bfc import BoxPlacement, TextPlacement, layout_block
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import compute_styles


def test_position_relative_shifts_box_and_descendants_visually() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    static_p = Element(id=NodeId("a"), tag="p")
    rel_p = Element(
        id=NodeId("b"),
        tag="p",
        attrs={"style": "position: relative; top: 25px; left: 40px"},
    )
    after_p = Element(id=NodeId("c"), tag="p")
    append_child(document, body)
    append_child(body, static_p)
    append_child(static_p, Text(id=NodeId("ta"), data="static"))
    append_child(body, rel_p)
    append_child(rel_p, Text(id=NodeId("tb"), data="moved"))
    append_child(body, after_p)
    append_child(after_p, Text(id=NodeId("tc"), data="after"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    static = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "static")
    moved = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "moved")
    after = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "after")

    # The relative paragraph's text shifts by 40px right and 25px down
    # relative to where it would have been in normal flow.
    expected_normal_y = static.y + (after.y - static.y - 25)  # ~ middle of static and after
    assert moved.x >= 40
    assert moved.y > static.y + 24
    # `after` is unaffected by the relative box: it sits in the
    # original normal-flow position right below `moved`'s reserved
    # space (which is ~ one line height below static).
    assert after.y > static.y
    assert after.y < moved.y  # after is at moved's static-position, which is < moved's shifted y


def test_position_absolute_uses_relative_ancestor_as_containing_block() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    rel_parent = Element(
        id=NodeId("rel"),
        tag="div",
        attrs={"style": "position: relative; margin: 50px"},
    )
    abs_child = Element(
        id=NodeId("abs"),
        tag="div",
        attrs={"style": "position: absolute; top: 10px; left: 20px; width: 50px"},
    )
    append_child(document, body)
    append_child(body, rel_parent)
    append_child(rel_parent, Text(id=NodeId("rt"), data="parent"))
    append_child(rel_parent, abs_child)
    append_child(abs_child, Text(id=NodeId("at"), data="abs"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    abs_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "abs")
    parent_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "parent")

    # The absolute child is positioned relative to its containing
    # block (the relative parent's content edge), not the viewport.
    # parent's content x ~= 50 (margin), so abs.x ~= 50 + 20 = 70.
    assert abs_text.x == parent_text.x + 20
    assert abs_text.y == parent_text.y + 10


def test_position_absolute_falls_through_to_viewport_when_no_relative_ancestor() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    abs_child = Element(
        id=NodeId("abs"),
        tag="div",
        attrs={"style": "position: absolute; top: 100px; left: 50px"},
    )
    append_child(document, body)
    append_child(body, abs_child)
    append_child(abs_child, Text(id=NodeId("at"), data="floating"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    abs_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "floating")
    # No positioned ancestor, so CB is the viewport at (0, 0).
    assert abs_text.x == 50
    assert abs_text.y == 100


def test_position_absolute_does_not_consume_normal_flow_space() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    abs_child = Element(
        id=NodeId("abs"),
        tag="div",
        attrs={"style": "position: absolute; top: 200px; left: 0; height: 200px; width: 100px"},
    )
    flow_p = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, abs_child)
    append_child(abs_child, Text(id=NodeId("at"), data="abs"))
    append_child(body, flow_p)
    append_child(flow_p, Text(id=NodeId("ft"), data="flow"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    flow_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "flow")
    # The absolute element is taken out of flow, so the in-flow
    # paragraph stays at the top.
    assert flow_text.y < 100


def test_position_fixed_uses_viewport_even_inside_relative_ancestor() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    rel_parent = Element(
        id=NodeId("rel"),
        tag="div",
        attrs={"style": "position: relative; margin: 50px"},
    )
    fixed_child = Element(
        id=NodeId("fix"),
        tag="div",
        attrs={"style": "position: fixed; top: 5px; left: 5px"},
    )
    append_child(document, body)
    append_child(body, rel_parent)
    append_child(rel_parent, fixed_child)
    append_child(fixed_child, Text(id=NodeId("ft"), data="fixed"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    fixed_text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "fixed")
    # Fixed ignores the relative ancestor and uses the viewport.
    assert fixed_text.x == 5
    assert fixed_text.y == 5
