"""Pillow image decoder adapter."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError


@dataclass(frozen=True, slots=True)
class DecodedImageInfo:
    width: int
    height: int
    mode: str
    format: str | None


@dataclass(frozen=True, slots=True)
class DecodedImageBitmap:
    width: int
    height: int
    stride: int
    pixels: bytes
    format: str | None


class ImageDecodeError(RuntimeError):
    """Raised when image bytes cannot be decoded."""


def decode_image_info(body: bytes) -> DecodedImageInfo:
    try:
        with Image.open(BytesIO(body)) as image:
            return DecodedImageInfo(
                width=image.width,
                height=image.height,
                mode=image.mode,
                format=image.format,
            )
    except UnidentifiedImageError as exc:
        raise ImageDecodeError("Unsupported or invalid image data") from exc


def decode_image_bitmap(body: bytes) -> DecodedImageBitmap:
    try:
        with Image.open(BytesIO(body)) as image:
            rgba = image.convert("RGBA")
            pixels = rgba.tobytes("raw", "RGBA")
            return DecodedImageBitmap(
                width=rgba.width,
                height=rgba.height,
                stride=rgba.width * 4,
                pixels=pixels,
                format=image.format,
            )
    except UnidentifiedImageError as exc:
        raise ImageDecodeError("Unsupported or invalid image data") from exc
