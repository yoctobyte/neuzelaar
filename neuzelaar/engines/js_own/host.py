"""Host boundary for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from neuzelaar.engines.js_own.runtime import JS_UNDEFINED


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
    # Optional post-write hook the host can attach to bridge mutations
    # back to a real underlying object (e.g. write through to the page
    # DOM when JS does ``el.textContent = "x"``). Fires after the
    # properties dict is updated so the JS-visible value and the
    # bridged side-effect agree.
    on_set: Callable[[str, object], None] | None = None

    def get(self, name: str) -> object:
        if name in self.properties:
            return self.properties.get(name)
        if self.prototype is not None:
            return self.prototype.get(name)
        return JS_UNDEFINED

    def set(self, name: str, value: object) -> object:
        self.properties[name] = value
        if self.on_set is not None:
            self.on_set(name, value)
        return value


@dataclass(slots=True)
class ConstructibleHostObject(HostObject):
    construct_impl: Callable[[tuple[object, ...]], object] | None = None

    def construct(self, arguments: tuple[object, ...]) -> object:
        if self.construct_impl is None:
            raise TypeError("Value is not a constructor")
        return self.construct_impl(arguments)
