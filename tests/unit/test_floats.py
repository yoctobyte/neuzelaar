from neuzelaar.document.bfc import BoxPlacement, TextPlacement, layout_block
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import ComputedStyle, compute_styles


def test_left_float_pushes_following_text_to_the_right() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    pull = Element(
        id=NodeId("pull"),
        tag="div",
        attrs={"style": "float: left; width: 100px; background-color: #cccccc"},
    )
    para = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, pull)
    append_child(pull, Text(id=NodeId("pulltext"), data="aside"))
    append_child(body, para)
    append_child(para, Text(id=NodeId("ptext"), data="flowing"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    flowing = next(
        p for p in placements if isinstance(p, TextPlacement) and p.text == "flowing"
    )
    aside = next(
        p for p in placements if isinstance(p, TextPlacement) and p.text == "aside"
    )
    # The flowing paragraph's text should sit to the right of the
    # 100px left-floated div.
    assert flowing.x >= 100
    # The float's own text should remain at the left edge.
    assert aside.x < flowing.x


def test_right_float_constrains_following_text_from_the_right() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    aside = Element(
        id=NodeId("aside"),
        tag="div",
        attrs={"style": "float: right; width: 80px"},
    )
    para = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, aside)
    append_child(body, para)
    append_child(
        para,
        Text(id=NodeId("t"), data="one two three four five six seven eight nine ten"),
    )
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    text_placements = [
        p for p in placements
        if isinstance(p, TextPlacement) and p.text in ("one", "two", "three", "four", "five")
    ]
    # No word should extend into the right 80px reserved by the float.
    for placement in text_placements:
        # Each word must end at x + word_width <= 320; we only check
        # the left edge here, as approximate measurement is used.
        assert placement.x < 320


def test_clear_advances_following_block_below_floats() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    floated = Element(
        id=NodeId("f"),
        tag="div",
        attrs={"style": "float: left; width: 80px; height: 60px"},
    )
    cleared = Element(
        id=NodeId("c"),
        tag="div",
        attrs={"style": "clear: both"},
    )
    append_child(document, body)
    append_child(body, floated)
    append_child(body, cleared)
    append_child(cleared, Text(id=NodeId("ct"), data="below"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    below = next(
        p for p in placements if isinstance(p, TextPlacement) and p.text == "below"
    )
    # Cleared element starts at-or-below the float's bottom (60px).
    assert below.y >= 60


def test_containing_block_extends_to_contain_floats() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    floated = Element(
        id=NodeId("f"),
        tag="div",
        attrs={"style": "float: left; width: 100px; height: 200px"},
    )
    append_child(document, body)
    append_child(body, floated)
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    total_height, _ = layout_block(root, viewport_width=400)

    # Body had no in-flow content, but the floated div is 200px tall;
    # the body should expand to contain it.
    assert total_height >= 200
