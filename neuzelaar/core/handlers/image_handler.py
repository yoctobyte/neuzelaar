"""Image placeholder handler.

Real image decoding is deferred until the visual rendering milestone.
"""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.fetch.resource import Resource
from neuzelaar.engines.image.pillow_adapter import ImageDecodeError, decode_image_info


@dataclass(frozen=True, slots=True)
class ImagePlaceholder:
    url: str
    size: int
    claimed_mime: str | None
    width: int | None = None
    height: int | None = None
    decode_error: str | None = None


def handle_image(resource: Resource) -> ImagePlaceholder:
    try:
        info = decode_image_info(resource.body)
    except ImageDecodeError as exc:
        return ImagePlaceholder(
            url=resource.final_url,
            size=len(resource.body),
            claimed_mime=resource.claimed_mime,
            decode_error=str(exc),
        )
    return ImagePlaceholder(
        url=resource.final_url,
        size=len(resource.body),
        claimed_mime=resource.claimed_mime,
        width=info.width,
        height=info.height,
    )
