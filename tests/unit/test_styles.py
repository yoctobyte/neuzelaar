from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.styles import compute_styles, parse_declarations, root_style, style_text_blocks
from neuzelaar.engines.css.tinycss2_adapter import parse_stylesheet


def test_parse_declarations_keeps_supported_properties() -> None:
    declarations = parse_declarations("color: red; unknown: nope; font-weight: bold")

    assert declarations == {"color": "red", "font-weight": "bold"}


def test_parse_stylesheet_returns_internal_rules() -> None:
    rules = parse_stylesheet("p { color: blue; margin: 4px; unknown: nope }")

    assert len(rules) == 1
    assert rules[0].selector == "p"
    assert rules[0].declarations == {"color": "blue", "margin": "4px"}


def test_compute_styles_applies_rule_and_inline_override() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"style": "color: red"})
    append_child(document, paragraph)

    styles = compute_styles(document, parse_stylesheet("p { color: blue; font-weight: bold }"))

    assert styles[NodeId("p")].color == "red"
    assert styles[NodeId("p")].font_weight == "bold"


def test_style_text_blocks_and_root_style() -> None:
    document = Document(id=NodeId("doc"))
    head_style = Element(id=NodeId("style"), tag="style")
    body = Element(id=NodeId("body"), tag="body")
    append_child(document, head_style)
    append_child(head_style, Text(id=NodeId("css"), data="body { color: blue }"))
    append_child(document, body)

    rules = parse_stylesheet(style_text_blocks(document)[0])
    styles = compute_styles(document, rules)

    assert root_style(document, styles).color == "blue"


def test_compute_styles_matches_descendant_selectors() -> None:
    document = Document(id=NodeId("doc"))
    section = Element(id=NodeId("section"), tag="section")
    paragraph = Element(id=NodeId("paragraph"), tag="p")
    append_child(document, section)
    append_child(section, paragraph)

    styles = compute_styles(document, parse_stylesheet("section p { color: green }"))

    assert styles[NodeId("paragraph")].color == "green"


def test_compute_styles_keeps_spacing_properties() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(document, parse_stylesheet("p { margin: 12px; padding: 8px; font-size: 20px }"))

    assert styles[NodeId("p")].margin == "12px"
    assert styles[NodeId("p")].padding == "8px"
    assert styles[NodeId("p")].font_size == "20px"


def test_compute_styles_inherits_color_from_parent() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(document, parse_stylesheet("body { color: blue; font-size: 20px }"))

    assert styles[NodeId("p")].color == "blue"
    assert styles[NodeId("p")].font_size == "20px"


def test_compute_styles_does_not_inherit_background_color() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(document, parse_stylesheet("body { background-color: #eeeeee }"))

    assert styles[NodeId("body")].background_color == "#eeeeee"
    assert styles[NodeId("p")].background_color == "#ffffff"


def test_compute_styles_respects_specificity() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"id": "lead", "class": "note"})
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("p { color: red } .note { color: green } #lead { color: blue }"),
    )

    assert styles[NodeId("p")].color == "blue"


def test_compute_styles_specificity_ties_break_by_order() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"class": "note"})
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet(".note { color: green } .note { color: orange }"),
    )

    assert styles[NodeId("p")].color == "orange"


def test_compute_styles_resolves_em_against_parent_font_size() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("body { font-size: 20px } p { font-size: 1.5em }"),
    )

    assert styles[NodeId("p")].font_size == "30px"


def test_compute_styles_resolves_rem_against_root_font_size() -> None:
    document = Document(id=NodeId("doc"))
    html = Element(id=NodeId("html"), tag="html")
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, html)
    append_child(html, body)
    append_child(body, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("html { font-size: 20px } body { font-size: 30px } p { font-size: 2rem }"),
    )

    assert styles[NodeId("p")].font_size == "40px"


def test_compute_styles_respects_small_font_sizes_without_flooring() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(document, parse_stylesheet("p { font-size: 10px }"))

    assert styles[NodeId("p")].font_size == "10px"


def test_ua_stylesheet_sizes_headings_without_author_rules() -> None:
    document = Document(id=NodeId("doc"))
    h1 = Element(id=NodeId("h1"), tag="h1")
    h3 = Element(id=NodeId("h3"), tag="h3")
    append_child(document, h1)
    append_child(document, h3)

    styles = compute_styles(document)

    assert styles[NodeId("h1")].font_size == "32px"
    assert styles[NodeId("h1")].font_weight == "bold"
    assert styles[NodeId("h3")].font_size == "19px"


def test_compute_styles_handles_grouped_selectors() -> None:
    document = Document(id=NodeId("doc"))
    h1 = Element(id=NodeId("h1"), tag="h1")
    h2 = Element(id=NodeId("h2"), tag="h2")
    p = Element(id=NodeId("p"), tag="p")
    for child in (h1, h2, p):
        append_child(document, child)

    styles = compute_styles(document, parse_stylesheet("h1, h2 { color: green }"))

    assert styles[NodeId("h1")].color == "green"
    assert styles[NodeId("h2")].color == "green"
    assert styles[NodeId("p")].color != "green"
