# Scripting Handover

Date: 2026-04-25

This is the current handover for the Neuzelaar scripting/runtime track after
the first upstream WPT import wave.

## Executive Summary

The scripting track is no longer just a standalone language prototype.

Current state:

- the in-repo interpreter (`js_own`) has a credible language/runtime core
- the curated local Test262 subset passes on:
  - `own`
  - `quickjs`
- the local WPT-style subset passes on:
  - `own`
  - `quickjs`
- the first imported upstream WPT subset also passes on:
  - `own`
  - `quickjs`

That means we now have real signal across three layers:

1. internal unit/integration tests
2. formal ECMAScript-oriented tests
3. browser-host-oriented timer/microtask tests

## Implemented Runtime Surface

### Language/runtime

Implemented in `js_own`:

- expressions and operators
- `var` / `let` / `const`
- blocks
- `if`
- `while`
- functions and closures
- arrow functions
- `return`
- objects and arrays
- property access and indexing
- method-call `this`
- `typeof`
- exceptions:
  - `throw`
  - `try` / `catch` / `finally`
- template literals
- tagged template support for the supported slice
- `++` prefix/postfix

### Classes

Implemented:

- class declarations and expressions
- inheritance
- `super(...)`
- `super.method(...)`
- static methods
- instance fields
- getters/setters
- static fields
- computed names
- private fields / methods / accessors

### Async/runtime control

Implemented:

- `Promise`
- `Promise.resolve(...)`
- `Promise.reject(...)`
- `.then(...)`
- `.catch(...)`
- `.finally(...)`
- `queueMicrotask(...)`
- `async function`
- async arrow functions
- async class methods
- `await`

Runtime control:

- step budget
- wall-time budget
- single-threaded event-loop stepping
- timer queue
- microtask queue
- scheduler/task snapshots and optional history

### Host/browser-shaped stubs

Implemented stubs:

- `console`
- `document`
- `location`
- `history`
- `setTimeout`
- `clearTimeout`
- `setInterval`
- `clearInterval`

## Testing Status

### 1. Internal test suite

Current repo baseline at handover:

- `.venv/bin/pytest -q` -> `455 passed`
- `tools/check_guardrails.sh` -> pass

### 2. Test262 subset

Runner:

- `tools/run_js_test262_subset.py`

Current curated subset status:

- `own`: pass
- `quickjs`: pass

This subset is still intentionally narrow. It is a foothold, not broad
conformance.

### 3. Local WPT-style subset

Runner:

- `tools/run_js_wpt_subset.py`

Manifest:

- `tests/fixtures/js/wpt_subset.txt`

Status:

- `own`: pass
- `quickjs`: pass

Current local focus:

- microtasks before timers
- `queueMicrotask`
- timer cancellation
- promise reaction ordering

### 4. Imported upstream WPT subset

Manifest:

- `tests/fixtures/js/wpt_upstream_subset.txt`

Current imported upstream coverage:

- `html/webappapis/timers/cleartimeout-clearinterval.any.js`
- `html/webappapis/timers/negative-settimeout.any.js`
- `html/webappapis/timers/missing-timeout-setinterval.any.js`
- `html/webappapis/microtask-queuing/queue-microtask.any.js`

Status:

- `own`: pass
- `quickjs`: pass

This is the first real upstream WPT foothold.

## Important Architectural Result

The biggest recent bug that mattered was not in timers or WPT directly.

It was function-call scoping.

Fixed:

- each function invocation now gets its own var-scope root

That corrected cross-call state leakage and was necessary for imported upstream
WPT cases to behave correctly.

This was a meaningful runtime correctness fix, not just test accommodation.

## Current Limitations

The scripting track is still not ready for broad live browser execution.

Important remaining gaps:

- broader Test262 coverage
- more upstream WPT coverage
- unhandled promise rejection behavior
- richer promise edge cases
- DOM mutation/event host surface
- event listeners and dispatch
- browser-state integration for real pages/tabs/navigation
- policy-correct execution gating in the browser path
- GUI exposure of scheduler/event-loop state

## Recommended Next Order

1. expose scheduler/event-loop state in the debug UI
2. expand upstream WPT around:
   - more `queueMicrotask`
   - promise rejection behavior
   - timer error behavior
3. expand Test262 around promises/async
4. only then widen browser-host integration
5. only after that start deeper DOM/event WPT work

## Commands To Re-Verify

```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
.venv/bin/python tools/run_js_test262_subset.py --engine own
.venv/bin/python tools/run_js_test262_subset.py --engine quickjs
.venv/bin/python tools/run_js_wpt_subset.py --engine own
.venv/bin/python tools/run_js_wpt_subset.py --engine quickjs
.venv/bin/python tools/run_js_wpt_subset.py --engine own --manifest tests/fixtures/js/wpt_upstream_subset.txt
.venv/bin/python tools/run_js_wpt_subset.py --engine quickjs --manifest tests/fixtures/js/wpt_upstream_subset.txt
```

## Files To Start From Next Time

- `docs/scripting_todo.md`
- `docs/js_own.md`
- `docs/js_test_strategy.md`
- `docs/wpt_plan.md`
- `tests/fixtures/js/wpt_upstream_subset.txt`
- `neuzelaar/engines/js/wpt.py`
