"""Build display lists from minimal layout results."""

from __future__ import annotations

from neuzelaar.document.layout import LayoutBox, LayoutImage, LayoutText, layout_document
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import Bitmap, Color, DisplayList, DrawImage, DrawText, FillRect, Placeholder, Rect


def build_display_list(
    document,
    *,
    width: int = 800,
    root_style: ComputedStyle | None = None,
    styles: dict | None = None,
    images: dict | None = None,
) -> DisplayList:
    layout = layout_document(document, width=width, styles=styles, images=images, root_style=root_style)
    style = root_style or ComputedStyle()
    ops = [FillRect(Rect(0, 0, layout.width, layout.height), _parse_color(style.background_color))]
    for item in layout.items:
        if isinstance(item, LayoutBox):
            ops.append(FillRect(Rect(item.x, item.y, item.width, item.height), _parse_color(item.color)))
        elif isinstance(item, LayoutText):
            ops.append(DrawText(item.x, item.y, item.text, _parse_color(item.color)))
        elif isinstance(item, LayoutImage):
            if item.bitmap is not None:
                ops.append(
                    DrawImage(
                        item.x,
                        item.y,
                        Bitmap(
                            width=item.bitmap.bitmap.width,
                            height=item.bitmap.bitmap.height,
                            stride=item.bitmap.bitmap.stride,
                            pixels=item.bitmap.bitmap.pixels,
                        ),
                    )
                )
            else:
                ops.append(Placeholder(Rect(item.x, item.y, item.width, item.height), f"image: {item.label}"))
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
