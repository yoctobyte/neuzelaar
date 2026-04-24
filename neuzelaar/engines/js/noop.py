"""No-op JavaScript engine for M1."""

from __future__ import annotations

from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)


class NoopJavaScriptEngine(JavaScriptEngine):
    name = "noop"

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.BLOCKED,
            reason="JavaScript execution is disabled",
            requested_capabilities=(required_capability_for(request),),
        )
