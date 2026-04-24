"""QuickJS-backed JavaScript engine."""

from __future__ import annotations

from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)

try:
    import quickjs as _quickjs
except ImportError:  # pragma: no cover - exercised through factory behavior
    _quickjs = None


class QuickJsJavaScriptEngine(JavaScriptEngine):
    name = "quickjs"

    def __init__(
        self,
        *,
        memory_limit_bytes: int | None = 8_000_000,
        time_limit_ms: int | None = 100,
        max_stack_size_bytes: int | None = 512_000,
    ) -> None:
        if _quickjs is None:
            raise RuntimeError("quickjs package is not installed")
        self.memory_limit_bytes = memory_limit_bytes
        self.time_limit_ms = time_limit_ms
        self.max_stack_size_bytes = max_stack_size_bytes

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        context = _quickjs.Context()
        if self.memory_limit_bytes is not None:
            context.set_memory_limit(self.memory_limit_bytes)
        if self.time_limit_ms is not None:
            context.set_time_limit(self.time_limit_ms)
        if self.max_stack_size_bytes is not None:
            context.set_max_stack_size(self.max_stack_size_bytes)
        try:
            context.eval(request.source)
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
