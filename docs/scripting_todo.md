# Scripting TODO

This is the focused handoff for the JS runtime track. It describes what is
already in, what is still missing, and the recommended order from here.

## Current State

Implemented on the standalone `js_own` path:

- language core:
  - expressions
  - variables / blocks / `if`
  - functions / closures / `return`
  - objects / arrays / property access / indexing
  - exceptions
  - template literals
  - arrow functions
  - classes
  - private fields / methods / accessors
- async surface:
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
- runtime control:
  - execution budgets
  - scheduler task taxonomy
  - scheduler debug snapshots/history
  - single-threaded event-loop stepping
  - bounded `step(...)`
  - `run_until_idle()` helper
  - timer dispatch for `setTimeout(...)`
  - `clearTimeout(...)`

Current verification baseline:

- `.venv/bin/pytest -q`
- `tools/check_guardrails.sh`
- `tools/run_js_test262_subset.py --engine own`

Related strategy docs:

- `docs/js_own.md`
- `docs/js_engines.md`
- `docs/js_test_strategy.md`

## What Is Still Missing

### Formal conformance

- broader Test262 coverage
- better compatibility with Test262 source/harness forms
- larger async/promise-oriented formal subset

### Runtime semantics

- richer promise edge cases
- unhandled rejection tracking/reporting
- more complete async expression coverage in complex edge cases
- stronger scheduler/task statistics for long-running sessions

### Event loop

- debug snapshot/export API for event-loop state
- clearer separation of:
  - queued
  - ready
  - due now
  - future scheduled
- fairness tuning beyond simple deterministic ordering
- later: background-thread execution if we ever truly need it

### Timers and tasks

- `setInterval(...)`
- interval cancellation semantics
- more explicit timer/task inspection for debug UI
- optional per-task budget overrides

### Browser integration

- controlled browser-fixture integration
- policy-aware execution gates for real JS
- live browser-path integration remains deferred

### Host surface

- more useful `document` methods
- event listener model
- DOM mutation/event bridge
- better browser-like globals

### Language surface still deferred

- modules
- generators
- `for` / `while` / `switch`
- destructuring
- classes beyond current supported slice if needed
- private static methods/fields edge-case hardening

## Recommended Order

1. Event-loop debug surface
   - structured snapshot API
   - expose loop/task/timer state cleanly for console/Tk debug panes

2. Browser-fixture integration
   - use the standalone runtime only on controlled fixtures first
   - keep policy and permission gates explicit

3. Promise/runtime hardening
   - unhandled rejection tracking
   - broader async/promise tests
   - more scheduler stats

4. Formal-test expansion
   - widen the curated Test262 subset around:
     - promises
     - async functions
     - await
     - microtask ordering

5. Host/DOM expansion
   - only after the runtime behavior is easier to observe and trust

## Explicit Non-Goals Right Now

- turning on JS execution broadly in the browser
- multi-threaded script execution
- performance tuning before we have stronger debug visibility
- chasing broad Test262 numbers before the runtime/debug path is easier to inspect
