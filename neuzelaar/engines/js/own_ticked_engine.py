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
    JavaScriptEngine,
    PageContext,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
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
        self._mutation_handler = None

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

    def reset_for_page(
        self,
        page_context: PageContext | None = None,
        *,
        mutation_handler=None,
    ) -> None:
        self._environment = None
        self._state = None
        self._scheduler = None
        self._mutation_handler = mutation_handler
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
            self._wire_mutation_handler(stubs)
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

    def _wire_mutation_handler(self, stubs) -> None:
        handler = self._mutation_handler
        if handler is None:
            return
        for node_id, host_object in stubs.document.nodes_by_id.items():
            # Capture node_id so each hook reports its own id back.
            host_object.on_set = lambda name, value, _id=node_id: handler(
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
    nodes = tuple(
        DocumentNodeFixture(
            id=node.id,
            text_content=node.text_content,
            extra_properties={"tagName": node.tag.upper()},
        )
        for node in page_context.nodes
    )
    return BrowserScenarioFixture(
        url=page_context.url,
        title=page_context.title,
        nodes=nodes,
    )
