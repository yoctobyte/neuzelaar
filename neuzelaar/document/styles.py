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
    margin: str = "0"
    padding: str = "0"


SUPPORTED_PROPERTIES = {
    "background-color",
    "color",
    "display",
    "font-size",
    "font-weight",
    "margin",
    "padding",
}

# Properties that inherit from parent by default in CSS. Non-listed
# supported properties fall back to the initial value instead.
INHERITED_PROPERTIES = {
    "color",
    "font-size",
    "font-weight",
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
        parent_style = _parent_style(node, styles)
        declarations = _cascade_declarations(node, rules)
        styles[node.id] = _style_from_declarations(declarations, parent_style)
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


def _cascade_declarations(node: Element, rules: tuple[StyleRule, ...]) -> dict[str, str]:
    matches: list[tuple[tuple[int, int, int], int, dict[str, str]]] = []
    order = 0
    for rule in rules:
        for selector in _split_selector_group(rule.selector):
            if _matches_selector(node, selector):
                matches.append((_selector_specificity(selector), order, _supported(rule.declarations)))
                order += 1
    # Sort ascending so later (higher-specificity / later document order)
    # entries overwrite earlier ones via dict.update.
    matches.sort(key=lambda item: (item[0], item[1]))
    declarations: dict[str, str] = {}
    for _, _, decls in matches:
        declarations.update(decls)
    inline_style = node.attr("style")
    if inline_style:
        # Inline declarations beat all selector-matched rules.
        declarations.update(parse_declarations(inline_style))
    return declarations


def _parent_style(node: Element, styles: dict[NodeId, ComputedStyle]) -> ComputedStyle:
    parent: Node | None = node.parent
    while parent is not None and not isinstance(parent, Element):
        parent = parent.parent
    if parent is None:
        return ComputedStyle()
    return styles.get(parent.id, ComputedStyle())


def _style_from_declarations(
    declarations: dict[str, str],
    parent_style: ComputedStyle,
) -> ComputedStyle:
    return ComputedStyle(
        color=declarations.get("color", parent_style.color),
        background_color=declarations.get("background-color", DEFAULT_BACKGROUND_COLOR),
        font_weight=declarations.get("font-weight", parent_style.font_weight),
        font_size=declarations.get("font-size", parent_style.font_size),
        display=declarations.get("display", DEFAULT_DISPLAY),
        margin=declarations.get("margin", "0"),
        padding=declarations.get("padding", "0"),
    )


def _split_selector_group(selector: str) -> list[str]:
    return [part.strip() for part in selector.split(",") if part.strip()]


def _selector_specificity(selector: str) -> tuple[int, int, int]:
    ids = classes = tags = 0
    for part in selector.split():
        if not part:
            continue
        if part.startswith("#"):
            ids += 1
        elif part.startswith("."):
            classes += 1
        else:
            tags += 1
    return (ids, classes, tags)


def _matches_selector(node: Element, selector: str) -> bool:
    parts = [part for part in selector.strip().split() if part]
    if not parts:
        return False
    # The rightmost simple selector must match the node itself.
    if not _matches_simple_selector(node, parts[-1]):
        return False
    parent = node.parent
    current: Element | None = parent if isinstance(parent, Element) else None
    for part in reversed(parts[:-1]):
        while current is not None and not _matches_simple_selector(current, part):
            parent = current.parent
            current = parent if isinstance(parent, Element) else None
        if current is None:
            return False
        parent = current.parent
        current = parent if isinstance(parent, Element) else None
    return True


def _matches_simple_selector(node: Element, selector: str) -> bool:
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
