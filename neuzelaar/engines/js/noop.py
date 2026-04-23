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
        if request.inline:
            capability = Capability.EXEC_INLINE_JS
        elif request.same_origin is False:
            capability = Capability.EXEC_THIRDPARTY_JS
        else:
            capability = Capability.EXEC_SAMEORIGIN_JS
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.BLOCKED,
            reason="JavaScript execution is disabled",
            requested_capabilities=(capability,),
        )
