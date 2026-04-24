"""Build display lists from minimal layout results."""

from __future__ import annotations

from neuzelaar.document.layout import LayoutBox, LayoutImage, LayoutText, layout_document
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import Bitmap, Color, DisplayList, DrawImage, DrawText, FillRect, Placeholder, Rect


def build_display_list(
    document,
    *,
    width: int = 800,
    zoom: float = 1.0,
    root_style: ComputedStyle | None = None,
    styles: dict | None = None,
    images: dict | None = None,
) -> DisplayList:
    if zoom <= 0:
        zoom = 1.0
    logical_width = max(int(round(width / zoom)), 120)
    layout = layout_document(
        document,
        width=logical_width,
        styles=styles,
        images=images,
        root_style=root_style,
    )

    def sx(value: int | float) -> int:
        return int(round(value * zoom))

    style = root_style or ComputedStyle()
    ops = [FillRect(Rect(0, 0, sx(layout.width), sx(layout.height)), _parse_color(style.background_color))]
    for item in layout.items:
        if isinstance(item, LayoutBox):
            ops.append(FillRect(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)), _parse_color(item.color)))
        elif isinstance(item, LayoutText):
            ops.append(
                DrawText(
                    sx(item.x),
                    sx(item.y),
                    item.text,
                    _parse_color(item.color),
                    sx(item.font_size),
                    max_width=sx(item.max_width),
                    align=item.text_align,
                )
            )
        elif isinstance(item, LayoutImage):
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
            else:
                ops.append(Placeholder(Rect(sx(item.x), sx(item.y), sx(item.width), sx(item.height)), f"image: {item.label}"))
    return DisplayList(width=sx(layout.width), height=sx(layout.height), ops=tuple(ops))


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
