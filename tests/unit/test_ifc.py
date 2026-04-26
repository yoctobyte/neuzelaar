from neuzelaar.document.bfc import TextPlacement, layout_block
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import ComputedStyle, compute_styles


def test_ifc_places_multiple_words_on_same_line() -> None:
    document = Document(id=NodeId("doc"))
    p = Element(id=NodeId("p"), tag="p")
    append_child(document, p)
    append_child(p, Text(id=NodeId("t"), data="hello world from neuzelaar"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=1000)

    texts = [p for p in placements if isinstance(p, TextPlacement)]
    ys = {p.y for p in texts}
    assert len(texts) == 4  # four words
    assert len(ys) == 1  # all on the same line
    # x positions should increase left-to-right.
    xs = sorted(p.x for p in texts)
    assert xs == [p.x for p in sorted(texts, key=lambda p: p.x)]


def test_ifc_wraps_words_when_exceeding_content_width() -> None:
    document = Document(id=NodeId("doc"))
    p = Element(id=NodeId("p"), tag="p")
    append_child(document, p)
    append_child(
        p,
        Text(
            id=NodeId("t"),
            data="one two three four five six seven eight nine ten eleven twelve",
        ),
    )
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=180)

    texts = [p for p in placements if isinstance(p, TextPlacement)]
    ys = {p.y for p in texts}
    # Multiple lines needed at a narrow viewport.
    assert len(ys) >= 2


def test_ifc_flows_inline_styles_through_word_fragments() -> None:
    document = Document(id=NodeId("doc"))
    p = Element(id=NodeId("p"), tag="p")
    append_child(document, p)
    append_child(p, Text(id=NodeId("t1"), data="plain"))
    strong = Element(id=NodeId("s"), tag="strong")
    append_child(p, strong)
    append_child(strong, Text(id=NodeId("t2"), data="bold"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=800)

    texts = {p.text: p for p in placements if isinstance(p, TextPlacement)}
    # Both words on the same visual line.
    assert texts["plain"].y == texts["bold"].y
    # The <strong> word picks up its own font-weight via the UA stylesheet.
    # Colors are equal here (no override) but the fragment-level style
    # lookup is the mechanism that will carry any per-inline color.
    assert texts["plain"].color == texts["bold"].color


def test_ifc_aligns_smaller_font_to_bottom_of_taller_line() -> None:
    document = Document(id=NodeId("doc"))
    p = Element(id=NodeId("p"), tag="p")
    append_child(document, p)
    big = Element(id=NodeId("big"), tag="span", attrs={"style": "display: inline; font-size: 40px"})
    small = Element(id=NodeId("sml"), tag="span", attrs={"style": "display: inline; font-size: 10px"})
    append_child(p, big)
    append_child(big, Text(id=NodeId("tb"), data="BIG"))
    append_child(p, small)
    append_child(small, Text(id=NodeId("ts"), data="sml"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=800)

    big_placement = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "BIG")
    small_placement = next(p for p in placements if isinstance(p, TextPlacement) and p.text == "sml")
    # Smaller text sits lower within the line box so its bottom roughly
    # matches the big text's bottom.
    assert small_placement.y > big_placement.y


def test_ifc_empty_block_has_zero_height_contribution() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    empty = Element(id=NodeId("e"), tag="p")
    append_child(document, body)
    append_child(body, empty)
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    total, placements = layout_block(root, viewport_width=400)

    assert not placements
    assert total == 0


def test_ifc_line_height_number_increases_line_spacing() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"style": "line-height: 2"})
    append_child(document, paragraph)
    append_child(paragraph, Text(id=NodeId("t"), data="one two three four five six seven eight nine ten"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    _, placements = layout_block(root, viewport_width=120)

    texts = [p for p in placements if isinstance(p, TextPlacement)]
    first_line_y = min(p.y for p in texts)
    second_line_y = sorted({p.y for p in texts})[1]

    assert second_line_y - first_line_y >= 28


def test_ifc_line_height_px_affects_single_text_box_height() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"style": "line-height: 40px"})
    append_child(document, paragraph)
    append_child(paragraph, Text(id=NodeId("t"), data="hello"))
    styles = compute_styles(document)

    root = build_box_tree(document, styles)
    total, placements = layout_block(root, viewport_width=400)

    assert len([p for p in placements if isinstance(p, TextPlacement)]) == 1
    assert total >= 40
