"""Font metric adapter backed by Pillow."""

from __future__ import annotations

from functools import lru_cache

from PIL import ImageFont


def measure_text(text: str, *, size: int, weight: str = "normal", style: str = "normal") -> int:
    if not text:
        return 0
    font = _load_font(size, weight, style)
    try:
        return int(round(font.getlength(text)))
    except AttributeError:
        bbox = font.getbbox(text)
        return max(int(round(bbox[2] - bbox[0])), 0)


@lru_cache(maxsize=32)
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
