"""Ticked variant of the standalone JS engine.

OwnJavaScriptEngine is drain-mode: every execute() runs the script's
sync code, drains microtasks, fires due timers, and exits. A
setTimeout(fn, 100) inside that script gets dropped on the floor when
the call returns, because the runtime state dies with it.

OwnTickedJavaScriptEngine keeps the state alive across calls.
``execute()`` runs only the script's sync code and microtasks; pending
timers stay in the runtime and fire when the host calls ``tick()``.
The host (e.g. the Tk shell) drives ``tick()`` from its UI clock so
timers fire on the host's schedule rather than blocking the page-load
critical path.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from neuzelaar.core.bus import Bus
from neuzelaar.engines.js.interface import (
    DomBridge,
    JavaScriptEngine,
    PageContext,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.errors import (
    JavaScriptExecutionLimitError,
    JavaScriptReferenceError,
    JavaScriptSyntaxError,
    JavaScriptThrownValue,
)
from neuzelaar.engines.js_own.execution import execution_budget
from neuzelaar.engines.js_own.host_scenarios import (
    BrowserScenarioFixture,
    DocumentNodeFixture,
    build_browser_scenario,
)
from neuzelaar.engines.js_own.interpreter import (
    create_global_environment,
    evaluate_program_with_config,
)
from neuzelaar.engines.js_own.runtime_state import (
    _CURRENT_RUNTIME_STATE,
    EventLoopSnapshot,
    ScriptRuntimeState,
)
from neuzelaar.engines.js_own.scheduler import ScriptScheduler
from neuzelaar.shell_api.events import ConsoleLog


class OwnTickedJavaScriptEngine(JavaScriptEngine):
    name = "own-ticked"

    def __init__(
        self,
        *,
        scenario_fixture: BrowserScenarioFixture | None = None,
        runtime_config: ScriptRuntimeConfig | None = None,
        bus: Bus | None = None,
    ) -> None:
        # ``scenario_fixture`` is the fallback used when the host
        # doesn't hand us a PageContext (e.g. direct test usage). On
        # real page loads the host calls reset_for_page(page_context)
        # and we rebuild the runtime from that instead.
        self.scenario_fixture = scenario_fixture
        self.runtime_config = runtime_config
        self.bus = bus
        self._environment: Environment | None = None
        self._state: ScriptRuntimeState | None = None
        self._scheduler: ScriptScheduler | None = None
        self._page_fixture: BrowserScenarioFixture | None = scenario_fixture
        self._dom_bridge: DomBridge | None = None

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        capability = required_capability_for(request)
        try:
            self._ensure_runtime()
            assert self._state is not None
            with self._enter_session():
                # The interpreter notices the existing state via the
                # contextvar and skips its own runtime_session. It also
                # skips the microtask drain in that branch, which is
                # exactly what we want for ticked execution: the host
                # drives drains via tick().
                with execution_budget(self.runtime_config):
                    evaluate_program_with_config(
                        request.source,
                        self._environment,
                        runtime_config=self.runtime_config,
                        scheduler=self._scheduler,
                    )
                # Drain microtasks now so promise .then chains attached
                # synchronously by the script run before we return —
                # matches drain-mode semantics for the script itself.
                # Pending timers stay parked for the next tick.
                self._state.drain_microtasks()
        except JavaScriptSyntaxError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"SyntaxError: {exc}",
                requested_capabilities=(capability,),
            )
        except JavaScriptExecutionLimitError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"ExecutionLimitError: {exc}",
                requested_capabilities=(capability,),
            )
        except JavaScriptReferenceError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"ReferenceError: {exc}",
                requested_capabilities=(capability,),
            )
        except JavaScriptThrownValue as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"Thrown: {exc.value!r}",
                requested_capabilities=(capability,),
            )
        except Exception as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"{type(exc).__name__}: {exc}",
                requested_capabilities=(capability,),
            )
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason="ok",
            requested_capabilities=(capability,),
        )

    def tick(self, *, timeout_ms: float = 8.0) -> None:
        if self._state is None:
            return
        with self._enter_session():
            with execution_budget(self.runtime_config):
                # until_idle=True so a tick can run several short tasks
                # if they all fit in the budget; the timeout caps total
                # wall time per tick so the UI thread never freezes.
                self._state.step(timeout_ms=timeout_ms, until_idle=True, max_tasks=None)

    def has_pending_work(self) -> bool:
        if self._state is None:
            return False
        return self._state.has_pending_work()

    def event_loop_snapshot(self) -> EventLoopSnapshot | None:
        if self._state is None:
            return None
        return self._state.snapshot()

    def reset_for_page(
        self,
        page_context: PageContext | None = None,
        *,
        dom_bridge: DomBridge | None = None,
    ) -> None:
        self._environment = None
        self._state = None
        self._scheduler = None
        self._dom_bridge = dom_bridge
        if page_context is not None:
            self._page_fixture = _fixture_from_page_context(page_context)
        else:
            # No context handed in: fall back to whatever the engine was
            # constructed with, which keeps direct-test usage working.
            self._page_fixture = self.scenario_fixture

    def _ensure_runtime(self) -> None:
        if self._state is not None:
            return
        fixture = self._page_fixture
        if fixture is not None:
            environment, stubs = build_browser_scenario(fixture)
            self._environment = environment
            self._scheduler = stubs.scheduler
            self._wire_console_sink(stubs)
            self._wire_dom_bridge(stubs)
        else:
            self._environment = create_global_environment()
            self._scheduler = None
        config = self.runtime_config or ScriptRuntimeConfig()
        scheduler = self._scheduler
        if scheduler is None and config.debug_track_tasks:
            scheduler = ScriptScheduler(config=config)
            self._scheduler = scheduler
        self._state = ScriptRuntimeState(config=config, scheduler=scheduler)

    def _wire_console_sink(self, stubs) -> None:
        if self.bus is None:
            return
        bus = self.bus

        def sink(level: str, text: str) -> None:
            bus.publish(ConsoleLog(level=level, text=text))

        stubs.console.sink = sink

    def _wire_dom_bridge(self, stubs) -> None:
        bridge = self._dom_bridge
        if bridge is None:
            return
        for node_id, host_object in stubs.document.nodes_by_id.items():
            # Inject the method bindings directly into properties so
            # they don't fire the on_set hook (which is for property
            # assignments only).
            host_object.properties["setAttribute"] = HostCallable(
                "setAttribute", _make_set_attribute(bridge, node_id, host_object)
            )
            host_object.properties["getAttribute"] = HostCallable(
                "getAttribute", _make_get_attribute(bridge, node_id)
            )
            host_object.properties["removeAttribute"] = HostCallable(
                "removeAttribute", _make_remove_attribute(bridge, node_id, host_object)
            )
            host_object.properties["insertAdjacentHTML"] = HostCallable(
                "insertAdjacentHTML", _make_insert_adjacent_html(bridge, node_id)
            )
            host_object.properties["remove"] = HostCallable(
                "remove", _make_remove_node(bridge, node_id)
            )
            style_object = _make_style_object(bridge, node_id, host_object)
            host_object.properties["style"] = style_object
            # Property writes (textContent, innerHTML, className, …)
            # route through the bridge so the page DOM stays in sync.
            host_object.on_set = lambda name, value, _id=node_id: bridge.set_property(
                _id, name, value
            )

    @contextmanager
    def _enter_session(self) -> Iterator[None]:
        assert self._state is not None
        token = _CURRENT_RUNTIME_STATE.set(self._state)
        try:
            yield
        finally:
            _CURRENT_RUNTIME_STATE.reset(token)


def _fixture_from_page_context(page_context: PageContext) -> BrowserScenarioFixture:
    nodes = []
    for node in page_context.nodes:
        attrs = dict(node.attributes)
        extras: dict[str, object] = {
            "tagName": node.tag.upper(),
            "id": node.id,
            "className": attrs.get("class", ""),
            "style": attrs.get("style", ""),
        }
        nodes.append(
            DocumentNodeFixture(
                id=node.id,
                text_content=node.text_content,
                extra_properties=extras,
            )
        )
    return BrowserScenarioFixture(
        url=page_context.url,
        title=page_context.title,
        nodes=tuple(nodes),
    )


def _make_set_attribute(bridge: DomBridge, node_id: str, host_object) -> "Callable":
    def impl(arguments, _this):
        if len(arguments) < 2:
            return None
        name = str(arguments[0])
        value = "" if arguments[1] is None else str(arguments[1])
        bridge.set_attribute(node_id, name, value)
        # Keep host-side mirror coherent for the common attr aliases
        # so subsequent reads of el.className / el.id reflect the
        # write without round-tripping through getAttribute.
        if name.lower() == "class":
            host_object.properties["className"] = value
        elif name.lower() == "id":
            host_object.properties["id"] = value
        elif name.lower() == "style":
            _sync_style_object(host_object, value)
        return None

    return impl


def _make_get_attribute(bridge: DomBridge, node_id: str) -> "Callable":
    def impl(arguments, _this):
        if not arguments:
            return None
        name = str(arguments[0])
        result = bridge.get_attribute(node_id, name)
        return result if result is not None else None

    return impl


def _make_remove_attribute(bridge: DomBridge, node_id: str, host_object) -> "Callable":
    def impl(arguments, _this):
        if not arguments:
            return None
        name = str(arguments[0])
        bridge.remove_attribute(node_id, name)
        if name.lower() == "class":
            host_object.properties["className"] = ""
        elif name.lower() == "id":
            host_object.properties["id"] = ""
        elif name.lower() == "style":
            _sync_style_object(host_object, "")
        return None

    return impl


def _make_insert_adjacent_html(bridge: DomBridge, node_id: str) -> "Callable":
    def impl(arguments, _this):
        if len(arguments) < 2:
            return None
        position = "" if arguments[0] is None else str(arguments[0])
        html = "" if arguments[1] is None else str(arguments[1])
        bridge.insert_adjacent_html(node_id, position, html)
        return None

    return impl


def _make_remove_node(bridge: DomBridge, node_id: str) -> "Callable":
    def impl(_arguments, _this):
        bridge.remove_node(node_id)
        return None

    return impl


def _make_style_object(bridge: DomBridge, node_id: str, host_object: HostObject) -> HostObject:
    style_object = HostObject(properties=_parse_style_properties(host_object))

    def on_set(name: str, value: object) -> None:
        bridge.set_style_property(node_id, name, value)

    style_object.on_set = on_set
    return style_object


def _sync_style_object(host_object: HostObject, value: object) -> None:
    style_object = host_object.properties.get("style")
    if isinstance(style_object, HostObject):
        style_object.properties.clear()
        style_object.properties.update(_parse_style_text("" if value is None else str(value)))


def _parse_style_properties(host_object: HostObject) -> dict[str, object]:
    raw_style = host_object.properties.get("style")
    return _parse_style_text("" if raw_style is None else str(raw_style))


def _parse_style_text(style_text: str) -> dict[str, object]:
    properties: dict[str, object] = {}
    for raw in style_text.split(";"):
        if ":" not in raw:
            continue
        name, value = raw.split(":", 1)
        js_name = _js_style_name(name.strip())
        if js_name:
            properties[js_name] = value.strip()
    return properties


def _js_style_name(css_name: str) -> str:
    parts = [part for part in css_name.lower().split("-") if part]
    if not parts:
        return ""
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])
