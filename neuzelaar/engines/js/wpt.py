"""Minimal WPT-oriented runner for local JS host/runtime checks.

This is not a general Web Platform Tests runner. It is a tiny harness for a
curated subset that exercises the current standalone runtime plus browser-shaped
host stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture, build_browser_scenario
from neuzelaar.engines.js_own.interpreter import evaluate_ast_program
from neuzelaar.engines.js_own.parser import parse_program
from neuzelaar.engines.js_own.runtime_state import runtime_session


_HARNESS_PREFIX = r"""
var __wpt_results = "";
var __wpt_pending = 0;

function __wpt_string(value) {
  if (value === undefined) {
    return "undefined";
  }
  if (value === null) {
    return "null";
  }
  return String(value);
}

function __wpt_record(status, name, message) {
  __wpt_results = __wpt_results + status + "|" + __wpt_string(name) + "|" + __wpt_string(message) + "\n";
}

function __wpt_fail(name, error) {
  if (error && error.message !== undefined) {
    __wpt_record("FAIL", name, error.message);
    return;
  }
  __wpt_record("FAIL", name, __wpt_string(error));
}

function assert_true(actual, message) {
  if (!actual) {
    throw new Error(message || "Expected truthy value");
  }
}

function assert_equals(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(message || ("Expected " + __wpt_string(expected) + ", got " + __wpt_string(actual)));
  }
}

function assert_array_equals(actual, expected, message) {
  if (actual.length !== expected.length) {
    throw new Error(message || ("Expected length " + expected.length + ", got " + actual.length));
  }
  var i = 0;
  while (i < actual.length) {
    if (actual[i] !== expected[i]) {
      throw new Error(message || ("Mismatch at " + i + ": " + __wpt_string(expected[i]) + " != " + __wpt_string(actual[i])));
    }
    i = i + 1;
  }
}

function assert_unreached(message) {
  throw new Error(message || "Reached unexpectedly");
}

function test(fn, name) {
  try {
    fn();
    __wpt_record("PASS", name, "");
  } catch (error) {
    __wpt_fail(name, error);
  }
}

function promise_test(fn, name) {
  __wpt_pending = __wpt_pending + 1;
  try {
    Promise.resolve(fn()).then(
      function() {
        __wpt_record("PASS", name, "");
        __wpt_pending = __wpt_pending - 1;
      },
      function(error) {
        __wpt_fail(name, error);
        __wpt_pending = __wpt_pending - 1;
      }
    );
  } catch (error) {
    __wpt_fail(name, error);
    __wpt_pending = __wpt_pending - 1;
  }
}

function async_test(name) {
  __wpt_pending = __wpt_pending + 1;
  var done_called = false;
  return {
    step: function(fn) {
      if (done_called) {
        throw new Error("async_test already completed");
      }
      try {
        fn();
      } catch (error) {
        done_called = true;
        __wpt_fail(name, error);
        __wpt_pending = __wpt_pending - 1;
      }
    },
    step_func: function(fn) {
      var self = this;
      return function() {
        var args = arguments;
        self.step(function() { return fn.apply(null, args); });
      };
    },
    step_timeout: function(fn, delay) {
      var wrapped = this.step_func(fn);
      return setTimeout(wrapped, delay);
    },
    done: function() {
      if (done_called) {
        throw new Error("async_test done called twice");
      }
      done_called = true;
      __wpt_record("PASS", name, "");
      __wpt_pending = __wpt_pending - 1;
    }
  };
}
""".strip()


@dataclass(frozen=True, slots=True)
class WptCase:
    path: Path
    source: str
    scenario: BrowserScenarioFixture

    @property
    def display_name(self) -> str:
        return self.path.as_posix()


@dataclass(frozen=True, slots=True)
class WptTestResult:
    status: str
    name: str
    message: str


@dataclass(frozen=True, slots=True)
class WptOutcome:
    case: WptCase
    status: str
    reason: str
    test_results: tuple[WptTestResult, ...] = ()
    pending_count: int = 0


@dataclass(frozen=True, slots=True)
class WptRunSummary:
    total: int
    passed: int
    failed: int
    outcomes: tuple[WptOutcome, ...] = field(default_factory=tuple)


def load_case(path: str | Path) -> WptCase:
    case_path = Path(path)
    source = case_path.read_text(encoding="utf-8")
    return WptCase(
        path=case_path,
        source=source,
        scenario=BrowserScenarioFixture(
            url="https://example.test/",
            title="WPT Fixture",
            scheduler_debug=True,
        ),
    )


def run_case(case: WptCase) -> WptOutcome:
    environment, stubs = build_browser_scenario(case.scenario)
    program = parse_program(build_program(case))
    try:
        with runtime_session(ScriptRuntimeConfig(debug_track_tasks=True, debug_keep_history=True), scheduler=stubs.scheduler) as state:
            evaluate_ast_program(program, environment)
            safety_rounds = 0
            while state.has_pending_work():
                result = state.step(until_idle=True, timeout_ms=5.0, max_tasks=1000)
                safety_rounds += 1
                if not result.progressed or safety_rounds > 100:
                    break
        test_results = _parse_results(str(environment.get("__wpt_results")))
        pending_count = int(environment.get("__wpt_pending"))
    except Exception as exc:
        return WptOutcome(case=case, status="failed", reason=f"{type(exc).__name__}: {exc}")
    if pending_count != 0:
        return WptOutcome(
            case=case,
            status="failed",
            reason=f"{pending_count} pending test(s) remain after event-loop drain",
            test_results=test_results,
            pending_count=pending_count,
        )
    failed = [result for result in test_results if result.status != "PASS"]
    if failed:
        first = failed[0]
        return WptOutcome(
            case=case,
            status="failed",
            reason=f"{first.name}: {first.message}",
            test_results=test_results,
            pending_count=pending_count,
        )
    return WptOutcome(
        case=case,
        status="passed",
        reason=f"{len(test_results)} test(s) passed",
        test_results=test_results,
        pending_count=pending_count,
    )


def run_cases(cases: list[WptCase]) -> WptRunSummary:
    outcomes = tuple(run_case(case) for case in cases)
    passed = sum(outcome.status == "passed" for outcome in outcomes)
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    return WptRunSummary(total=len(outcomes), passed=passed, failed=failed, outcomes=outcomes)


def build_program(case: WptCase) -> str:
    return "\n".join((_HARNESS_PREFIX, case.source))


def _parse_results(raw: str) -> tuple[WptTestResult, ...]:
    results: list[WptTestResult] = []
    for line in raw.splitlines():
        if not line:
            continue
        status, name, message = (line.split("|", 2) + ["", ""])[:3]
        results.append(WptTestResult(status=status, name=name, message=message))
    return tuple(results)
