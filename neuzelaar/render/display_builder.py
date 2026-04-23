"""Build display lists from minimal layout results."""

from __future__ import annotations

from neuzelaar.document.layout import LayoutImage, LayoutText, layout_document
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import Color, DisplayList, DrawText, FillRect, Placeholder, Rect


def build_display_list(document, *, width: int = 800, root_style: ComputedStyle | None = None) -> DisplayList:
    layout = layout_document(document, width=width)
    style = root_style or ComputedStyle()
    ops = [FillRect(Rect(0, 0, layout.width, layout.height), _parse_color(style.background_color))]
    text_color = _parse_color(style.color)
    for item in layout.items:
        if isinstance(item, LayoutText):
            ops.append(DrawText(item.x, item.y, item.text, text_color))
        elif isinstance(item, LayoutImage):
            ops.append(Placeholder(Rect(item.x, item.y, 240, 32), f"image: {item.label}"))
    return DisplayList(width=layout.width, height=layout.height, ops=tuple(ops))


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
