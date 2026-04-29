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

from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
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


class OwnTickedJavaScriptEngine(JavaScriptEngine):
    name = "own-ticked"

    def __init__(
        self,
        *,
        scenario_fixture: BrowserScenarioFixture | None = None,
        runtime_config: ScriptRuntimeConfig | None = None,
    ) -> None:
        self.scenario_fixture = scenario_fixture
        self.runtime_config = runtime_config
        self._environment: Environment | None = None
        self._state: ScriptRuntimeState | None = None
        self._scheduler: ScriptScheduler | None = None

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

    def reset_for_page(self) -> None:
        self._environment = None
        self._state = None
        self._scheduler = None

    def _ensure_runtime(self) -> None:
        if self._state is not None:
            return
        if self.scenario_fixture is not None:
            environment, stubs = build_browser_scenario(self.scenario_fixture)
            self._environment = environment
            self._scheduler = stubs.scheduler
        else:
            self._environment = create_global_environment()
            self._scheduler = None
        config = self.runtime_config or ScriptRuntimeConfig()
        scheduler = self._scheduler
        if scheduler is None and config.debug_track_tasks:
            scheduler = ScriptScheduler(config=config)
            self._scheduler = scheduler
        self._state = ScriptRuntimeState(config=config, scheduler=scheduler)

    @contextmanager
    def _enter_session(self) -> Iterator[None]:
        assert self._state is not None
        token = _CURRENT_RUNTIME_STATE.set(self._state)
        try:
            yield
        finally:
            _CURRENT_RUNTIME_STATE.reset(token)
