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
