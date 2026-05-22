"""Tests for the QuickJS-ticked variant of the JS engine."""

from __future__ import annotations

import time
import pytest

from neuzelaar.core.bus import Bus
from neuzelaar.engines.js.interface import (
    PageContext,
    PageContextNode,
    ScriptExecutionRequest,
    ScriptExecutionStatus,
)
from neuzelaar.engines.js.quickjs_engine import QuickJsTickedJavaScriptEngine
from neuzelaar.shell_api.events import ConsoleLog

# Skip entire module if quickjs is not installed
quickjs = pytest.importorskip("quickjs")


def _make_engine() -> QuickJsTickedJavaScriptEngine:
    return QuickJsTickedJavaScriptEngine()


def test_ticked_engine_runs_sync_code_immediately() -> None:
    engine = _make_engine()
    bus = Bus()
    logs: list[ConsoleLog] = []
    bus.subscribe(ConsoleLog, logs.append)
    engine.bus = bus

    result = engine.execute(
        ScriptExecutionRequest(source="var x = 1 + 2; console.log(x);")
    )

    assert result.status is ScriptExecutionStatus.RAN
    assert engine.has_pending_work() is False
    assert len(logs) == 1
    assert logs[0].text == "3"


def test_settimeout_fires_on_subsequent_tick_not_inside_execute() -> None:
    engine = _make_engine()

    setup = engine.execute(
        ScriptExecutionRequest(
            source="var fired = false; setTimeout(function () { fired = true; }, 0);"
        )
    )

    assert setup.status is ScriptExecutionStatus.RAN
    assert engine.has_pending_work() is True

    # The callback must NOT have run inside execute — fired is still false.
    check_before = engine.execute(
        ScriptExecutionRequest(
            source='if (fired) throw new Error("timer fired too early");'
        )
    )
    assert check_before.status is ScriptExecutionStatus.RAN

    engine.tick(timeout_ms=50.0)

    # After the tick the global must be true.
    check_after = engine.execute(
        ScriptExecutionRequest(
            source='if (!fired) throw new Error("timer did not fire");'
        )
    )
    assert check_after.status is ScriptExecutionStatus.RAN, check_after.reason
    assert engine.has_pending_work() is False


def test_ticked_engine_preserves_globals_across_executes() -> None:
    engine = _make_engine()

    first = engine.execute(ScriptExecutionRequest(source="var counter = 1;"))
    second = engine.execute(ScriptExecutionRequest(source="counter += 5;"))

    assert first.status is ScriptExecutionStatus.RAN
    assert second.status is ScriptExecutionStatus.RAN


def test_setinterval_repeats_across_ticks() -> None:
    engine = _make_engine()

    engine.execute(
        ScriptExecutionRequest(
            source=(
                "var hits = 0;"
                "var id = setInterval(function () { hits = hits + 1; }, 0);"
            )
        )
    )

    assert engine.has_pending_work() is True

    engine.tick(timeout_ms=20.0)
    time.sleep(0.005)
    engine.tick(timeout_ms=20.0)

    # Cancel and confirm the queue eventually empties.
    engine.execute(ScriptExecutionRequest(source="clearInterval(id);"))
    engine.tick(timeout_ms=20.0)
    assert engine.has_pending_work() is False


def test_reset_for_page_drops_state_and_pending_timers() -> None:
    engine = _make_engine()

    engine.execute(
        ScriptExecutionRequest(
            source="setTimeout(function () {}, 1000);"
        )
    )
    assert engine.has_pending_work() is True

    engine.reset_for_page()

    assert engine.has_pending_work() is False
    # A fresh execute after reset works (rebuilds runtime).
    result = engine.execute(ScriptExecutionRequest(source="var y = 7;"))
    assert result.status is ScriptExecutionStatus.RAN


def test_tick_on_engine_with_no_state_is_safe() -> None:
    engine = _make_engine()

    engine.tick(timeout_ms=10.0)

    assert engine.has_pending_work() is False
    assert engine.event_loop_snapshot() is None


def test_ticked_engine_exposes_event_loop_snapshot() -> None:
    engine = _make_engine()

    engine.execute(
        ScriptExecutionRequest(
            source=(
                "queueMicrotask(function () {});"
                "setTimeout(function () {}, 1000);"
            )
        )
    )

    snapshot = engine.event_loop_snapshot()
    assert snapshot is not None
    assert snapshot == {"pending_timers": 1}


def test_reset_for_page_with_context_rebuilds_host_for_real_url_and_nodes() -> None:
    engine = _make_engine()
    bus = Bus()
    logs: list[ConsoleLog] = []
    bus.subscribe(ConsoleLog, logs.append)
    engine.bus = bus

    engine.reset_for_page(
        PageContext(
            url="https://example.test/articles/intro",
            title="Intro",
            nodes=(
                PageContextNode(id="headline", tag="h1", text_content="Hello"),
            ),
        )
    )

    result = engine.execute(
        ScriptExecutionRequest(
            source=(
                "console.log(location.href);"
                "console.log(document.title);"
                "console.log(document.getElementById('headline').textContent);"
            )
        )
    )

    assert result.status is ScriptExecutionStatus.RAN, result.reason
    assert [log.text for log in logs] == [
        "https://example.test/articles/intro",
        "Intro",
        "Hello",
    ]


def test_console_sink_routes_through_bus_for_log_warn_error() -> None:
    engine = _make_engine()
    bus = Bus()
    logs: list[ConsoleLog] = []
    bus.subscribe(ConsoleLog, logs.append)
    engine.bus = bus

    engine.reset_for_page()

    engine.execute(
        ScriptExecutionRequest(
            source=(
                'console.log("hi", 1);'
                'console.warn("careful");'
                'console.error("oops");'
            )
        )
    )

    assert [(log.level, log.text) for log in logs] == [
        ("info", "hi 1"),
        ("warning", "careful"),
        ("error", "oops"),
    ]
