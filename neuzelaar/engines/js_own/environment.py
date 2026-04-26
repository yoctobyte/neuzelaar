"""Runtime environment for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.engines.js_own.errors import JavaScriptReferenceError, JavaScriptSyntaxError


@dataclass(slots=True)
class Binding:
    value: object
    kind: str
    initialized: bool = True


@dataclass(slots=True)
class Environment:
    values: dict[str, Binding] = field(default_factory=dict)
    parent: "Environment | None" = None
    var_scope: "Environment | None" = None

    def __post_init__(self) -> None:
        self.values = {
            name: value if isinstance(value, Binding) else Binding(value=value, kind="var")
            for name, value in self.values.items()
        }
        if self.var_scope is None:
            self.var_scope = self if self.parent is None else self.parent.var_scope

    def child_block(self) -> "Environment":
        return Environment(parent=self, var_scope=self.var_scope)

    def get(self, name: str) -> object:
        binding = self._lookup_binding(name)
        if binding is None:
            raise JavaScriptReferenceError(f"{name} is not defined")
        return binding.value

    def declare(self, name: str, value: object, *, kind: str) -> object:
        target = self.var_scope if kind == "var" else self
        assert target is not None
        if kind in ("let", "const") and name in target.values:
            raise JavaScriptSyntaxError(
                f"Identifier {name!r} has already been declared"
            )
        if kind == "var" and name in target.values:
            target.values[name].value = value
            return value
        target.values[name] = Binding(value=value, kind=kind)
        return value

    def assign(self, name: str, value: object) -> object:
        owner = self._lookup_owner(name)
        if owner is None:
            raise JavaScriptReferenceError(f"{name} is not defined")
        binding = owner.values[name]
        if binding.kind == "const":
            raise TypeError(f"Assignment to constant variable: {name}")
        binding.value = value
        return value

    def _lookup_binding(self, name: str) -> Binding | None:
        owner = self._lookup_owner(name)
        if owner is None:
            return None
        return owner.values[name]

    def _lookup_owner(self, name: str) -> "Environment | None":
        env: Environment | None = self
        while env is not None:
            if name in env.values:
                return env
            env = env.parent
        return None
