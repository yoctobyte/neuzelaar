"""Synchronous command/event bus used by shells and core services."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar


MessageT = TypeVar("MessageT")
Handler = Callable[[Any], None]


@dataclass
class Bus:
    """Small synchronous pub/sub bus.

    This is intentionally simple for M1. It gives shells and services a shared
    contract without committing to async scheduling yet.
    """

    _handlers: dict[type[Any], list[Handler]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def subscribe(self, message_type: type[MessageT], handler: Callable[[MessageT], None]) -> None:
        self._handlers[message_type].append(handler)

    def publish(self, message: object) -> None:
        for cls in type(message).mro():
            for handler in self._handlers.get(cls, []):
                handler(message)
