"""Pillow-backed software rasterizer."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from neuzelaar.render.display_list import Color, DisplayList, DrawImage, DrawText, FillRect, Placeholder
from neuzelaar.shell_api.frame import Frame, PixelFormat


def rasterize(display_list: DisplayList) -> Frame:
    image = Image.new("RGBA", (display_list.width, display_list.height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)

    for op in display_list.ops:
        if isinstance(op, FillRect):
            draw.rectangle(_rect_tuple(op.rect), fill=_color_tuple(op.color))
        elif isinstance(op, DrawText):
            font = _load_font(op.font_size)
            x = _aligned_text_x(op, font)
            draw.text((x, op.y), op.text, fill=_color_tuple(op.color), font=font)
        elif isinstance(op, DrawImage):
            bitmap = Image.frombytes("RGBA", (op.bitmap.width, op.bitmap.height), op.bitmap.pixels)
            image.alpha_composite(bitmap, (op.x, op.y))
        elif isinstance(op, Placeholder):
            draw.rectangle(_rect_tuple(op.rect), outline=(120, 120, 120, 255), fill=(245, 245, 245, 255))
            draw.text((op.rect.x + 6, op.rect.y + 9), op.label, fill=(60, 60, 60, 255), font=_load_font(16))

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


def _aligned_text_x(op: DrawText, font) -> int:
    if op.align == "left" or op.max_width <= 0:
        return op.x
    text_width = int(font.getlength(op.text))
    if op.align == "center":
        return op.x + max((op.max_width - text_width) // 2, 0)
    if op.align == "right":
        return op.x + max(op.max_width - text_width, 0)
    return op.x


@lru_cache(maxsize=16)
def _load_font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=max(size, 1))
    except OSError:
        return ImageFont.load_default()
