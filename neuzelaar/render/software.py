"""Pillow-backed software rasterizer."""

from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from neuzelaar.render.display_list import (
    Color,
    DisplayList,
    DrawImage,
    DrawText,
    FillRect,
    Placeholder,
    PopClip,
    PushClip,
    Rect,
)
from neuzelaar.shell_api.frame import Frame, PixelFormat
from neuzelaar.core.watchdog import check_resources


# Safety cap: prevent X11 BadAlloc by limiting the rasterized bitmap.
# At 800px wide × 16384px tall × 4 bytes/pixel = ~50 MB — well within
# X server limits on any reasonable system.
MAX_RASTER_HEIGHT = 16_384
MAX_RASTER_PIXELS = 800 * MAX_RASTER_HEIGHT  # ~52 million pixels


def rasterize(display_list: DisplayList) -> Frame:
    check_resources()
    clamped_height = min(display_list.height, MAX_RASTER_HEIGHT)
    clamped_height = max(clamped_height, 1)
    image = Image.new("RGBA", (display_list.width, clamped_height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Active clip stack: each entry is the intersection of all clips
    # pushed so far. None means "no clip"; a Rect means subsequent ops
    # whose bounding box is fully outside are skipped.
    clip_stack: list[Rect | None] = [None]

    def active_clip() -> Rect | None:
        return clip_stack[-1]

    def fully_outside(item_x: int, item_y: int, item_w: int, item_h: int) -> bool:
        clip = active_clip()
        if clip is None:
            return False
        if item_y + item_h <= clip.y or item_y >= clip.y + clip.height:
            return True
        if item_x + item_w <= clip.x or item_x >= clip.x + clip.width:
            return True
        return False

    for op in display_list.ops:
        if isinstance(op, PushClip):
            existing = active_clip()
            new_clip = op.rect
            if existing is not None:
                # Intersect with existing clip.
                left = max(existing.x, new_clip.x)
                top = max(existing.y, new_clip.y)
                right = min(existing.x + existing.width, new_clip.x + new_clip.width)
                bottom = min(existing.y + existing.height, new_clip.y + new_clip.height)
                if right <= left or bottom <= top:
                    new_clip = Rect(left, top, 0, 0)
                else:
                    new_clip = Rect(left, top, right - left, bottom - top)
            clip_stack.append(new_clip)
            continue
        if isinstance(op, PopClip):
            if len(clip_stack) > 1:
                clip_stack.pop()
            continue

        if isinstance(op, FillRect):
            if op.rect.y >= clamped_height:
                continue
            if fully_outside(op.rect.x, op.rect.y, op.rect.width, op.rect.height):
                continue
            draw.rectangle(_rect_tuple(op.rect), fill=_color_tuple(op.color))
        elif isinstance(op, DrawText):
            if op.y >= clamped_height:
                continue
            font = _load_font(op.font_size, op.font_weight, op.font_style)
            x = _aligned_text_x(op, font)
            est_w = max(op.max_width or len(op.text) * op.font_size, op.font_size)
            if fully_outside(x, op.y, est_w, op.font_size + 4):
                continue
            draw.text((x, op.y), op.text, fill=_color_tuple(op.color), font=font)
            _draw_text_decoration(draw, op, x, font)
        elif isinstance(op, DrawImage):
            if op.y >= clamped_height:
                continue
            if fully_outside(op.x, op.y, op.bitmap.width, op.bitmap.height):
                continue
            bitmap = Image.frombytes("RGBA", (op.bitmap.width, op.bitmap.height), op.bitmap.pixels)
            image.alpha_composite(bitmap, (op.x, op.y))
        elif isinstance(op, Placeholder):
            if op.rect.y >= clamped_height:
                continue
            if fully_outside(op.rect.x, op.rect.y, op.rect.width, op.rect.height):
                continue
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


def _draw_text_decoration(draw, op: DrawText, x: int, font) -> None:
    decoration = op.text_decoration.strip().lower()
    if decoration == "none" or not decoration:
        return
    text_width = int(round(font.getlength(op.text)))
    color = _color_tuple(op.color)
    if "underline" in decoration:
        y = op.y + max(int(round(op.font_size * 1.05)), op.font_size)
        draw.line((x, y, x + text_width, y), fill=color, width=max(op.font_size // 14, 1))
    if "line-through" in decoration:
        y = op.y + max(int(round(op.font_size * 0.55)), 1)
        draw.line((x, y, x + text_width, y), fill=color, width=max(op.font_size // 14, 1))


@lru_cache(maxsize=16)
def _load_font(size: int, weight: str = "normal", style: str = "normal"):
    filename = _font_filename(weight, style)
    try:
        return ImageFont.truetype(filename, size=max(size, 1))
    except OSError:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size=max(size, 1))
        except OSError:
            return ImageFont.load_default()


def _font_filename(weight: str, style: str) -> str:
    normalized_weight = weight.strip().lower()
    normalized_style = style.strip().lower()
    is_bold = normalized_weight == "bold" or normalized_weight.isdigit() and int(normalized_weight) >= 600
    is_italic = normalized_style in {"italic", "oblique"}
    if is_bold and is_italic:
        return "DejaVuSans-BoldOblique.ttf"
    if is_bold:
        return "DejaVuSans-Bold.ttf"
    if is_italic:
        return "DejaVuSans-Oblique.ttf"
    return "DejaVuSans.ttf"
