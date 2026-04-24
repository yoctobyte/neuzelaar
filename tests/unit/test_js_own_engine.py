from neuzelaar.core.policy.capability import Capability
from neuzelaar.engines.js.interface import ScriptExecutionRequest, ScriptExecutionStatus
from neuzelaar.engines.js.own_engine import OwnJavaScriptEngine
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture, DocumentNodeFixture


def test_own_engine_runs_supported_program() -> None:
    engine = OwnJavaScriptEngine()

    result = engine.execute(ScriptExecutionRequest(source="function add(a, b) { return a + b; } add(2, 3);"))

    assert result.status is ScriptExecutionStatus.RAN
    assert result.requested_capabilities == (Capability.EXEC_INLINE_JS,)


def test_own_engine_reports_reference_error() -> None:
    engine = OwnJavaScriptEngine()

    result = engine.execute(ScriptExecutionRequest(source="missing + 1;"))

    assert result.status is ScriptExecutionStatus.ERROR
    assert "ReferenceError:" in result.reason


def test_own_engine_reports_thrown_values() -> None:
    engine = OwnJavaScriptEngine()

    result = engine.execute(ScriptExecutionRequest(source='throw "boom";'))

    assert result.status is ScriptExecutionStatus.ERROR
    assert "Thrown:" in result.reason


def test_own_engine_can_run_against_fixture_driven_host_scenario() -> None:
    engine = OwnJavaScriptEngine(
        scenario_fixture=BrowserScenarioFixture(
            url="https://example.test/post/1",
            title="Post 1",
            history_entries=("/home", "/post/1"),
            history_index=1,
            nodes=(DocumentNodeFixture(id="headline", text_content="Post 1"),),
        )
    )

    result = engine.execute(
        ScriptExecutionRequest(
            source="console.log(document.title); document.getElementById('headline').textContent;",
        )
    )

    assert result.status is ScriptExecutionStatus.RAN
