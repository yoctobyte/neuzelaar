# JavaScript Engine Notes

This project still defaults to the `noop` JavaScript engine in the browser
pipeline. Real execution is now pluggable, but it remains an explicit opt-in
for testing and backend evaluation until permission gating is enforced before
execution.

## Engine Boundary

Backends now plug in through:

- `neuzelaar.engines.js.interface.JavaScriptEngine`
- `neuzelaar.engines.js.factory.create_javascript_engine()`
- `BrowserSession(js_engine=...)`
- `BrowserState(js_engine_factory=...)`

Current backend names:

- `noop`
- `quickjs`
- `own`
- `js2py`

## Reference Suite

Reference suite: TC39 Test262

- official repository: <https://github.com/tc39/test262>
- local runner in this repo: `tools/run_js_test262_subset.py`
- local manifest: `tests/fixtures/js/test262_subset.txt`

The local runner is intentionally narrow. It currently supports:

- sync script tests
- positive tests
- simple negative parse/runtime tests

It does not yet support:

- modules
- async tests
- harness includes
- agent-based or realm-heavy cases

## Current Snapshot

Measured on April 24, 2026 with Python 3.12 in the local `.venv`.

Commands:

```sh
git clone --depth 1 https://github.com/tc39/test262 .cache/test262
.venv/bin/python tools/run_js_test262_subset.py --engine noop
.venv/bin/python tools/run_js_test262_subset.py --engine quickjs
.venv/bin/python tools/run_js_test262_subset.py --engine js2py
```

Results:

- `noop`: `0 passed, 7 failed`
- `quickjs`: `7 passed, 0 failed`
- `own`: separate standalone interpreter track, not yet measured through Test262 subset
- `js2py`: unavailable on Python 3.12 import path, currently fails with `KeyError: 3`

Current read:

- `quickjs` is the strongest reference backend for now
- `own` is now available behind the `JavaScriptEngine` contract for isolated testing
- `js2py` is not a viable baseline in this environment
- `noop` remains the safe browser default while active-content policy stays under construction

## Next Useful Step

The current execution plan is split:

- build the in-repo interpreter first: see `docs/js_own.md`
- keep `quickjs` as the reference backend and oracle
- keep browser default on `noop`

Current practical comparison path:

- fixture-only runner in `neuzelaar/engines/js/fixture_runner.py`
- compare `own` vs `quickjs` on observable host effects
- keep this outside `core/page.py`

Current practical fixture status:

- fixture-only `own` vs `quickjs` parity checks are in place
- current checks cover:
  - console effects
  - document mutations
  - location/history effects
  - timer registration effects

Only after the in-repo interpreter has a credible standalone core and
practical fixture parity should `core/page.py` grow real execution gating and
browser wiring.
