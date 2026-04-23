"""WebAssembly engine contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neuzelaar.core.policy.capability import Capability


class WasmExecutionStatus(Enum):
    BLOCKED = "blocked"
    RAN = "ran"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WasmExecutionRequest:
    module: bytes
    url: str | None = None


@dataclass(frozen=True, slots=True)
class WasmExecutionResult:
    status: WasmExecutionStatus
    reason: str
    requested_capabilities: tuple[Capability, ...] = ()


class WasmEngine:
    def execute(self, request: WasmExecutionRequest) -> WasmExecutionResult:
        raise NotImplementedError
