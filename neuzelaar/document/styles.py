"""Internal style model and tiny cascade for early rendering."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.document.dom import Document, Element, Node, NodeId, Text, walk


@dataclass(frozen=True, slots=True)
class StyleRule:
    selector: str
    declarations: dict[str, str]


@dataclass(frozen=True, slots=True)
class ComputedStyle:
    color: str = "#141414"
    background_color: str = "#ffffff"
    font_weight: str = "normal"
    font_size: str = "16px"
    display: str = "block"


SUPPORTED_PROPERTIES = {
    "background-color",
    "color",
    "display",
    "font-size",
    "font-weight",
    "margin",
    "padding",
}

DEFAULT_COLOR = "#141414"
DEFAULT_BACKGROUND_COLOR = "#ffffff"
DEFAULT_FONT_WEIGHT = "normal"
DEFAULT_FONT_SIZE = "16px"
DEFAULT_DISPLAY = "block"


def compute_styles(document: Document, rules: tuple[StyleRule, ...] = ()) -> dict[NodeId, ComputedStyle]:
    styles: dict[NodeId, ComputedStyle] = {}
    for node in walk(document):
        if not isinstance(node, Element):
            continue
        declarations: dict[str, str] = {}
        for rule in rules:
            if _matches_selector(node, rule.selector):
                declarations.update(_supported(rule.declarations))
        inline_style = node.attr("style")
        if inline_style:
            declarations.update(parse_declarations(inline_style))
        styles[node.id] = _style_from_declarations(declarations)
    return styles


def style_text_blocks(document: Document) -> tuple[str, ...]:
    blocks: list[str] = []
    for node in walk(document):
        if isinstance(node, Element) and node.tag.lower() == "style":
            text = _text_content(node)
            if text:
                blocks.append(text)
    return tuple(blocks)


def root_style(document: Document, styles: dict[NodeId, ComputedStyle]) -> ComputedStyle:
    for node in walk(document):
        if isinstance(node, Element) and node.tag.lower() == "body":
            return styles.get(node.id, ComputedStyle())
    return ComputedStyle()


def parse_declarations(text: str) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for raw in text.split(";"):
        if ":" not in raw:
            continue
        name, value = raw.split(":", 1)
        name = name.strip().lower()
        if name in SUPPORTED_PROPERTIES:
            declarations[name] = value.strip()
    return declarations


def _supported(declarations: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in declarations.items() if name in SUPPORTED_PROPERTIES}


def _style_from_declarations(declarations: dict[str, str]) -> ComputedStyle:
    return ComputedStyle(
        color=declarations.get("color", DEFAULT_COLOR),
        background_color=declarations.get("background-color", DEFAULT_BACKGROUND_COLOR),
        font_weight=declarations.get("font-weight", DEFAULT_FONT_WEIGHT),
        font_size=declarations.get("font-size", DEFAULT_FONT_SIZE),
        display=declarations.get("display", DEFAULT_DISPLAY),
    )


def _matches_selector(node: Element, selector: str) -> bool:
    selector = selector.strip()
    if not selector:
        return False
    if selector.startswith("."):
        classes = (node.attr("class") or "").split()
        return selector[1:] in classes
    if selector.startswith("#"):
        return node.attr("id") == selector[1:]
    return node.tag.lower() == selector.lower()


def _text_content(node: Node) -> str:
    if isinstance(node, Text):
        return node.data
    children = getattr(node, "children", None)
    if not children:
        return ""
    return "".join(_text_content(child) for child in children)
