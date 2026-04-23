"""No-op JavaScript engine for M1."""

from __future__ import annotations

from neuzelaar.core.policy.capability import Capability
from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
)


class NoopJavaScriptEngine(JavaScriptEngine):
    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        capability = Capability.EXEC_INLINE_JS if request.inline else Capability.EXEC_SAMEORIGIN_JS
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.BLOCKED,
            reason="JavaScript execution is disabled in M1",
            requested_capabilities=(capability,),
        )
