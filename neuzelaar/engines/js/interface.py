"""JavaScript engine contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

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
    """Snapshot of an id-bearing DOM element handed to the engine.

    Engines that expose a host ``document`` build host-side wrappers
    from these. Writes to the wrappers route through DomBridge below
    so the underlying page DOM stays in sync.
    """

    id: str
    tag: str
    text_content: str
    attributes: tuple[tuple[str, str], ...] = ()  # ((name, value), …)


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


@dataclass
class DomBridge:
    """Operations the engine calls to mutate the underlying page DOM.

    The host (PageLoader) builds an instance with closures over the
    real Element objects; the engine wires them into host-object
    setters and method bindings. All mutations are expected to publish
    DomMutated on the bus so shells can repaint.
    """

    set_property: Callable[[str, str, object], None] = field(
        default=lambda node_id, name, value: None
    )
    get_attribute: Callable[[str, str], "str | None"] = field(
        default=lambda node_id, name: None
    )
    set_attribute: Callable[[str, str, str], None] = field(
        default=lambda node_id, name, value: None
    )
    remove_attribute: Callable[[str, str], None] = field(
        default=lambda node_id, name: None
    )
    set_style_property: Callable[[str, str, object], None] = field(
        default=lambda node_id, name, value: None
    )
    insert_adjacent_html: Callable[[str, str, str], None] = field(
        default=lambda node_id, position, html: None
    )
    remove_node: Callable[[str], None] = field(default=lambda node_id: None)


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

    def event_loop_snapshot(self) -> object | None:
        """Structured debug view of pending JS event-loop work, if any."""
        return None

    def reset_for_page(
        self,
        page_context: PageContext | None = None,
        *,
        dom_bridge: DomBridge | None = None,
    ) -> None:
        """Drop any per-page state (timers, intervals, globals).

        Called by the host on navigation so the new page starts with a
        fresh runtime. ``page_context`` carries the new page's URL,
        title, and id-bearing nodes. ``dom_bridge`` exposes the writes
        the engine should route back to the page DOM (textContent,
        innerHTML, className, getAttribute / setAttribute / style
        declarations / …). No-op for engines with no persistent state.
        """
        return
