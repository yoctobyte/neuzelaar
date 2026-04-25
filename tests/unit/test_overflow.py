from neuzelaar.document.bfc import (
    ClipPopPlacement,
    ClipPushPlacement,
    layout_block,
)
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import compute_styles


def test_overflow_visible_emits_no_clip_placements() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    div = Element(id=NodeId("d"), tag="div", attrs={"style": "height: 50px"})
    append_child(document, body)
    append_child(body, div)
    append_child(div, Text(id=NodeId("t"), data="text"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    assert not any(isinstance(p, (ClipPushPlacement, ClipPopPlacement)) for p in placements)


def test_overflow_hidden_emits_balanced_clip_placements() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    div = Element(
        id=NodeId("d"),
        tag="div",
        attrs={"style": "overflow: hidden; height: 50px; width: 200px"},
    )
    append_child(document, body)
    append_child(body, div)
    append_child(div, Text(id=NodeId("t"), data="text"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    pushes = [p for p in placements if isinstance(p, ClipPushPlacement)]
    pops = [p for p in placements if isinstance(p, ClipPopPlacement)]
    assert len(pushes) == 1
    assert len(pops) == 1
    push = pushes[0]
    assert push.width == 200
    assert push.height == 50


def test_overflow_scroll_and_auto_normalize_to_hidden_for_now() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    div = Element(
        id=NodeId("d"),
        tag="div",
        attrs={"style": "overflow: scroll; height: 30px"},
    )
    append_child(document, body)
    append_child(body, div)
    append_child(div, Text(id=NodeId("t"), data="x"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    pushes = [p for p in placements if isinstance(p, ClipPushPlacement)]
    assert len(pushes) == 1
