"""Minimal block text layout for early visual rendering."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.document.dom import Document, Element, Node, NodeId, Text
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.core.page import ImageAsset


@dataclass(frozen=True, slots=True)
class LayoutText:
    x: int
    y: int
    text: str
    color: str
    font_size: int


@dataclass(frozen=True, slots=True)
class LayoutImage:
    x: int
    y: int
    width: int
    height: int
    label: str
    bitmap: ImageAsset | None


@dataclass(frozen=True, slots=True)
class LayoutBox:
    x: int
    y: int
    width: int
    height: int
    color: str


LayoutItem = LayoutText | LayoutImage | LayoutBox


@dataclass(frozen=True, slots=True)
class LayoutResult:
    width: int
    height: int
    items: tuple[LayoutItem, ...]


def layout_document(
    document: Document,
    *,
    width: int = 800,
    styles: dict[NodeId, ComputedStyle] | None = None,
    images: dict[NodeId, ImageAsset] | None = None,
    root_style: ComputedStyle | None = None,
) -> LayoutResult:
    cursor_y = 16
    items: list[LayoutItem] = []
    base_style = root_style or ComputedStyle()
    if document.title:
        items.append(LayoutText(16, cursor_y, document.title, base_style.color, max(_font_size_px(base_style), 24)))
        cursor_y += 28
    cursor_y = _layout_node(
        document,
        items,
        x=16,
        y=cursor_y,
        content_width=max(width - 32, 120),
        styles=styles or {},
        images=images or {},
        inherited_style=base_style,
    )
    return LayoutResult(width=width, height=max(cursor_y + 16, 64), items=tuple(items))


def _layout_node(
    node: Node,
    items: list[LayoutItem],
    *,
    x: int,
    y: int,
    content_width: int,
    styles: dict[NodeId, ComputedStyle],
    images: dict[NodeId, ImageAsset],
    inherited_style: ComputedStyle,
) -> int:
    if isinstance(node, Text):
        text = " ".join(node.data.split())
        if text:
            items.append(LayoutText(x, y, text, inherited_style.color, _font_size_px(inherited_style)))
            return y + _line_height(inherited_style)
        return y

    if isinstance(node, Element):
        tag = node.tag.lower()
        style = _effective_style(node, styles, inherited_style)
        if style.display == "none":
            return y
        if tag in {"script", "style", "head", "title"}:
            return y
        margin = _size_px(style.margin)
        padding = _size_px(style.padding)
        if tag in {"body", "div", "section", "article", "p", "ul", "ol", "li"}:
            y += margin
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            text = _collect_text(node)
            if text:
                items.append(LayoutText(x, y, text, style.color, _font_size_px(style)))
                return y + _line_height(style) + margin
            return y
        if tag == "img":
            label = node.attr("alt") or node.attr("src") or "image"
            image_width, image_height = _image_dimensions(node, images.get(node.id))
            image = images.get(node.id)
            if image is not None:
                items.append(
                    LayoutImage(
                        x,
                        y,
                        image_width,
                        image_height,
                        label,
                        image,
                    )
                )
                return y + image_height + margin + 12
            items.append(LayoutImage(x, y, image_width, image_height, label, None))
            return y + image_height + margin + 12
        if tag == "li":
            text = _collect_text(node)
            if text:
                items.append(LayoutText(x, y, f"- {text}", style.color, _font_size_px(style)))
                return y + _line_height(style) + margin
            return y
        y += padding
        start_y = y
        insert_at = len(items)
        child_x = x + padding
        child_width = max(content_width - (padding * 2), 40)
        for child in node.children:
            y = _layout_node(
                child,
                items,
                x=child_x,
                y=y,
                content_width=child_width,
                styles=styles,
                images=images,
                inherited_style=style,
            )
        if (
            style.background_color != "#ffffff"
            and y > start_y
            and tag in {"body", "div", "section", "article", "p", "ul", "ol"}
        ):
            items.insert(
                insert_at,
                LayoutBox(
                    x=max(0, x),
                    y=max(0, start_y - padding),
                    width=max(content_width, 40),
                    height=max((y - start_y) + (padding * 2), 8),
                    color=style.background_color,
                ),
            )
        y += padding
        if tag in {"p", "div", "section", "ul", "ol", "article"}:
            y += 8
        y += margin
        return y

    children = getattr(node, "children", None)
    if not children:
        return y
    for child in children:
        y = _layout_node(
            child,
            items,
            x=x,
            y=y,
            content_width=content_width,
            styles=styles,
            images=images,
            inherited_style=inherited_style,
        )
    return y


def _collect_text(node: Node) -> str:
    if isinstance(node, Text):
        return " ".join(node.data.split())
    children = getattr(node, "children", None)
    if not children:
        return ""
    return " ".join(part for child in children if (part := _collect_text(child)))


def _effective_style(
    node: Element,
    styles: dict[NodeId, ComputedStyle],
    inherited_style: ComputedStyle,
) -> ComputedStyle:
    return styles.get(node.id, inherited_style)


def _line_height(style: ComputedStyle) -> int:
    return max(int(round(_font_size_px(style) * 1.3)), 10)


def _font_size_px(style: ComputedStyle) -> int:
    value = style.font_size.strip()
    if value.endswith("px"):
        try:
            return max(int(round(float(value[:-2]))), 1)
        except ValueError:
            pass
    return 16


def _size_px(value: str) -> int:
    token = value.strip().split()[0] if value.strip() else "0"
    if token.endswith("px"):
        token = token[:-2]
    try:
        return max(int(float(token)), 0)
    except ValueError:
        return 0


def _image_dimensions(node: Element, image: ImageAsset | None) -> tuple[int, int]:
    intrinsic_width = image.bitmap.width if image is not None else 240
    intrinsic_height = image.bitmap.height if image is not None else 32
    attr_width = _attr_px(node.attr("width"))
    attr_height = _attr_px(node.attr("height"))
    return (
        attr_width if attr_width is not None else intrinsic_width,
        attr_height if attr_height is not None else intrinsic_height,
    )


def _attr_px(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return max(int(value), 1)
    except ValueError:
        return None
