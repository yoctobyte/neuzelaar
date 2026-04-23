"""Safe handler selection for classified resources."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from neuzelaar.core.fetch.resource import Resource
from neuzelaar.core.handlers.html_handler import handle_html
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
        if decision.kind == "html":
            return HandlerResult("document", self._handlers["html"](resource))
        if decision.kind == "text":
            return HandlerResult("text", self._handlers["text"](resource))
        if decision.kind == "image":
            return HandlerResult("placeholder", "image resource recognized; decoding deferred")
        if decision.kind == "download":
            return HandlerResult("download", "resource treated as download")
        return HandlerResult("unknown", "no safe handler available")


def default_registry() -> HandlerRegistry:
    registry = HandlerRegistry()
    registry.register("html", handle_html)
    registry.register("text", handle_text)
    return registry
