"""Runtime environment for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.engines.js_own.errors import JavaScriptReferenceError


@dataclass(slots=True)
class Environment:
    values: dict[str, object] = field(default_factory=dict)

    def get(self, name: str) -> object:
        if name not in self.values:
            raise JavaScriptReferenceError(f"{name} is not defined")
        return self.values[name]
