"""Js2Py-backed JavaScript engine."""

from __future__ import annotations

from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)

try:
    import js2py
except ImportError:  # pragma: no cover - exercised through factory behavior
    js2py = None


class Js2PyJavaScriptEngine(JavaScriptEngine):
    name = "js2py"

    def __init__(self) -> None:
        if js2py is None:
            raise RuntimeError("js2py package is not installed")

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        context = js2py.EvalJs({})
        try:
            context.execute(request.source)
        except Exception as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=str(exc),
                requested_capabilities=(required_capability_for(request),),
            )
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason="ok",
            requested_capabilities=(required_capability_for(request),),
        )
