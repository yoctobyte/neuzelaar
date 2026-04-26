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
    assert rules[0].important == frozenset()


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


def test_compute_styles_keeps_white_space_property() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(document, parse_stylesheet("p { white-space: pre }"))

    assert styles[NodeId("p")].white_space == "pre"


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


def test_ua_stylesheet_marks_emphasis_elements_italic() -> None:
    document = Document(id=NodeId("doc"))
    emphasis = Element(id=NodeId("em"), tag="em")
    append_child(document, emphasis)

    styles = compute_styles(document)

    assert styles[NodeId("em")].font_style == "italic"


def test_compute_styles_inherits_text_align() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(document, parse_stylesheet("body { text-align: center }"))

    assert styles[NodeId("body")].text_align == "center"
    assert styles[NodeId("p")].text_align == "center"


def test_compute_styles_ignores_invalid_text_align_values() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(document, parse_stylesheet("p { text-align: nonsense }"))

    assert styles[NodeId("p")].text_align == "left"


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


def test_compute_styles_matches_compound_selector_parts() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"id": "lead", "class": "note hero"})
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("p.note#lead { color: purple }"),
    )

    assert styles[NodeId("p")].color == "purple"


def test_compute_styles_matches_descendant_compound_selector() -> None:
    document = Document(id=NodeId("doc"))
    section = Element(id=NodeId("section"), tag="section", attrs={"class": "article"})
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"class": "lead"})
    append_child(document, section)
    append_child(section, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("section.article p.lead { color: teal }"),
    )

    assert styles[NodeId("p")].color == "teal"


def test_compute_styles_supports_inherit_initial_and_unset_keywords() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(
        id=NodeId("p"),
        tag="p",
        attrs={"style": "color: inherit; background-color: initial; text-align: unset"},
    )
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("body { color: blue; text-align: center; background-color: #222222 }"),
    )

    assert styles[NodeId("p")].color == "blue"
    assert styles[NodeId("p")].background_color == "#ffffff"
    assert styles[NodeId("p")].text_align == "center"


def test_compute_styles_resolves_font_size_keywords_through_cascade_keywords() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("body { font-size: 20px } p { font-size: inherit }"),
    )

    assert styles[NodeId("p")].font_size == "20px"


def test_parse_stylesheet_preserves_important_declarations() -> None:
    rules = parse_stylesheet("p { color: blue !important; margin-top: 4px }")

    assert rules[0].declarations == {"color": "blue", "margin-top": "4px"}
    assert rules[0].important == frozenset({"color"})


def test_compute_styles_supports_child_combinator() -> None:
    document = Document(id=NodeId("doc"))
    section = Element(id=NodeId("section"), tag="section")
    paragraph = Element(id=NodeId("p"), tag="p")
    span = Element(id=NodeId("span"), tag="span")
    append_child(document, section)
    append_child(section, paragraph)
    append_child(paragraph, span)

    styles = compute_styles(document, parse_stylesheet("section > p { color: navy } section > span { color: red }"))

    assert styles[NodeId("p")].color == "navy"
    assert styles[NodeId("span")].color != "red"


def test_compute_styles_supports_universal_selector() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, paragraph)

    styles = compute_styles(document, parse_stylesheet("* { color: olive }"))

    assert styles[NodeId("body")].color == "olive"
    assert styles[NodeId("p")].color == "olive"


def test_compute_styles_resolves_margin_longhands_over_shorthand() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("p { margin: 1px 2px; margin-left: 9px; margin-top: 4px }"),
    )

    assert styles[NodeId("p")].margin == "4px 2px 1px 9px"


def test_compute_styles_resolves_padding_longhands_over_shorthand() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("p { padding: 3px; padding-bottom: 8px; padding-right: 5px }"),
    )

    assert styles[NodeId("p")].padding == "3px 5px 8px 3px"


def test_compute_styles_respects_important_over_higher_specificity() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"id": "lead"})
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet("p { color: green !important } #lead { color: blue }"),
    )

    assert styles[NodeId("p")].color == "green"


def test_compute_styles_supports_adjacent_sibling_combinator() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    h1 = Element(id=NodeId("h1"), tag="h1")
    paragraph = Element(id=NodeId("p"), tag="p")
    trailing = Element(id=NodeId("span"), tag="span")
    append_child(document, body)
    append_child(body, h1)
    append_child(body, paragraph)
    append_child(body, trailing)

    styles = compute_styles(document, parse_stylesheet("h1 + p { color: maroon }"))

    assert styles[NodeId("p")].color == "maroon"
    assert styles[NodeId("span")].color != "maroon"


