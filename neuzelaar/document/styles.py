"""Internal style model and tiny cascade for early rendering."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from neuzelaar.document.dom import Document, Element, Node, NodeId, Text, walk


@dataclass(frozen=True, slots=True)
class StyleRule:
    selector: str
    declarations: dict[str, str]
    important: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ComputedStyle:
    color: str = "#141414"
    background_color: str = "#ffffff"
    border_width: str = "0"
    border_style: str = "none"
    border_color: str = "currentcolor"
    box_sizing: str = "content-box"
    font_weight: str = "normal"
    font_style: str = "normal"
    font_size: str = "16px"
    line_height: str = "normal"
    text_transform: str = "none"
    text_decoration: str = "none"
    white_space: str = "normal"
    display: str = "block"
    margin: str = "0"
    padding: str = "0"
    text_align: str = "left"
    width: str = "auto"
    height: str = "auto"
    float: str = "none"
    clear: str = "none"
    position: str = "static"
    top: str = "auto"
    right: str = "auto"
    bottom: str = "auto"
    left: str = "auto"
    overflow: str = "visible"
    z_index: str = "auto"


SUPPORTED_PROPERTIES = {
    "background-color",
    "border",
    "border-bottom",
    "border-bottom-color",
    "border-bottom-style",
    "border-bottom-width",
    "border-color",
    "border-left",
    "border-left-color",
    "border-left-style",
    "border-left-width",
    "border-right",
    "border-right-color",
    "border-right-style",
    "border-right-width",
    "border-style",
    "border-top",
    "border-top-color",
    "border-top-style",
    "border-top-width",
    "border-width",
    "box-sizing",
    "bottom",
    "clear",
    "color",
    "display",
    "float",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "left",
    "line-height",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "overflow",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "position",
    "right",
    "text-align",
    "text-decoration",
    "text-transform",
    "top",
    "white-space",
    "width",
    "z-index",
}

# Properties that inherit from parent by default in CSS. Non-listed
# supported properties fall back to the initial value instead.
INHERITED_PROPERTIES = {
    "color",
    "font-size",
    "font-style",
    "font-weight",
    "line-height",
    "text-align",
    "text-transform",
    "white-space",
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
    StyleRule("i, em, cite, dfn, var", {"font-style": "italic"}),
)


def compute_styles(document: Document, rules: tuple[StyleRule, ...] = ()) -> dict[NodeId, ComputedStyle]:
    styles: dict[NodeId, ComputedStyle] = {}
    root_px: int | None = None
    all_rules = UA_STYLESHEET + tuple(rules)
    initial_values = _initial_style_values()
    rule_index = _build_rule_index(all_rules)
    for node in walk(document):
        if not isinstance(node, Element):
            continue
        parent_style = _parent_style(node, styles)
        declarations = _cascade_declarations(node, rule_index)
        parent_px = _font_size_to_px(parent_style.font_size, fallback=16)
        raw_font_size = _resolve_property_value(
            "font-size",
            declarations,
            parent_style,
            initial_values,
        )
        resolved_px = _resolve_font_size(
            raw_font_size,
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
            declarations[name] = value.replace("!important", "").strip()
    return declarations


def _supported(declarations: dict[str, str]) -> dict[str, str]:
    return {name: value for name, value in declarations.items() if name in SUPPORTED_PROPERTIES}


@dataclass(frozen=True, slots=True)
class _PreparedRule:
    """A single comma-split selector with its rule's declarations.

    `order` is assigned globally at index-build time so cascade
    tie-breaking still favors later rules even when matches arrive
    out of source order via the per-bucket lookup.
    """
    selector: str
    specificity: tuple[int, int, int]
    order: int
    declarations: dict[str, str]
    important: frozenset[str]


@dataclass(frozen=True, slots=True)
class _RuleIndex:
    """Buckets prepared rules by their rightmost simple selector.

    Per-node lookup unions the buckets for the node's id, each of its
    classes, its tag, and the universal bucket — yielding only rules
    that *could* match. Each prepared rule is filed in exactly one
    bucket (most discriminating attribute wins), so unioning at query
    time does not produce duplicates.
    """
    by_id: dict[str, list[_PreparedRule]]
    by_class: dict[str, list[_PreparedRule]]
    by_tag: dict[str, list[_PreparedRule]]
    universal: list[_PreparedRule]


def _build_rule_index(rules: tuple[StyleRule, ...]) -> _RuleIndex:
    by_id: dict[str, list[_PreparedRule]] = {}
    by_class: dict[str, list[_PreparedRule]] = {}
    by_tag: dict[str, list[_PreparedRule]] = {}
    universal: list[_PreparedRule] = []
    order = 0
    for rule in rules:
        supported = _supported(rule.declarations)
        if not supported:
            continue
        for selector in _split_selector_group(rule.selector):
            steps = _parse_selector_steps(selector)
            if not steps:
                continue
            rightmost = _parse_simple_selector(steps[-1][1])
            if rightmost is None:
                continue
            prepared = _PreparedRule(
                selector=selector,
                specificity=_selector_specificity(selector),
                order=order,
                declarations=supported,
                important=rule.important,
            )
            order += 1
            if rightmost.id_name is not None:
                by_id.setdefault(rightmost.id_name, []).append(prepared)
            elif rightmost.classes:
                by_class.setdefault(rightmost.classes[0], []).append(prepared)
            elif rightmost.tag is not None and rightmost.tag != "*":
                by_tag.setdefault(rightmost.tag, []).append(prepared)
            else:
                universal.append(prepared)
    return _RuleIndex(by_id=by_id, by_class=by_class, by_tag=by_tag, universal=universal)


def _candidate_rules(index: _RuleIndex, node: Element) -> list[_PreparedRule]:
    candidates: list[_PreparedRule] = []
    node_id_attr = node.attr("id")
    if node_id_attr and node_id_attr in index.by_id:
        candidates.extend(index.by_id[node_id_attr])
    classes_attr = node.attr("class")
    if classes_attr:
        for cls in classes_attr.split():
            bucket = index.by_class.get(cls)
            if bucket is not None:
                candidates.extend(bucket)
    tag_bucket = index.by_tag.get(node.tag.lower())
    if tag_bucket is not None:
        candidates.extend(tag_bucket)
    candidates.extend(index.universal)
    return candidates


def _cascade_declarations(node: Element, index: _RuleIndex) -> dict[str, str]:
    matches: list[tuple[tuple[int, int, int], int, dict[str, str], frozenset[str]]] = []
    for prepared in _candidate_rules(index, node):
        if _matches_selector(node, prepared.selector):
            matches.append(
                (prepared.specificity, prepared.order, prepared.declarations, prepared.important)
            )
    declarations = _flatten_cascade_matches(matches)
    inline_style = node.attr("style")
    if inline_style:
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
    initial_values = _initial_style_values()
    color = _normalize_color(
        _resolve_property_value("color", declarations, parent_style, initial_values),
        parent_style.color,
    )
    return ComputedStyle(
        color=color,
        background_color=_normalize_background_color(
            _resolve_property_value("background-color", declarations, parent_style, initial_values)
        ),
        border_width=_normalize_border_box(
            _resolve_border_property("width", declarations, parent_style, initial_values),
            default="0",
        ),
        border_style=_normalize_border_style_box(
            _resolve_border_property("style", declarations, parent_style, initial_values),
        ),
        border_color=_normalize_border_color_box(
            _resolve_border_property("color", declarations, parent_style, initial_values),
            color,
        ),
        box_sizing=_normalize_box_sizing(
            _resolve_property_value("box-sizing", declarations, parent_style, initial_values)
        ),
        font_weight=_normalize_font_weight(
            _resolve_property_value("font-weight", declarations, parent_style, initial_values),
            parent_style.font_weight,
        ),
        font_style=_normalize_font_style(
            _resolve_property_value("font-style", declarations, parent_style, initial_values),
            parent_style.font_style,
        ),
        font_size=_normalize_font_size(
            _resolve_property_value("font-size", declarations, parent_style, initial_values),
            parent_style.font_size,
        ),
        line_height=_normalize_line_height(
            _resolve_property_value("line-height", declarations, parent_style, initial_values),
            parent_style.line_height,
        ),
        text_transform=_normalize_text_transform(
            _resolve_property_value("text-transform", declarations, parent_style, initial_values),
            parent_style.text_transform,
        ),
        text_decoration=_normalize_text_decoration(
            _resolve_property_value("text-decoration", declarations, parent_style, initial_values)
        ),
        white_space=_normalize_white_space(
            _resolve_property_value("white-space", declarations, parent_style, initial_values),
            parent_style.white_space,
        ),
        display=_normalize_display(
            _resolve_property_value("display", declarations, parent_style, initial_values)
        ),
        margin=_resolve_box_property("margin", declarations, parent_style, initial_values),
        padding=_resolve_box_property("padding", declarations, parent_style, initial_values),
        text_align=_normalize_text_align(
            _resolve_property_value("text-align", declarations, parent_style, initial_values),
            parent_style.text_align,
        ),
        width=_normalize_length_or_auto(
            _resolve_property_value("width", declarations, parent_style, initial_values)
        ),
        height=_normalize_length_or_auto(
            _resolve_property_value("height", declarations, parent_style, initial_values)
        ),
        float=_normalize_float(
            _resolve_property_value("float", declarations, parent_style, initial_values)
        ),
        clear=_normalize_clear(
            _resolve_property_value("clear", declarations, parent_style, initial_values)
        ),
        position=_normalize_position(
            _resolve_property_value("position", declarations, parent_style, initial_values)
        ),
        top=_normalize_offset(
            _resolve_property_value("top", declarations, parent_style, initial_values)
        ),
        right=_normalize_offset(
            _resolve_property_value("right", declarations, parent_style, initial_values)
        ),
        bottom=_normalize_offset(
            _resolve_property_value("bottom", declarations, parent_style, initial_values)
        ),
        left=_normalize_offset(
            _resolve_property_value("left", declarations, parent_style, initial_values)
        ),
        overflow=_normalize_overflow(
            _resolve_property_value("overflow", declarations, parent_style, initial_values)
        ),
        z_index=_normalize_z_index(
            _resolve_property_value("z-index", declarations, parent_style, initial_values)
        ),
    )


def _initial_style_values() -> dict[str, str]:
    return {
        "background-color": DEFAULT_BACKGROUND_COLOR,
        "border": "medium none currentcolor",
        "border-bottom": "medium none currentcolor",
        "border-bottom-color": "currentcolor",
        "border-bottom-style": "none",
        "border-bottom-width": "medium",
        "border-color": "currentcolor",
        "border-left": "medium none currentcolor",
        "border-left-color": "currentcolor",
        "border-left-style": "none",
        "border-left-width": "medium",
        "border-right": "medium none currentcolor",
        "border-right-color": "currentcolor",
        "border-right-style": "none",
        "border-right-width": "medium",
        "border-style": "none",
        "border-top": "medium none currentcolor",
        "border-top-color": "currentcolor",
        "border-top-style": "none",
        "border-top-width": "medium",
        "border-width": "medium",
        "box-sizing": "content-box",
        "bottom": "auto",
        "clear": "none",
        "color": DEFAULT_COLOR,
        "display": DEFAULT_DISPLAY,
        "float": "none",
        "font-size": DEFAULT_FONT_SIZE,
        "font-style": "normal",
        "font-weight": DEFAULT_FONT_WEIGHT,
        "height": "auto",
        "left": "auto",
        "line-height": "normal",
        "margin": "0",
        "margin-bottom": "0",
        "margin-left": "0",
        "margin-right": "0",
        "margin-top": "0",
        "overflow": "visible",
        "padding": "0",
        "padding-bottom": "0",
        "padding-left": "0",
        "padding-right": "0",
        "padding-top": "0",
        "position": "static",
        "right": "auto",
        "text-align": "left",
        "text-decoration": "none",
        "text-transform": "none",
        "top": "auto",
        "white-space": "normal",
        "width": "auto",
        "z-index": "auto",
    }


def _resolve_property_value(
    name: str,
    declarations: dict[str, str],
    parent_style: ComputedStyle,
    initial_values: dict[str, str],
) -> str:
    value = declarations.get(name)
    if value is None or value.strip().lower() == "unset":
        if name in INHERITED_PROPERTIES:
            return getattr(parent_style, name.replace("-", "_"))
        return initial_values[name]
    normalized = value.strip()
    lowered = normalized.lower()
    if lowered == "inherit":
        return getattr(parent_style, name.replace("-", "_"))
    if lowered == "initial":
        return initial_values[name]
    return normalized


def _flatten_cascade_matches(
    matches: list[tuple[tuple[int, int, int], int, dict[str, str], frozenset[str]]]
) -> dict[str, str]:
    resolved: dict[str, tuple[int, tuple[int, int, int], int, str]] = {}
    for specificity, order, declarations, important in matches:
        for name, value in declarations.items():
            weight = 1 if name in important else 0
            current = resolved.get(name)
            candidate = (weight, specificity, order, value)
            if current is None or candidate[:3] >= current[:3]:
                resolved[name] = candidate
    return {name: value for name, (_, _, _, value) in resolved.items()}


def _resolve_box_property(
    prefix: str,
    declarations: dict[str, str],
    parent_style: ComputedStyle,
    initial_values: dict[str, str],
) -> str:
    shorthand = _resolve_property_value(prefix, declarations, parent_style, initial_values)
    top, right, bottom, left = _expand_box_tokens(shorthand)
    edges = {
        "top": top,
        "right": right,
        "bottom": bottom,
        "left": left,
    }
    for side in ("top", "right", "bottom", "left"):
        longhand_name = f"{prefix}-{side}"
        if longhand_name in declarations:
            edges[side] = _resolve_property_value(
                longhand_name,
                declarations,
                parent_style,
                initial_values,
            )
    return _compress_box_edges(edges["top"], edges["right"], edges["bottom"], edges["left"])


def _resolve_border_property(
    suffix: str,
    declarations: dict[str, str],
    parent_style: ComputedStyle,
    initial_values: dict[str, str],
) -> str:
    shorthand = _resolve_property_value(f"border-{suffix}", declarations, parent_style, initial_values)
    top, right, bottom, left = _expand_box_tokens(shorthand)
    edges = {
        "top": top,
        "right": right,
        "bottom": bottom,
        "left": left,
    }
    if "border" in declarations:
        border_all = _split_border_shorthand(
            _resolve_property_value("border", declarations, parent_style, initial_values)
        )
        if border_all[suffix] is not None:
            for side in edges:
                edges[side] = border_all[suffix]
    for side in ("top", "right", "bottom", "left"):
        side_name = f"border-{side}"
        if side_name in declarations:
            side_shorthand = _split_border_shorthand(
                _resolve_property_value(side_name, declarations, parent_style, initial_values)
            )
            if side_shorthand[suffix] is not None:
                edges[side] = side_shorthand[suffix]
        longhand_name = f"border-{side}-{suffix}"
        if longhand_name in declarations:
            edges[side] = _resolve_property_value(
                longhand_name,
                declarations,
                parent_style,
                initial_values,
            )
    return _compress_box_edges(edges["top"], edges["right"], edges["bottom"], edges["left"])


def _expand_box_tokens(value: str) -> tuple[str, str, str, str]:
    tokens = value.strip().split()
    if not tokens:
        return ("0", "0", "0", "0")
    if len(tokens) == 1:
        token = tokens[0]
        return (token, token, token, token)
    if len(tokens) == 2:
        top_bottom, right_left = tokens
        return (top_bottom, right_left, top_bottom, right_left)
    if len(tokens) == 3:
        top, right_left, bottom = tokens
        return (top, right_left, bottom, right_left)
    return (tokens[0], tokens[1], tokens[2], tokens[3])


def _compress_box_edges(top: str, right: str, bottom: str, left: str) -> str:
    if top == right == bottom == left:
        return top
    if top == bottom and right == left:
        return f"{top} {right}"
    if right == left:
        return f"{top} {right} {bottom}"
    return f"{top} {right} {bottom} {left}"


def _split_border_shorthand(value: str) -> dict[str, str | None]:
    result: dict[str, str | None] = {
        "width": None,
        "style": None,
        "color": None,
    }
    for token in value.strip().split():
        lowered = token.lower()
        if result["width"] is None and _is_border_width_token(lowered):
            result["width"] = lowered
            continue
        if result["style"] is None and lowered in _BORDER_STYLE_VALUES:
            result["style"] = lowered
            continue
        if result["color"] is None:
            result["color"] = token.strip()
    return result


def _normalize_color(value: str, fallback: str) -> str:
    text = value.strip()
    return text or fallback


def _normalize_background_color(value: str) -> str:
    text = value.strip()
    return text or DEFAULT_BACKGROUND_COLOR


def _normalize_border_box(value: str, *, default: str) -> str:
    edges = []
    for token in _expand_box_tokens(value):
        edges.append(_normalize_border_width_token(token, default=default))
    return _compress_box_edges(*edges)


def _normalize_border_width_token(value: str, *, default: str) -> str:
    text = value.strip().lower()
    if text in {"thin", "medium", "thick"}:
        return text
    if text.endswith("px"):
        text = text[:-2]
    try:
        return f"{max(int(round(float(text))), 0)}px"
    except ValueError:
        return default


def _normalize_border_style_box(value: str) -> str:
    edges = []
    for token in _expand_box_tokens(value):
        text = token.strip().lower()
        edges.append(text if text in _BORDER_STYLE_VALUES else "none")
    return _compress_box_edges(*edges)


def _normalize_border_color_box(value: str, fallback_color: str) -> str:
    edges = []
    for token in _expand_box_tokens(value):
        text = token.strip()
        if not text:
            edges.append("currentcolor")
        elif text.lower() == "currentcolor":
            edges.append(fallback_color)
        else:
            edges.append(text)
    return _compress_box_edges(*edges)


def _normalize_font_weight(value: str, fallback: str) -> str:
    text = value.strip().lower()
    if text in {"normal", "bold", "bolder", "lighter"}:
        return text
    if text.isdigit():
        return text
    return fallback


def _normalize_box_sizing(value: str | None) -> str:
    if value is None:
        return "content-box"
    normalized = value.strip().lower()
    if normalized in {"content-box", "border-box"}:
        return normalized
    return "content-box"


def _normalize_font_style(value: str, fallback: str) -> str:
    text = value.strip().lower()
    if text in {"normal", "italic", "oblique"}:
        return text
    return fallback


def _normalize_font_size(value: str, fallback: str) -> str:
    text = value.strip().lower()
    if text:
        return text
    return fallback


def _normalize_line_height(value: str, fallback: str) -> str:
    text = value.strip().lower()
    if not text:
        return fallback
    if text == "normal":
        return text
    try:
        float(text)
        return text
    except ValueError:
        pass
    for suffix in ("px", "em", "%"):
        if text.endswith(suffix):
            try:
                float(text[: -len(suffix)])
                return text
            except ValueError:
                return fallback
    return fallback


def _normalize_text_decoration(value: str) -> str:
    text = " ".join(value.strip().lower().split())
    if not text:
        return "none"
    if text == "none":
        return text
    supported = [part for part in text.split() if part in {"underline", "line-through"}]
    return " ".join(supported) if supported else "none"


def _normalize_text_transform(value: str | None, fallback: str) -> str:
    if value is None:
        return fallback
    normalized = value.strip().lower()
    if normalized in {"none", "uppercase", "lowercase", "capitalize"}:
        return normalized
    return fallback


def _normalize_white_space(value: str, fallback: str) -> str:
    text = value.strip().lower()
    if text in {"normal", "nowrap", "pre", "pre-wrap", "pre-line"}:
        return text
    return fallback


def _normalize_display(value: str) -> str:
    text = value.strip().lower()
    if text:
        return text
    return DEFAULT_DISPLAY


def _normalize_box_shorthand(value: str) -> str:
    text = " ".join(value.strip().split())
    return text or "0"


def _normalize_length_or_auto(value: str) -> str:
    text = value.strip().lower()
    return text or "auto"


def _normalize_offset(value: str) -> str:
    text = value.strip().lower()
    return text or "auto"


def _normalize_z_index(value: str) -> str:
    text = value.strip().lower()
    return text or "auto"


def _normalize_position(value: str | None) -> str:
    if value is None:
        return "static"
    normalized = value.strip().lower()
    if normalized in {"static", "relative", "absolute", "fixed"}:
        return normalized
    return "static"


def _normalize_overflow(value: str | None) -> str:
    if value is None:
        return "visible"
    normalized = value.strip().lower()
    if normalized in {"visible", "hidden", "clip", "scroll", "auto"}:
        # We treat scroll/auto/clip as hidden for visual purposes since
        # we have no scrollbar UI yet.
        if normalized in {"scroll", "auto", "clip"}:
            return "hidden"
        return normalized
    return "visible"


def _normalize_float(value: str | None) -> str:
    if value is None:
        return "none"
    normalized = value.strip().lower()
    if normalized in {"left", "right", "none"}:
        return normalized
    return "none"


def _normalize_clear(value: str | None) -> str:
    if value is None:
        return "none"
    normalized = value.strip().lower()
    if normalized in {"left", "right", "both", "none"}:
        return normalized
    return "none"


def _normalize_text_align(value: str | None, parent_value: str) -> str:
    if value is None:
        return parent_value
    normalized = value.strip().lower()
    if normalized in {"left", "right", "center", "justify"}:
        return normalized
    return parent_value


@lru_cache(maxsize=4096)
def _split_selector_group(selector: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in selector.split(",") if part.strip())


@lru_cache(maxsize=4096)
def _selector_specificity(selector: str) -> tuple[int, int, int]:
    ids = classes = tags = 0
    for combinator, part in _parse_selector_steps(selector):
        if combinator not in {" ", ">", "+", "~"}:
            continue
        parsed = _parse_simple_selector(part)
        if parsed is None:
            continue
        ids += 1 if parsed.id_name is not None else 0
        classes += len(parsed.classes) + len(parsed.attributes)
        for pseudo, arg in parsed.pseudo_classes:
            if pseudo == "not" and arg is not None:
                arg_parsed = _parse_simple_selector(arg)
                if arg_parsed is not None:
                    ids += 1 if arg_parsed.id_name is not None else 0
                    classes += len(arg_parsed.classes) + len(arg_parsed.attributes)
                    tags += 1 if arg_parsed.tag not in (None, "*") else 0
                    continue
            classes += 1
        tags += 1 if parsed.tag not in (None, "*") else 0
    return (ids, classes, tags)


def _matches_selector(node: Element, selector: str) -> bool:
    steps = _parse_selector_steps(selector)
    if not steps:
        return False
    if not _matches_simple_selector(node, steps[-1][1]):
        return False
    current: Element = node
    for index in range(len(steps) - 1, 0, -1):
        combinator = steps[index][0]
        expected = steps[index - 1][1]
        if combinator == ">":
            parent = current.parent
            current = parent if isinstance(parent, Element) else None
            if current is None or not _matches_simple_selector(current, expected):
                return False
            continue
        if combinator in {"+", "~"}:
            sibling = _previous_element_sibling(current)
            if combinator == "+":
                current = sibling
                if current is None or not _matches_simple_selector(current, expected):
                    return False
                continue
            while sibling is not None and not _matches_simple_selector(sibling, expected):
                sibling = _previous_element_sibling(sibling)
            current = sibling
            if current is None:
                return False
            continue
        parent = current.parent
        current = parent if isinstance(parent, Element) else None
        while current is not None and not _matches_simple_selector(current, expected):
            parent = current.parent
            current = parent if isinstance(parent, Element) else None
        if current is None:
            return False
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

_BORDER_STYLE_VALUES = frozenset(
    {"none", "solid", "dashed", "dotted", "double", "hidden"}
)


def _is_border_width_token(value: str) -> bool:
    if value in {"thin", "medium", "thick"}:
        return True
    text = value[:-2] if value.endswith("px") else value
    try:
        float(text)
        return True
    except ValueError:
        return False


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
    parsed = _parse_simple_selector(selector)
    if parsed is None:
        return False
    if parsed.tag not in (None, "*") and node.tag.lower() != parsed.tag:
        return False
    if parsed.id_name is not None and node.attr("id") != parsed.id_name:
        return False
    if parsed.classes:
        classes = set((node.attr("class") or "").split())
        if not all(name in classes for name in parsed.classes):
            return False
    if parsed.attributes:
        for name, operator, expected in parsed.attributes:
            actual = node.attr(name)
            if actual is None:
                return False
            if not _matches_attribute(actual, operator, expected):
                return False
    if parsed.pseudo_classes:
        for pseudo, arg in parsed.pseudo_classes:
            if pseudo == "first-child" and _previous_element_sibling(node) is not None:
                return False
            if pseudo == "last-child" and _next_element_sibling(node) is not None:
                return False
            if pseudo == "nth-child" and not _matches_nth_child(node, arg):
                return False
            if pseudo == "not":
                if arg is None:
                    return False
                negated = _parse_simple_selector(arg)
                if negated is None or negated.pseudo_classes:
                    return False
                if _matches_simple_selector(node, arg):
                    return False
    return (
        parsed.tag is not None
        or parsed.id_name is not None
        or bool(parsed.classes)
        or bool(parsed.attributes)
        or bool(parsed.pseudo_classes)
    )


@lru_cache(maxsize=4096)
def _parse_selector_steps(selector: str) -> tuple[tuple[str, str], ...]:
    steps: list[tuple[str, str]] = []
    current = ""
    pending_combinator = " "
    in_whitespace = False
    bracket_depth = 0
    quote_char: str | None = None
    for char in selector.strip():
        if quote_char is not None:
            current += char
            if char == quote_char:
                quote_char = None
            continue
        if char in {'"', "'"}:
            current += char
            quote_char = char
            continue
        if char == "[":
            bracket_depth += 1
            current += char
            continue
        if char == "]":
            bracket_depth = max(bracket_depth - 1, 0)
            current += char
            continue
        if bracket_depth > 0:
            current += char
            continue
        if char == ">":
            if current.strip():
                steps.append((pending_combinator, current.strip()))
                current = ""
            pending_combinator = ">"
            in_whitespace = False
            continue
        if char in {"+", "~"}:
            if current.strip():
                steps.append((pending_combinator, current.strip()))
                current = ""
            pending_combinator = char
            in_whitespace = False
            continue
        if char.isspace():
            if current.strip():
                steps.append((pending_combinator, current.strip()))
                current = ""
            if pending_combinator not in {">", "+", "~"}:
                pending_combinator = " "
            in_whitespace = True
            continue
        if in_whitespace and pending_combinator not in {">", "+", "~"}:
            pending_combinator = " "
            in_whitespace = False
        current += char
    if current.strip():
        steps.append((pending_combinator, current.strip()))
    return tuple(steps)


@dataclass(frozen=True, slots=True)
class _SimpleSelector:
    tag: str | None
    id_name: str | None
    classes: tuple[str, ...]
    attributes: tuple[tuple[str, str, str | None], ...]
    pseudo_classes: tuple[tuple[str, str | None], ...]


@lru_cache(maxsize=4096)
def _parse_simple_selector(selector: str) -> _SimpleSelector | None:
    text = selector.strip()
    if not text:
        return None
    tag: str | None = None
    id_name: str | None = None
    classes: list[str] = []
    attributes: list[tuple[str, str, str | None]] = []
    pseudo_classes: list[tuple[str, str | None]] = []
    token = ""
    mode = "tag"
    index = 0
    while index < len(text):
        char = text[index]
        if char == "[":
            if token:
                if mode == "tag":
                    if tag is not None:
                        return None
                    tag = token.lower()
                elif mode == "id":
                    if id_name is not None:
                        return None
                    id_name = token
                else:
                    classes.append(token)
            token = ""
            end = _find_attribute_selector_end(text, index)
            if end is None:
                return None
            attribute = _parse_attribute_selector(text[index + 1 : end])
            if attribute is None:
                return None
            attributes.append(attribute)
            mode = "tag"
            index = end + 1
            continue
        if char == ":":
            if token:
                if mode == "tag":
                    if tag is not None:
                        return None
                    tag = token.lower()
                elif mode == "id":
                    if id_name is not None:
                        return None
                    id_name = token
                else:
                    classes.append(token)
            token = ""
            end = index + 1
            while end < len(text) and text[end] not in "#.:[(":
                end += 1
            pseudo = text[index + 1 : end].strip().lower()
            arg: str | None = None
            if end < len(text) and text[end] == "(":
                close = text.find(")", end)
                if close == -1:
                    return None
                arg = text[end + 1 : close].strip().lower()
                end = close + 1
            if pseudo == "not":
                if arg is None:
                    return None
                parsed_arg = _parse_simple_selector(arg)
                if parsed_arg is None or parsed_arg.pseudo_classes:
                    return None
            elif pseudo not in {"first-child", "last-child", "nth-child"}:
                return None
            pseudo_classes.append((pseudo, arg))
            mode = "tag"
            index = end
            continue
        if char in {"#", "."}:
            if token:
                if mode == "tag":
                    if tag is not None:
                        return None
                    tag = token.lower()
                elif mode == "id":
                    if id_name is not None:
                        return None
                    id_name = token
                else:
                    classes.append(token)
            token = ""
            mode = "id" if char == "#" else "class"
            index += 1
            continue
        token += char
        index += 1
    if token:
        if mode == "tag":
            if tag is not None:
                return None
            tag = token.lower()
        elif mode == "id":
            if id_name is not None:
                return None
            id_name = token
        else:
            classes.append(token)
    return _SimpleSelector(
        tag=tag,
        id_name=id_name,
        classes=tuple(classes),
        attributes=tuple(attributes),
        pseudo_classes=tuple(pseudo_classes),
    )


def _find_attribute_selector_end(text: str, start: int) -> int | None:
    quote_char: str | None = None
    for index in range(start + 1, len(text)):
        char = text[index]
        if quote_char is not None:
            if char == quote_char:
                quote_char = None
            continue
        if char in {'"', "'"}:
            quote_char = char
            continue
        if char == "]":
            return index
    return None


def _parse_attribute_selector(text: str) -> tuple[str, str, str | None] | None:
    content = text.strip()
    if not content:
        return None
    for operator in ("~=", "|=", "^=", "$=", "*=", "="):
        if operator in content:
            name, value = content.split(operator, 1)
            normalized_name = name.strip().lower()
            normalized_value = value.strip()
            if not normalized_name:
                return None
            if (
                len(normalized_value) >= 2
                and normalized_value[0] == normalized_value[-1]
                and normalized_value[0] in {'"', "'"}
            ):
                normalized_value = normalized_value[1:-1]
            return (normalized_name, operator, normalized_value)
    return (content.lower(), "exists", None)


def _matches_attribute(actual: str, operator: str, expected: str | None) -> bool:
    if operator == "exists":
        return True
    if expected is None:
        return False
    if operator == "=":
        return actual == expected
    if operator == "~=":
        return expected in actual.split()
    if operator == "|=":
        return actual == expected or actual.startswith(f"{expected}-")
    if operator == "^=":
        return actual.startswith(expected)
    if operator == "$=":
        return actual.endswith(expected)
    if operator == "*=":
        return expected in actual
    return False


def _previous_element_sibling(node: Element) -> Element | None:
    parent = node.parent
    if not isinstance(parent, (Document, Element)):
        return None
    previous: Element | None = None
    for child in parent.children:
        if child is node:
            return previous
        if isinstance(child, Element):
            previous = child
    return None


def _next_element_sibling(node: Element) -> Element | None:
    parent = node.parent
    if not isinstance(parent, (Document, Element)):
        return None
    seen = False
    for child in parent.children:
        if child is node:
            seen = True
            continue
        if seen and isinstance(child, Element):
            return child
    return None


def _matches_nth_child(node: Element, arg: str | None) -> bool:
    if arg is None:
        return False
    index = _element_child_index(node)
    if index is None:
        return False
    if arg == "odd":
        return index % 2 == 1
    if arg == "even":
        return index % 2 == 0
    try:
        return index == int(arg)
    except ValueError:
        return False


def _element_child_index(node: Element) -> int | None:
    parent = node.parent
    if not isinstance(parent, (Document, Element)):
        return None
    index = 0
    for child in parent.children:
        if isinstance(child, Element):
            index += 1
        if child is node:
            return index
    return None


def _text_content(node: Node) -> str:
    if isinstance(node, Text):
        return node.data
    children = getattr(node, "children", None)
    if not children:
        return ""
    return "".join(_text_content(child) for child in children)
