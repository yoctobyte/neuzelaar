"""Host boundary for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


HostCallableImpl = Callable[[tuple[object, ...], object | None], object]


@dataclass(slots=True)
class HostCallable:
    name: str
    impl: HostCallableImpl
    properties: dict[str, object] = field(default_factory=dict)

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        return self.impl(arguments, this_value)


@dataclass(slots=True)
class HostObject:
    properties: dict[str, object] = field(default_factory=dict)
    prototype: "HostObject | None" = None

    def get(self, name: str) -> object:
        if name in self.properties:
            return self.properties.get(name)
        if self.prototype is not None:
            return self.prototype.get(name)
        return None

    def set(self, name: str, value: object) -> object:
        self.properties[name] = value
        return value


@dataclass(slots=True)
class ConstructibleHostObject(HostObject):
    construct_impl: Callable[[tuple[object, ...]], object] | None = None

    def construct(self, arguments: tuple[object, ...]) -> object:
        if self.construct_impl is None:
            raise TypeError("Value is not a constructor")
        return self.construct_impl(arguments)
