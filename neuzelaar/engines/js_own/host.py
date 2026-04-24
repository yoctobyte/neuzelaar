"""Host boundary for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


HostCallableImpl = Callable[[tuple[object, ...], object | None], object]


@dataclass(slots=True)
class HostCallable:
    name: str
    impl: HostCallableImpl

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        return self.impl(arguments, this_value)


@dataclass(slots=True)
class HostObject:
    properties: dict[str, object] = field(default_factory=dict)

    def get(self, name: str) -> object:
        return self.properties.get(name)

    def set(self, name: str, value: object) -> object:
        self.properties[name] = value
        return value
