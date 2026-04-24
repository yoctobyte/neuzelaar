"""JavaScript engine construction and discovery."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from neuzelaar.engines.js.interface import JavaScriptEngine
from neuzelaar.engines.js.noop import NoopJavaScriptEngine


@dataclass(frozen=True, slots=True)
class JavaScriptEngineSpec:
    name: str
    import_target: str | None
    description: str


class EngineUnavailableError(RuntimeError):
    """Raised when a configured JS engine backend cannot be created."""


_ENGINE_SPECS = {
    "noop": JavaScriptEngineSpec(
        name="noop",
        import_target=None,
        description="Policy-only engine that never executes JavaScript.",
    ),
    "quickjs": JavaScriptEngineSpec(
        name="quickjs",
        import_target="quickjs",
        description="QuickJS backend via the Python quickjs package.",
    ),
    "own": JavaScriptEngineSpec(
        name="own",
        import_target=None,
        description="In-repo standalone interpreter wrapped behind JavaScriptEngine.",
    ),
    "js2py": JavaScriptEngineSpec(
        name="js2py",
        import_target="js2py",
        description="Pure-Python Js2Py backend with mostly ES5.1 support.",
    ),
}


def engine_specs() -> tuple[JavaScriptEngineSpec, ...]:
    return tuple(_ENGINE_SPECS[name] for name in sorted(_ENGINE_SPECS))


def create_javascript_engine(name: str) -> JavaScriptEngine:
    normalized = name.strip().lower()
    if normalized == "noop":
        return NoopJavaScriptEngine()
    if normalized == "quickjs":
        try:
            engine_module = import_module("neuzelaar.engines.js.quickjs_engine")
            return engine_module.QuickJsJavaScriptEngine()
        except Exception as exc:
            raise EngineUnavailableError(f"{type(exc).__name__}: {exc}") from exc
    if normalized == "own":
        try:
            engine_module = import_module("neuzelaar.engines.js.own_engine")
            return engine_module.OwnJavaScriptEngine()
        except Exception as exc:
            raise EngineUnavailableError(f"{type(exc).__name__}: {exc}") from exc
    if normalized == "js2py":
        try:
            engine_module = import_module("neuzelaar.engines.js.js2py_engine")
            return engine_module.Js2PyJavaScriptEngine()
        except Exception as exc:
            raise EngineUnavailableError(f"{type(exc).__name__}: {exc}") from exc
    raise EngineUnavailableError(f"Unknown JavaScript engine: {name}")