def test_compute_styles_supports_general_sibling_combinator() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    h1 = Element(id=NodeId("h1"), tag="h1")
    divider = Element(id=NodeId("divider"), tag="hr")
    paragraph = Element(id=NodeId("p"), tag="p")
    append_child(document, body)
    append_child(body, h1)
    append_child(body, divider)
    append_child(body, paragraph)

    styles = compute_styles(document, parse_stylesheet("h1 ~ p { color: brown }"))

    assert styles[NodeId("p")].color == "brown"


def test_compute_styles_supports_attribute_presence_selector() -> None:
    document = Document(id=NodeId("doc"))
    form = Element(id=NodeId("form"), tag="form")
    enabled = Element(id=NodeId("enabled"), tag="input", attrs={"name": "q"})
    disabled = Element(id=NodeId("disabled"), tag="input")
    append_child(document, form)
    append_child(form, enabled)
    append_child(form, disabled)

    styles = compute_styles(document, parse_stylesheet("input[name] { color: darkgreen }"))

    assert styles[NodeId("enabled")].color == "darkgreen"
    assert styles[NodeId("disabled")].color != "darkgreen"


def test_compute_styles_supports_attribute_value_selector() -> None:
    document = Document(id=NodeId("doc"))
    form = Element(id=NodeId("form"), tag="form")
    text_input = Element(id=NodeId("text"), tag="input", attrs={"type": "text"})
    button = Element(id=NodeId("button"), tag="input", attrs={"type": "submit"})
    append_child(document, form)
    append_child(form, text_input)
    append_child(form, button)

    styles = compute_styles(document, parse_stylesheet('input[type="text"] { color: purple }'))

    assert styles[NodeId("text")].color == "purple"
    assert styles[NodeId("button")].color != "purple"


def test_compute_styles_supports_compound_attribute_selector() -> None:
    document = Document(id=NodeId("doc"))
    paragraph = Element(id=NodeId("p"), tag="p", attrs={"class": "lead", "data-kind": "hero"})
    append_child(document, paragraph)

    styles = compute_styles(
        document,
        parse_stylesheet('p.lead[data-kind="hero"] { color: crimson }'),
    )

    assert styles[NodeId("p")].color == "crimson"


def test_compute_styles_supports_attribute_contains_word_selector() -> None:
    document = Document(id=NodeId("doc"))
    item = Element(id=NodeId("item"), tag="div", attrs={"data-tags": "alpha beta gamma"})
    append_child(document, item)

    styles = compute_styles(document, parse_stylesheet('div[data-tags~="beta"] { color: seagreen }'))

    assert styles[NodeId("item")].color == "seagreen"


def test_compute_styles_supports_attribute_dash_prefix_selector() -> None:
    document = Document(id=NodeId("doc"))
    item = Element(id=NodeId("item"), tag="div", attrs={"lang": "en-US"})
    append_child(document, item)

    styles = compute_styles(document, parse_stylesheet('div[lang|="en"] { color: steelblue }'))

    assert styles[NodeId("item")].color == "steelblue"


def test_compute_styles_supports_attribute_prefix_suffix_and_substring_selectors() -> None:
    document = Document(id=NodeId("doc"))
    image = Element(id=NodeId("img"), tag="img", attrs={"src": "/assets/icons/logo-dark.png"})
    append_child(document, image)

    styles = compute_styles(
        document,
        parse_stylesheet(
            'img[src^="/assets"][src*="logo"][src$=".png"] { color: orange }'
        ),
    )

    assert styles[NodeId("img")].color == "orange"


def test_compute_styles_supports_first_child_pseudo_class() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    first = Element(id=NodeId("first"), tag="p")
    second = Element(id=NodeId("second"), tag="p")
    append_child(document, body)
    append_child(body, first)
    append_child(body, second)

    styles = compute_styles(document, parse_stylesheet("p:first-child { color: navy }"))

    assert styles[NodeId("first")].color == "navy"
    assert styles[NodeId("second")].color != "navy"


def test_compute_styles_supports_last_child_pseudo_class() -> None:
    document = Document(id=NodeId("doc"))
    body = Element(id=NodeId("body"), tag="body")
    first = Element(id=NodeId("first"), tag="p")
    second = Element(id=NodeId("second"), tag="p")
    append_child(document, body)
    append_child(body, first)
    append_child(body, second)

    styles = compute_styles(document, parse_stylesheet("p:last-child { color: teal }"))

    assert styles[NodeId("first")].color != "teal"
    assert styles[NodeId("second")].color == "teal"


def test_compute_styles_keeps_text_decoration() -> None:
    document = Document(id=NodeId("doc"))
    link = Element(id=NodeId("link"), tag="a")
    append_child(document, link)

    styles = compute_styles(document, parse_stylesheet("a { text-decoration: underline }"))

    assert styles[NodeId("link")].text_decoration == "underline"
