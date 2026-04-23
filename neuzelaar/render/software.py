"""Pillow-backed software rasterizer."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from neuzelaar.render.display_list import Color, DisplayList, DrawText, FillRect, Placeholder
from neuzelaar.shell_api.frame import Frame, PixelFormat


def rasterize(display_list: DisplayList) -> Frame:
    image = Image.new("RGBA", (display_list.width, display_list.height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for op in display_list.ops:
        if isinstance(op, FillRect):
            draw.rectangle(_rect_tuple(op.rect), fill=_color_tuple(op.color))
        elif isinstance(op, DrawText):
            draw.text((op.x, op.y), op.text, fill=_color_tuple(op.color), font=font)
        elif isinstance(op, Placeholder):
            draw.rectangle(_rect_tuple(op.rect), outline=(120, 120, 120, 255), fill=(245, 245, 245, 255))
            draw.text((op.rect.x + 6, op.rect.y + 9), op.label, fill=(60, 60, 60, 255), font=font)

    pixels = image.tobytes("raw", "RGBA")
    return Frame(
        width=image.width,
        height=image.height,
        format=PixelFormat.RGBA8888,
        pixels=pixels,
        stride=image.width * 4,
    )


def _rect_tuple(rect) -> tuple[int, int, int, int]:
    return (rect.x, rect.y, rect.x + rect.width, rect.y + rect.height)


def _color_tuple(color: Color) -> tuple[int, int, int, int]:
    return (color.r, color.g, color.b, color.a)
