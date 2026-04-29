"""Tests for the ticked variant of the standalone JS engine."""

from __future__ import annotations

import time

from neuzelaar.engines.js.interface import ScriptExecutionRequest, ScriptExecutionStatus
from neuzelaar.engines.js.own_ticked_engine import OwnTickedJavaScriptEngine
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture


def _make_engine() -> OwnTickedJavaScriptEngine:
    # The fixture installs the host stubs we need (console, setTimeout,
    # …); without it the engine's plain global env has no setTimeout.
    return OwnTickedJavaScriptEngine(scenario_fixture=BrowserScenarioFixture())


def test_ticked_engine_runs_sync_code_immediately() -> None:
    engine = _make_engine()

    result = engine.execute(
        ScriptExecutionRequest(source="var x = 1 + 2; console.log(x);")
    )

    assert result.status is ScriptExecutionStatus.RAN
    assert engine.has_pending_work() is False


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
            source='if (fired) throw "timer fired too early";'
        )
    )
    assert check_before.status is ScriptExecutionStatus.RAN

    engine.tick(timeout_ms=50.0)

    # After the tick the global must be true. If it isn't, the throw
    # surfaces as ERROR and the assertion below catches it.
    check_after = engine.execute(
        ScriptExecutionRequest(
            source='if (!fired) throw "timer did not fire";'
        )
    )
    assert check_after.status is ScriptExecutionStatus.RAN, check_after.reason
    assert engine.has_pending_work() is False


def test_ticked_engine_preserves_globals_across_executes() -> None:
    engine = _make_engine()

    first = engine.execute(ScriptExecutionRequest(source="var counter = 1;"))
    second = engine.execute(ScriptExecutionRequest(source="counter += 5; counter;"))

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

    # Each tick fires one due interval and re-arms it; loop a few times.
    engine.tick(timeout_ms=20.0)
    # Allow the re-armed timer to be due (delay 0, but the scheduler
    # bases due_at on monotonic time so a tiny sleep ensures readiness).
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

    # No execute() yet, so no state. Tick should silently no-op.
    engine.tick(timeout_ms=10.0)

    assert engine.has_pending_work() is False
