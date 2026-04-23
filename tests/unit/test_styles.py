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
