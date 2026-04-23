"""Safe handler selection for classified resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from neuzelaar.core.fetch.resource import Resource
from neuzelaar.core.handlers.download_handler import handle_download
from neuzelaar.core.handlers.html_handler import handle_html
from neuzelaar.core.handlers.image_handler import handle_image
from neuzelaar.core.handlers.text_handler import handle_text
from neuzelaar.core.mime.classifier import MimeDecision


HandlerFn = Callable[[Resource], Any]


@dataclass(frozen=True, slots=True)
class HandlerResult:
    kind: str
    value: Any


class HandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, HandlerFn] = {}

    def register(self, kind: str, handler: HandlerFn) -> None:
        self._handlers[kind] = handler

    def handle(self, resource: Resource, decision: MimeDecision) -> HandlerResult:
        if decision.kind not in self._handlers:
            return HandlerResult("unknown", "no safe handler available")
        value = self._handlers[decision.kind](resource)
        if decision.kind == "html":
            return HandlerResult("document", value)
        return HandlerResult(decision.kind, value)


def default_registry() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register("download", handle_download)
    registry.register("html", handle_html)
    registry.register("image", handle_image)
    registry.register("text", handle_text)
    return registry
