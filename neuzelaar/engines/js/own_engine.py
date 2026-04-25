"""Adapter from the standalone in-repo interpreter to JavaScriptEngine."""

from __future__ import annotations

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
    required_capability_for,
)
from neuzelaar.engines.js_own.errors import (
    JavaScriptExecutionLimitError,
    JavaScriptReferenceError,
    JavaScriptSyntaxError,
    JavaScriptThrownValue,
)
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture, build_browser_scenario
from neuzelaar.engines.js_own.interpreter import evaluate_program_with_config


class OwnJavaScriptEngine(JavaScriptEngine):
    name = "own"

    def __init__(
        self,
        *,
        scenario_fixture: BrowserScenarioFixture | None = None,
        runtime_config: ScriptRuntimeConfig | None = None,
    ) -> None:
        self.scenario_fixture = scenario_fixture
        self.runtime_config = runtime_config

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        try:
            environment = None
            if self.scenario_fixture is not None:
                environment, _stubs = build_browser_scenario(self.scenario_fixture)
            evaluate_program_with_config(
                request.source,
                environment,
                runtime_config=self.runtime_config,
            )
        except JavaScriptSyntaxError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"SyntaxError: {exc}",
                requested_capabilities=(required_capability_for(request),),
            )
        except JavaScriptExecutionLimitError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"ExecutionLimitError: {exc}",
                requested_capabilities=(required_capability_for(request),),
            )
        except JavaScriptReferenceError as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"ReferenceError: {exc}",
                requested_capabilities=(required_capability_for(request),),
            )
        except JavaScriptThrownValue as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"Thrown: {exc.value!r}",
                requested_capabilities=(required_capability_for(request),),
            )
        except Exception as exc:
            return ScriptExecutionResult(
                status=ScriptExecutionStatus.ERROR,
                reason=f"{type(exc).__name__}: {exc}",
                requested_capabilities=(required_capability_for(request),),
            )
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason="ok",
            requested_capabilities=(required_capability_for(request),),
        )
