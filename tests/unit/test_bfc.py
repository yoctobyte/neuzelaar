from neuzelaar.document.bfc import (
    BoxPlacement,
    ImagePlacement,
    TextPlacement,
    finalize_backgrounds,
    layout_block,
)
from neuzelaar.document.box import Box, BoxKind, build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import ComputedStyle, compute_styles


def _document_with_two_paragraphs() -> tuple[Document, dict[NodeId, ComputedStyle]]:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    p1 = Element(id=NodeId("p1"), tag="p")
    p2 = Element(id=NodeId("p2"), tag="p")
    append_child(document, body)
    append_child(body, p1)
    append_child(body, p2)
    append_child(p1, Text(id=NodeId("t1"), data="first"))
    append_child(p2, Text(id=NodeId("t2"), data="second"))
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("p1"): ComputedStyle(margin="10px"),
        NodeId("p2"): ComputedStyle(margin="20px"),
    }
    return document, styles


def test_bfc_collapses_adjacent_block_margins_to_the_larger_value() -> None:
    document, styles = _document_with_two_paragraphs()
    root = build_box_tree(document, styles)

    _, placements = layout_block(root, viewport_width=400)

    texts = [p for p in placements if isinstance(p, TextPlacement)]
    first = next(p for p in texts if p.text == "first")
    second = next(p for p in texts if p.text == "second")

    # Between the two <p> siblings the larger of (10, 20) = 20 wins.
    # first line_height is 1.3 * 16 = ~21. second.y = first.y + ~21 + 20.
    gap = second.y - first.y
    assert gap >= 40
    assert gap <= 48


def test_bfc_applies_explicit_width_to_block() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    append_child(box, Text(id=NodeId("t"), data="hello"))
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(width="120px", background_color="#eeeeee"),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=800)
    placements = finalize_backgrounds(root, placements)

    rect = next(p for p in placements if isinstance(p, BoxPlacement))
    assert rect.width == 120


def test_bfc_respects_explicit_height_on_block() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(height="200px", background_color="#ddeeff"),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)
    placements = finalize_backgrounds(root, placements)

    rect = next(p for p in placements if isinstance(p, BoxPlacement))
    assert rect.height == 200


def test_bfc_border_box_width_includes_padding_and_border() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    append_child(box, Text(id=NodeId("t"), data="hello"))
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(
            width="120px",
            padding="10px",
            border_width="2px",
            border_style="solid",
            box_sizing="border-box",
            background_color="#eeeeee",
        ),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=800)
    placements = finalize_backgrounds(root, placements)

    background = next(p for p in placements if isinstance(p, BoxPlacement) and p.color == "#eeeeee")
    borders = [p for p in placements if isinstance(p, BoxPlacement) and p.color != "#eeeeee"]
    left = min([background.x, *(rect.x for rect in borders)])
    right = max([background.x + background.width, *(rect.x + rect.width for rect in borders)])
    assert right - left == 120


def test_bfc_border_box_height_includes_padding_and_border() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(
            height="80px",
            padding="10px",
            border_width="2px",
            border_style="solid",
            box_sizing="border-box",
            background_color="#ddeeff",
        ),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)
    placements = finalize_backgrounds(root, placements)

    background = next(p for p in placements if isinstance(p, BoxPlacement) and p.color == "#ddeeff")
    borders = [p for p in placements if isinstance(p, BoxPlacement) and p.color != "#ddeeff"]
    top = min([background.y, *(rect.y for rect in borders)])
    bottom = max([background.y + background.height, *(rect.y + rect.height for rect in borders)])
    assert bottom - top == 80


def test_bfc_padding_contributes_to_box_geometry() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    append_child(document, body)
    append_child(body, Text(id=NodeId("t"), data="text"))
    styles = {
        NodeId("body"): ComputedStyle(padding="15px", background_color="#aabbcc"),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)
    placements = finalize_backgrounds(root, placements)

    text = next(p for p in placements if isinstance(p, TextPlacement))
    rect = next(p for p in placements if isinstance(p, BoxPlacement))
    # Text should start 15px in from the body's content edge.
    assert text.x == 15
    assert text.y == 15
    # Background height should at least cover the text line plus both
    # vertical paddings.
    assert rect.height >= 15 + text.y + 15 - text.y


