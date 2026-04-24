"""JavaScript engine contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from neuzelaar.core.policy.capability import Capability
from neuzelaar.document.dom import NodeId


class ScriptExecutionStatus(Enum):
    BLOCKED = "blocked"
    RAN = "ran"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScriptExecutionRequest:
    source: str
    url: str | None = None
    inline: bool = True
    same_origin: bool | None = None
    node_id: NodeId | None = None


@dataclass(frozen=True, slots=True)
class ScriptExecutionResult:
    status: ScriptExecutionStatus
    reason: str
    requested_capabilities: tuple[Capability, ...] = ()


def required_capability_for(request: ScriptExecutionRequest) -> Capability:
    """The capability a script needs to execute, derived purely from its shape.

    Kept outside JavaScriptEngine.execute() so the pipeline can check
    permissions before asking the engine to run anything. All engines must
    agree on this mapping; only the mapping of (inline, same_origin) to
    capability matters, not engine internals.
    """
    if request.inline:
        return Capability.EXEC_INLINE_JS
    if request.same_origin is False:
        return Capability.EXEC_THIRDPARTY_JS
    return Capability.EXEC_SAMEORIGIN_JS


class JavaScriptEngine:
    name = "unknown"

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        raise NotImplementedError

    def evaluate_program(
        self,
        source: str,
        *,
        url: str | None = None,
    ) -> ScriptExecutionResult:
        return self.execute(
            ScriptExecutionRequest(
                source=source,
                url=url,
                inline=url is None,
                same_origin=None,
                node_id=None,
            )
        )
