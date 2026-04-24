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
    text_align: str = "left"
    width: str = "auto"
    height: str = "auto"


SUPPORTED_PROPERTIES = {
    "background-color",
    "color",
    "display",
    "font-size",
    "font-weight",
    "height",
    "margin",
    "padding",
    "text-align",
    "width",
}

# Properties that inherit from parent by default in CSS. Non-listed
# supported properties fall back to the initial value instead.
INHERITED_PROPERTIES = {
    "color",
    "font-size",
    "font-weight",
    "text-align",
}

DEFAULT_COLOR = "#141414"
DEFAULT_BACKGROUND_COLOR = "#ffffff"
DEFAULT_FONT_WEIGHT = "normal"
DEFAULT_FONT_SIZE = "16px"
DEFAULT_DISPLAY = "block"


# Minimal user-agent stylesheet. Prepended before author rules so that
# author rules with equal specificity win via the stable document-order
# tiebreak.
UA_STYLESHEET: tuple[StyleRule, ...] = (
    StyleRule("h1", {"font-size": "2em", "font-weight": "bold"}),
    StyleRule("h2", {"font-size": "1.5em", "font-weight": "bold"}),
    StyleRule("h3", {"font-size": "1.17em", "font-weight": "bold"}),
    StyleRule("h4", {"font-size": "1em", "font-weight": "bold"}),
    StyleRule("h5", {"font-size": "0.83em", "font-weight": "bold"}),
    StyleRule("h6", {"font-size": "0.67em", "font-weight": "bold"}),
    StyleRule("b, strong", {"font-weight": "bold"}),
    # Inline flow defaults: these elements participate in the parent's
    # inline formatting context rather than starting a new block line.
    StyleRule(
        "a, span, strong, em, b, i, u, code, small, mark, cite, abbr, q,"
        " sub, sup, tt, kbd, samp, var, time, dfn, s, del, ins",
        {"display": "inline"},
    ),
    StyleRule("i, em, cite, dfn, var", {"font-weight": "normal"}),
)


def compute_styles(document: Document, rules: tuple[StyleRule, ...] = ()) -> dict[NodeId, ComputedStyle]:
    styles: dict[NodeId, ComputedStyle] = {}
    root_px: int | None = None
    all_rules = UA_STYLESHEET + tuple(rules)
    for node in walk(document):
        if not isinstance(node, Element):
            continue
        parent_style = _parent_style(node, styles)
        declarations = _cascade_declarations(node, all_rules)
        parent_px = _font_size_to_px(parent_style.font_size, fallback=16)
        resolved_px = _resolve_font_size(
            declarations.get("font-size"),
            parent_px=parent_px,
            root_px=root_px if root_px is not None else parent_px,
        )
        declarations["font-size"] = f"{resolved_px}px"
        if root_px is None:
            root_px = resolved_px
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
        text_align=_normalize_text_align(declarations.get("text-align"), parent_style.text_align),
        width=declarations.get("width", "auto"),
        height=declarations.get("height", "auto"),
    )


def _normalize_text_align(value: str | None, parent_value: str) -> str:
    if value is None:
        return parent_value
    normalized = value.strip().lower()
    if normalized in {"left", "right", "center", "justify"}:
        return normalized
    return parent_value


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


_FONT_SIZE_KEYWORDS: dict[str, int] = {
    "xx-small": 9,
    "x-small": 10,
    "small": 13,
    "medium": 16,
    "large": 18,
    "x-large": 24,
    "xx-large": 32,
}


def _resolve_font_size(raw: str | None, *, parent_px: int, root_px: int) -> int:
    if raw is None:
        return parent_px
    value = raw.strip().lower()
    if not value:
        return parent_px
    if value in _FONT_SIZE_KEYWORDS:
        return _FONT_SIZE_KEYWORDS[value]
    if value == "smaller":
        return max(int(round(parent_px * 5 / 6)), 1)
    if value == "larger":
        return max(int(round(parent_px * 6 / 5)), 1)
    for suffix, scale in (
        ("rem", root_px),
        ("em", parent_px),
        ("px", 1),
        ("pt", 4 / 3),
        ("%", parent_px / 100),
    ):
        if value.endswith(suffix):
            try:
                number = float(value[: -len(suffix)])
            except ValueError:
                return parent_px
            return max(int(round(number * scale)), 1)
    try:
        # Unitless values are not CSS-conformant for font-size, but some
        # stylesheets rely on them being treated as pixels.
        return max(int(round(float(value))), 1)
    except ValueError:
        return parent_px


def _font_size_to_px(value: str, *, fallback: int) -> int:
    text = value.strip().lower()
    if text.endswith("px"):
        try:
            return max(int(round(float(text[:-2]))), 1)
        except ValueError:
            return fallback
    return fallback


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
