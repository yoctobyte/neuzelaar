"""Plain-text resource handling."""

from __future__ import annotations

from neuzelaar.core.fetch.resource import Resource


def handle_text(resource: Resource) -> str:
    return resource.body.decode(resource.encoding or "utf-8", errors="replace")
