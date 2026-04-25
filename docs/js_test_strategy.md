# JavaScript Test Strategy

This project needs multiple JS test layers. No single suite covers the whole
problem.

## Why Multiple Suites

We are building two things at once:

- a standalone JavaScript interpreter/runtime
- a browser host and UI around that runtime

Those require different verification tools.

## Test Layers

### 1. Internal unit and integration tests

Files:

- `tests/unit/test_js_own_*.py`
- `tests/unit/test_js_practical_fixtures.py`

Purpose:

- fast local feedback
- narrow regression coverage
- direct checks for parser, evaluator, promises, scheduler, timers, and host
  stubs

Use this for:

- new language features
- runtime bug fixes
- scheduler/event-loop behavior
- debug-surface plumbing

### 2. Test262

Primary formal suite for ECMAScript language semantics.

Files and tooling:

- local checkout: `.cache/test262`
- runner: `tools/run_js_test262_subset.py`
- manifest: `tests/fixtures/js/test262_subset.txt`

Purpose:

- standards-oriented language conformance
- parser and runtime correctness for supported syntax/semantics

Use this for:

- expressions
- functions
- classes
- template literals
- promises
- async / await

Guidance:

- expand coverage in controlled batches
- keep manifests feature-oriented
- treat failures explicitly as one of:
  - unsupported by design
  - parser gap
  - runtime bug
  - harness/runner limitation

### 3. Practical backend parity

Files:

- `neuzelaar/engines/js/fixture_runner.py`
- `tests/unit/test_js_practical_fixtures.py`

Purpose:

- compare `own` vs `quickjs` on observable browser-shaped behavior
- verify host effects rather than only return values

Use this for:

- console effects
- document/title changes
- location/history changes
- timer registration and loop behavior

This is the bridge between pure language testing and real browser integration.

### 4. Web Platform Tests (WPT)

Primary suite for browser-facing platform behavior.

Relevant project:

- <https://github.com/web-platform-tests/wpt>

Purpose:

- verify browser host behavior, not just ECMAScript language semantics

Use this later for:

- timers
- microtask ordering in browser contexts
- DOM/event behavior
- URL/history/location behavior
- HTML/script interaction

Why this matters:

- Test262 tells us whether the language/runtime behaves correctly
- WPT tells us whether the browser environment behaves correctly

That distinction matters. Passing Test262 does not mean script execution is
browser-correct.

## Recommended Order

1. internal unit tests first
2. expand Test262 for supported language/runtime features
3. expand practical parity fixtures
4. adopt selected WPT cases once browser-host integration grows

## Near-Term Plan

Before deeper browser JS integration:

- keep expanding Test262 around promises/async/await
- keep parity tests against `quickjs`
- expose scheduler/event-loop state in debug surfaces

When browser-host work becomes active:

- start a curated local WPT subset for:
  - timers
  - microtasks
  - event ordering
  - DOM mutation/event basics
  - history/location behavior

## Non-Goal

Do not try to run broad WPT coverage before the host layer exists. That would
mostly generate noise instead of useful signal.