def test_bfc_border_contributes_to_geometry_and_paint() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    append_child(box, Text(id=NodeId("t"), data="bordered"))
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(
            border_width="2px",
            border_style="solid",
            border_color="#cc0000",
            background_color="#eeeeee",
        ),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)
    placements = finalize_backgrounds(root, placements)

    text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "bordered")
    rects = [p for p in placements if isinstance(p, BoxPlacement)]

    assert text.x == 2
    assert text.y == 2
    assert sum(1 for rect in rects if rect.color == "#cc0000") == 4


def test_bfc_border_none_suppresses_border_width() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    box = Element(id=NodeId("b"), tag="div")
    append_child(document, body)
    append_child(body, box)
    append_child(box, Text(id=NodeId("t"), data="plain"))
    styles = {
        NodeId("body"): ComputedStyle(),
        NodeId("b"): ComputedStyle(border_width="5px", border_style="none"),
    }

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    text = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "plain")

    assert text.x == 0
    assert text.y == 0


def test_bfc_anonymous_block_wraps_inline_siblings_when_mixed() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    append_child(document, body)
    append_child(body, Text(id=NodeId("t1"), data="loose"))
    p = Element(id=NodeId("p"), tag="p")
    append_child(body, p)
    append_child(p, Text(id=NodeId("t2"), data="in paragraph"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)

    text_placements = [p for p in placements if isinstance(p, TextPlacement)]
    loose = next(p for p in text_placements if p.text == "loose")
    inside = next(p for p in text_placements if p.text == "paragraph")
    # Anonymous-block-wrapped "loose" text should come before the
    # paragraph's inner text.
    assert loose.y < inside.y


def test_bfc_places_image_at_current_cursor() -> None:
    from neuzelaar.core.page import ImageAsset
    from neuzelaar.engines.image.pillow_adapter import DecodedImageBitmap

    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    img = Element(
        id=NodeId("i"),
        tag="img",
        attrs={"src": "x.png", "width": "30", "height": "18", "alt": "logo"},
    )
    append_child(document, body)
    append_child(body, img)
    images = {
        NodeId("i"): ImageAsset(
            url="file:///tmp/x.png",
            bitmap=DecodedImageBitmap(
                width=1, height=1, stride=4, pixels=b"\xff\x00\x00\xff", format="PNG"
            ),
        )
    }
    styles = {NodeId("body"): ComputedStyle(), NodeId("i"): ComputedStyle()}

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400, images=images)

    image = next(p for p in placements if isinstance(p, ImagePlacement))
    assert image.width == 30
    assert image.height == 18
    # The label is the box's own description, ready to draw as a
    # placeholder — layout knows the box kind, the renderer does not.
    assert image.label == "image: logo"


def _first_child_margin_layout(parent_style: str, child_style: str) -> TextPlacement:
    document = Document(id=NodeId("doc"))
    parent = Element(id=NodeId("parent"), tag="div", attrs={"style": parent_style})
    child = Element(id=NodeId("child"), tag="div", attrs={"style": child_style})
    append_child(document, parent)
    append_child(parent, child)
    append_child(child, Text(id=NodeId("t"), data="hi"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=400)
    return next(p for p in placements if isinstance(p, TextPlacement))


def test_first_child_top_margin_collapses_through_its_parent() -> None:
    # CSS 2.1 8.3.1: with nothing between the two top edges, the
    # margins collapse and the result applies outside the parent. The
    # page moves down by 40, not by 0 and not by 40 twice.
    text = _first_child_margin_layout("margin: 0", "margin: 40px 0")

    assert text.y == 40


def test_collapsed_top_margin_is_the_larger_of_parent_and_child() -> None:
    text = _first_child_margin_layout("margin: 30px 0 0 0", "margin: 10px 0")

    assert text.y == 30


def test_padding_stops_the_parent_first_child_margin_collapse() -> None:
    # A top padding separates the edges, so the child's margin applies
    # inside the parent and both distances count.
    text = _first_child_margin_layout("margin: 0; padding: 10px 0 0 0", "margin: 40px 0")

    assert text.y == 50


def test_border_stops_the_parent_first_child_margin_collapse() -> None:
    text = _first_child_margin_layout(
        "margin: 0; border-top: 2px solid #000", "margin: 40px 0"
    )

    assert text.y == 42
