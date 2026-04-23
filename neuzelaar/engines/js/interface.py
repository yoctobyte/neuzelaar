"""JavaScript engine contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neuzelaar.core.policy.capability import Capability


class ScriptExecutionStatus(Enum):
    BLOCKED = "blocked"
    RAN = "ran"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScriptExecutionRequest:
    source: str
    url: str | None = None
    inline: bool = True


@dataclass(frozen=True, slots=True)
class ScriptExecutionResult:
    status: ScriptExecutionStatus
    reason: str
    requested_capabilities: tuple[Capability, ...] = ()


class JavaScriptEngine:
    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        raise NotImplementedError
