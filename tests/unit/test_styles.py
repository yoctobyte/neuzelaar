from neuzelaar.document.dom import Document, Element, NodeId, append_child
from neuzelaar.document.styles import compute_styles, parse_declarations
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
