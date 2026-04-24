from neuzelaar.core.browser import BrowserState
from neuzelaar.core.session import BrowserSession
from neuzelaar.engines.js.factory import EngineUnavailableError, create_javascript_engine, engine_specs
from neuzelaar.engines.js.interface import (
    JavaScriptEngine,
    ScriptExecutionRequest,
    ScriptExecutionResult,
    ScriptExecutionStatus,
)
from neuzelaar.engines.js.noop import NoopJavaScriptEngine


class FakeEngine(JavaScriptEngine):
    name = "fake"

    def execute(self, request: ScriptExecutionRequest) -> ScriptExecutionResult:
        return ScriptExecutionResult(
            status=ScriptExecutionStatus.RAN,
            reason=request.source,
        )


def test_engine_specs_include_supported_backends() -> None:
    names = {spec.name for spec in engine_specs()}

    assert {"noop", "quickjs", "own", "js2py"} <= names


def test_factory_creates_noop_engine() -> None:
    engine = create_javascript_engine("noop")

    assert isinstance(engine, NoopJavaScriptEngine)


def test_factory_rejects_unknown_engine() -> None:
    try:
        create_javascript_engine("missing")
    except EngineUnavailableError as exc:
        assert "Unknown JavaScript engine" in str(exc)
    else:
        raise AssertionError("expected EngineUnavailableError")


def test_session_accepts_explicit_javascript_engine() -> None:
    session = BrowserSession(js_engine=FakeEngine())

    assert session.loader.js_engine.name == "fake"


def test_browser_state_uses_engine_factory_for_new_tabs() -> None:
    browser = BrowserState(js_engine_factory=FakeEngine)

    tab = browser.new_tab()

    assert tab.session.loader.js_engine.name == "fake"
