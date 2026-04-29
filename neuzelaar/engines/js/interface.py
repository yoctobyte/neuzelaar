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


@dataclass(frozen=True, slots=True)
class PageContextNode:
    """Read-only snapshot of an id-bearing DOM element.

    Engines that expose a host ``document`` build host-side wrappers
    from these. Mutations to the wrappers do not propagate back to the
    underlying page DOM in V1; that bridge is deferred.
    """

    id: str
    tag: str
    text_content: str


@dataclass(frozen=True, slots=True)
class PageContext:
    """Page-scoped data the host hands to the engine on navigation.

    Lets the engine tailor its global object to the actual page (real
    URL, real title, real id-bearing elements) instead of a static
    fixture origin.
    """

    url: str
    title: str = ""
    nodes: tuple[PageContextNode, ...] = ()


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

    def tick(self, *, timeout_ms: float = 8.0) -> None:
        """Advance any pending microtasks and due timers for up to ``timeout_ms``.

        Default is a no-op: drain-mode engines run scripts to completion
        inside ``execute`` and have nothing left to drive. Ticked engines
        override this so the host can fire setTimeout/setInterval
        callbacks on its own clock.
        """
        return

    def has_pending_work(self) -> bool:
        """True if a future call to ``tick`` would do something useful."""
        return False

    def reset_for_page(self, page_context: PageContext | None = None) -> None:
        """Drop any per-page state (timers, intervals, globals).

        Called by the host on navigation so the new page starts with a
        fresh runtime. ``page_context`` carries the new page's URL,
        title, and id-bearing nodes; engines that expose a host
        ``document`` rebuild their host objects from it. No-op for
        engines with no persistent state.
        """
        return
