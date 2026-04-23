"""No-op WebAssembly engine for M1."""

from __future__ import annotations

from neuzelaar.core.policy.capability import Capability
from neuzelaar.engines.wasm.interface import (
    WasmEngine,
    WasmExecutionRequest,
    WasmExecutionResult,
    WasmExecutionStatus,
)


class NoopWasmEngine(WasmEngine):
    def execute(self, request: WasmExecutionRequest) -> WasmExecutionResult:
        return WasmExecutionResult(
            status=WasmExecutionStatus.BLOCKED,
            reason="WebAssembly execution is disabled in M1",
            requested_capabilities=(Capability.LOAD_WASM,),
        )
