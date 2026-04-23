"""Image placeholder handler.

Real image decoding is deferred until the visual rendering milestone.
"""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.fetch.resource import Resource


@dataclass(frozen=True, slots=True)
class ImagePlaceholder:
    url: str
    size: int
    claimed_mime: str | None


def handle_image(resource: Resource) -> ImagePlaceholder:
    return ImagePlaceholder(
        url=resource.final_url,
        size=len(resource.body),
        claimed_mime=resource.claimed_mime,
    )
