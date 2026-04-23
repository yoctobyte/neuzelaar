"""Build display lists from minimal layout results."""

from __future__ import annotations

from neuzelaar.document.layout import LayoutImage, LayoutText, layout_document
from neuzelaar.render.display_list import Color, DisplayList, DrawText, FillRect, Placeholder, Rect


def build_display_list(document, *, width: int = 800) -> DisplayList:
    layout = layout_document(document, width=width)
    ops = [FillRect(Rect(0, 0, layout.width, layout.height), Color(255, 255, 255))]
    for item in layout.items:
        if isinstance(item, LayoutText):
            ops.append(DrawText(item.x, item.y, item.text, Color(20, 20, 20)))
        elif isinstance(item, LayoutImage):
            ops.append(Placeholder(Rect(item.x, item.y, 240, 32), f"image: {item.label}"))
    return DisplayList(width=layout.width, height=layout.height, ops=tuple(ops))
