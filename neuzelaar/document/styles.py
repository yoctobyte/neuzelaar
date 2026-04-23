"""Internal style model and tiny cascade for early rendering."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.document.dom import Document, Element, NodeId, walk


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
        color=declarations.get("color", ComputedStyle.color),
        background_color=declarations.get("background-color", ComputedStyle.background_color),
        font_weight=declarations.get("font-weight", ComputedStyle.font_weight),
        font_size=declarations.get("font-size", ComputedStyle.font_size),
        display=declarations.get("display", ComputedStyle.display),
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
