"""Minimal WPT-oriented runner for local JS host/runtime checks.

This is not a general Web Platform Tests runner. It is a tiny harness for a
curated subset that exercises the current standalone runtime plus browser-shaped
host stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture, build_browser_scenario
from neuzelaar.engines.js_own.interpreter import evaluate_ast_program
from neuzelaar.engines.js_own.parser import parse_program
from neuzelaar.engines.js_own.runtime_state import runtime_session

try:
    import quickjs as _quickjs
except ImportError:  # pragma: no cover
    _quickjs = None


_HARNESS_PREFIX = r"""
var __wpt_results = "";
var __wpt_pending = 0;
var __wpt_single_test_mode = false;
var __wpt_single_test_done = false;

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

function assert_false(actual, message) {
  if (actual) {
    throw new Error(message || "Expected falsy value");
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

function assert_throws_js(ExpectedError, fn, message) {
  try {
    fn();
  } catch (error) {
    if (error instanceof ExpectedError || error.name === ExpectedError.name) {
      return;
    }
    throw new Error(message || ("Unexpected error: " + __wpt_string(error)));
  }
  throw new Error(message || ("Expected " + ExpectedError.name + " to be thrown"));
}

function setup(_options) {
  if (_options && _options.single_test) {
    __wpt_single_test_mode = true;
  }
}

function done() {
  __wpt_record("PASS", "single_test", "");
  __wpt_single_test_done = true;
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

function __wpt_make_async_test(name) {
  __wpt_pending = __wpt_pending + 1;
  var done_called = false;
  return {
    step: function(fn) {
      if (done_called) {
        return;
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
        self.step(function() { return fn(); });
      };
    },
    step_func_done: function(fn) {
      var self = this;
      return self.step_func(function() {
        var result = fn.apply(null, arguments);
        self.done();
        return result;
      });
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

function async_test(name) {
  if (name && name.call) {
    var fn = name;
    var label = "";
    if (arguments.length > 1) {
      label = arguments[1];
    }
    var t = __wpt_make_async_test(label);
    try {
      fn(t);
    } catch (error) {
      __wpt_fail(label, error);
      __wpt_pending = __wpt_pending - 1;
    }
    return t;
  }
  return __wpt_make_async_test(name);
}
""".strip()

_QUICKJS_TIMER_SHIM = r"""
var __wpt_timer_queue = [];
var __wpt_timer_registry = {};
var __wpt_next_timer_id = 1;
var __wpt_now = 0;

function setTimeout(fn, delay) {
  if (!fn || !fn.call) {
    throw new TypeError("Timer callback must be callable");
  }
  if (delay === undefined || delay === null || isNaN(Number(delay))) {
    delay = 0;
  } else {
    delay = Number(delay);
  }
  if (delay < 0) {
    delay = 0;
  }
  var args = [];
  var i = 2;
  while (i < arguments.length) {
    args.push(arguments[i]);
    i = i + 1;
  }
  var timer = {
    id: __wpt_next_timer_id,
    fn: fn,
    cancelled: false,
    args: args,
    repeat: false,
    delay: delay,
    dueAt: __wpt_now + delay
  };
  __wpt_next_timer_id = __wpt_next_timer_id + 1;
  __wpt_timer_queue.push(timer);
  __wpt_timer_registry[timer.id] = timer;
  return timer.id;
}

function setInterval(fn, delay) {
  if (!fn || !fn.call) {
    throw new TypeError("Timer callback must be callable");
  }
  if (delay === undefined || delay === null || isNaN(Number(delay))) {
    delay = 0;
  } else {
    delay = Number(delay);
  }
  if (delay < 0) {
    delay = 0;
  }
  var args = [];
  var i = 2;
  while (i < arguments.length) {
    args.push(arguments[i]);
    i = i + 1;
  }
  var timer = {
    id: __wpt_next_timer_id,
    fn: fn,
    cancelled: false,
    args: args,
    repeat: true,
    delay: delay,
    dueAt: __wpt_now + delay
  };
  __wpt_next_timer_id = __wpt_next_timer_id + 1;
  __wpt_timer_queue.push(timer);
  __wpt_timer_registry[timer.id] = timer;
  return timer.id;
}

function clearTimeout(id) {
  if (__wpt_timer_registry[id]) {
    __wpt_timer_registry[id].cancelled = true;
  }
}

function clearInterval(id) {
  clearTimeout(id);
}

function queueMicrotask(fn) {
  if (!fn || !fn.call) {
    throw new TypeError("queueMicrotask callback must be callable");
  }
  Promise.resolve().then(function() {
    fn();
  });
}

function __wpt_run_one_timer() {
  if (__wpt_single_test_mode && __wpt_single_test_done) {
    __wpt_timer_queue = [];
    __wpt_timer_registry = {};
    return false;
  }
  var nextIndex = -1;
  var nextDueAt = 0;
  var i = 0;
  while (i < __wpt_timer_queue.length) {
    var candidate = __wpt_timer_queue[i];
    if (!candidate.cancelled && (nextIndex === -1 || candidate.dueAt < nextDueAt)) {
      nextIndex = i;
      nextDueAt = candidate.dueAt;
    }
    i = i + 1;
  }
  if (nextIndex === -1) {
    return false;
  }
  __wpt_now = nextDueAt;
  var timer = __wpt_timer_queue.splice(nextIndex, 1)[0];
  if (timer.cancelled) {
    delete __wpt_timer_registry[timer.id];
    return false;
  }
  timer.fn.apply(null, timer.args);
  if (timer.repeat && !timer.cancelled) {
    timer.dueAt = __wpt_now + timer.delay;
    __wpt_timer_queue.push(timer);
  } else {
    delete __wpt_timer_registry[timer.id];
  }
  return true;
}

function __wpt_has_timer_work() {
  if (__wpt_single_test_mode && __wpt_single_test_done) {
    return false;
  }
  while (__wpt_timer_queue.length > 0) {
    var timer = __wpt_timer_queue[0];
    if (!timer.cancelled) {
      return true;
    }
    __wpt_timer_queue.shift();
  }
  return false;
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
    engine: str
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


def run_case(case: WptCase, *, engine: str = "own") -> WptOutcome:
    if engine == "own":
        return _run_case_own(case)
    if engine == "quickjs":
        return _run_case_quickjs(case)
    raise ValueError(f"Unknown engine: {engine}")


def _run_case_own(case: WptCase) -> WptOutcome:
    environment, stubs = build_browser_scenario(case.scenario)
    program = parse_program(build_program(case))
    try:
        with runtime_session(ScriptRuntimeConfig(debug_track_tasks=True, debug_keep_history=True), scheduler=stubs.scheduler) as state:
            evaluate_ast_program(program, environment)
            safety_rounds = 0
            while state.has_pending_work():
                if bool(environment.get("__wpt_single_test_done")):
                    state.timers = []
                    break
                if not state.has_ready_work():
                    next_due = min(
                        (pending.due_at for pending in state.timers if not pending.cancelled),
                        default=None,
                    )
                    if next_due is not None:
                        for pending in state.timers:
                            if not pending.cancelled and pending.due_at == next_due:
                                pending.due_at = time.monotonic()
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


def _run_case_quickjs(case: WptCase) -> WptOutcome:
    if _quickjs is None:
        return WptOutcome(case=case, status="failed", reason="quickjs package is not installed")
    context = _quickjs.Context()
    try:
        context.eval(build_quickjs_program(case))
        safety_rounds = 0
        while True:
            progressed = False
            while context.execute_pending_job():
                progressed = True
            if context.eval("__wpt_has_timer_work();"):
                context.eval("__wpt_run_one_timer();")
                progressed = True
                continue
            if not progressed:
                break
            safety_rounds += 1
            if safety_rounds > 1000:
                break
        raw_results = str(context.eval("__wpt_results"))
        pending_count = int(context.eval("__wpt_pending"))
        test_results = _parse_results(raw_results)
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


def run_cases(cases: list[WptCase], *, engine: str = "own") -> WptRunSummary:
    outcomes = tuple(run_case(case, engine=engine) for case in cases)
    passed = sum(outcome.status == "passed" for outcome in outcomes)
    failed = sum(outcome.status == "failed" for outcome in outcomes)
    return WptRunSummary(engine=engine, total=len(outcomes), passed=passed, failed=failed, outcomes=outcomes)


def build_program(case: WptCase) -> str:
    return "\n".join((_HARNESS_PREFIX, case.source))


def build_quickjs_program(case: WptCase) -> str:
    return "\n".join((_HARNESS_PREFIX, _QUICKJS_TIMER_SHIM, case.source))


def _parse_results(raw: str) -> tuple[WptTestResult, ...]:
    results: list[WptTestResult] = []
    for line in raw.splitlines():
        if not line:
            continue
        status, name, message = (line.split("|", 2) + ["", ""])[:3]
        results.append(WptTestResult(status=status, name=name, message=message))
    return tuple(results)
