"""Build display lists from minimal layout results."""

from __future__ import annotations

from dataclasses import replace

from neuzelaar.document.bfc import measure_text_width
from neuzelaar.document.dom import Element, walk
from neuzelaar.document.layout import (
    LayoutBox,
    LayoutClipPop,
    LayoutClipPush,
    LayoutImage,
    LayoutText,
    layout_document,
)
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import (
    Bitmap,
    Color,
    DisplayList,
    DrawImage,
    DrawText,
    FillRect,
    HitRegion,
    Placeholder,
    PopClip,
    PushClip,
    Rect,
)


def build_display_list(
    document,
    *,
    width: int = 800,
    height: int = 600,
    zoom: float = 1.0,
    root_style: ComputedStyle | None = None,
    styles: dict | None = None,
    images: dict | None = None,
    frames: dict | None = None,
) -> DisplayList:
    if zoom <= 0:
        zoom = 1.0
    logical_width = max(int(round(width / zoom)), 120)
    logical_height = max(int(round(height / zoom)), 120)
    layout = layout_document(
        document,
        width=logical_width,
        height=logical_height,
        styles=styles,
        images=images,
        root_style=root_style,
        frames=frames,
    )

    def sx(value: int | float) -> int:
        return int(round(value * zoom))

    style = root_style or ComputedStyle()
    ops = [FillRect(Rect(0, 0, sx(layout.width), sx(layout.height)), _parse_color(style.background_color))]
    hit_regions: list[HitRegion] = []
    elements = {
        node.id: node
        for node in walk(document)
        if isinstance(node, Element)
    }

    def interactive_kind(node_id) -> str | None:
        node = elements.get(node_id)
        if node is None:
            return None
        tag = node.tag.lower()
        if tag == "a" and node.attr("href"):
            return "link"
        if tag in {"input", "textarea", "select", "button"}:
            input_type = (node.attr("type") or "text").lower()
            if tag == "button" or input_type in {"submit", "button"}:
                return "submit"
            return "form-control"
        return None

    for item in layout.items:
        if isinstance(item, LayoutBox):
            ops.append(FillRect(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)), _parse_color(item.color)))
        elif isinstance(item, LayoutText):
            kind = interactive_kind(item.node_id)
            if kind is not None:
                hit_regions.append(
                    HitRegion(
                        Rect(sx(item.x), sx(item.y), max(sx(_text_width(item)), 1), sx(item.font_size + 6)),
                        kind,
                        str(item.node_id),
                    )
                )
            ops.append(
                DrawText(
                    sx(item.x),
                    sx(item.y),
                    item.text,
                    _parse_color(item.color),
                    sx(item.font_size),
                    font_weight=item.font_weight,
                    font_style=item.font_style,
                    text_decoration=item.text_decoration,
                )
            )
        elif isinstance(item, LayoutImage):
            kind = interactive_kind(item.node_id)
            if kind is not None:
                hit_regions.append(
                    HitRegion(
                        Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)),
                        kind,
                        str(item.node_id),
                    )
                )
            if item.bitmap is not None:
                ops.append(
                    DrawImage(
                        sx(item.x),
                        sx(item.y),
                        Bitmap(
                            width=item.bitmap.bitmap.width,
                            height=item.bitmap.bitmap.height,
                            stride=item.bitmap.bitmap.stride,
                            pixels=item.bitmap.bitmap.pixels,
                        ),
                    )
                )
            elif kind is not None:
                ops.append(Placeholder(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)), item.label))
            else:
                # The label is already the box's own description —
                # "image: logo.png", "iframe: child.html". Layout knows
                # what kind of box it is; the builder does not.
                ops.append(Placeholder(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)), item.label))
        elif isinstance(item, LayoutClipPush):
            ops.append(PushClip(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height))))
        elif isinstance(item, LayoutClipPop):
            ops.append(PopClip())
    return DisplayList(width=sx(layout.width), height=sx(layout.height), ops=tuple(ops), hit_regions=tuple(hit_regions))


def _text_width(item: LayoutText) -> int:
    style = replace(
        ComputedStyle(),
        font_size=f"{item.font_size}px",
        font_weight=item.font_weight,
        font_style=item.font_style,
    )
    return measure_text_width(item.text, style)


def _parse_color(value: str) -> Color:
    named = {
        "black": Color(0, 0, 0),
        "blue": Color(0, 0, 180),
        "green": Color(0, 120, 0),
        "red": Color(180, 0, 0),
        "white": Color(255, 255, 255),
    }
    normalized = value.strip().lower()
    if normalized in named:
        return named[normalized]
    if normalized.startswith("#") and len(normalized) == 7:
        try:
            return Color(
                int(normalized[1:3], 16),
                int(normalized[3:5], 16),
                int(normalized[5:7], 16),
            )
        except ValueError:
            return Color(20, 20, 20)
    return Color(20, 20, 20)
