# Scripting TODO

This is the focused handoff for the JS runtime track. It describes what is
already in, what is still missing, and the recommended order from here.

## Current State

Implemented on the standalone `js_own` path:

- language core:
  - expressions and operators (incl. `**`, `??`, `?:`, `--`, `+=`/`-=`/`*=`/`/=`/`%=`)
  - variables / blocks / `if`
  - `while`, `for`, `break`, `continue`
  - var and function-declaration hoisting
  - `let` / `const` re-declaration is a SyntaxError
  - functions / closures / `return`
  - objects / arrays / property access / indexing
  - exceptions (`throw`, `try` / `catch` / `finally`)
  - template literals (incl. tagged templates for the supported slice)
  - arrow functions
  - classes (incl. private fields / methods / accessors,
    inheritance, `super`, static members, computed names)
- runtime semantics:
  - distinct `null` and `undefined` (singleton sentinel)
  - reference identity for `===` on objects and arrays
  - IEEE 754 division/modulo (`1/0` is `Infinity`, `0/0` is `NaN`,
    `5 % -2` matches JS)
  - deep recursion surfaces as a catchable JS RangeError
  - `typeof` on an undeclared identifier returns `"undefined"`
- stdlib surface:
  - **strings**: `length`, indexing, `charAt`, `charCodeAt`,
    `indexOf`, `lastIndexOf`, `includes`, `startsWith`,
    `endsWith`, `slice`, `substring`, `toUpperCase`,
    `toLowerCase`, `trim`/`trimStart`/`trimEnd`, `split`,
    `replace` (first match), `replaceAll`, `repeat`, `concat`,
    `padStart`, `padEnd`, `toString`, `valueOf`
  - **arrays**: `push`, `pop`, `shift`, `unshift`, `indexOf`,
    `lastIndexOf`, `includes`, `slice`, `concat`, `join`,
    `reverse`, `forEach`, `map`, `filter`, `find`, `findIndex`,
    `some`, `every`, `reduce`, `sort`, `flat`
  - **`Math`**: `abs`, `floor`, `ceil`, `round`, `trunc`, `sign`,
    `sqrt`, `log`, `log2`, `log10`, `exp`, `sin`, `cos`, `tan`,
    `asin`, `acos`, `atan`, `atan2`, `pow`, `min`, `max`,
    `random`, plus `PI`, `E`, `LN2`, `LN10`, `LOG2E`, `LOG10E`,
    `SQRT2`, `SQRT1_2`
  - **`Number`**: `isFinite`, `isNaN`, `isInteger`, plus
    `MAX_SAFE_INTEGER` / `MIN_SAFE_INTEGER` / `MAX_VALUE` /
    `MIN_VALUE` / `EPSILON` / `POSITIVE_INFINITY` /
    `NEGATIVE_INFINITY` / `NaN`
  - **globals**: `parseInt` (with radix and `0x` prefix),
    `parseFloat`, `isNaN`, `isFinite`, `Infinity`, `NaN`,
    `undefined`
  - **`JSON`**: `parse`, `stringify` (whole-number floats render
    as integers; class internal markers and undefined/function
    values are skipped; supports the indent argument)
  - **`Object`**: `create`, `keys`, `values`, `entries`,
    `assign`, `freeze` (no-op), `fromEntries`
  - **`Array`**: `isArray`, `from`, `of`
  - **`Boolean`**: coercion constructor
  - **error constructors**: `Error`, `TypeError`, `RangeError`,
    `ReferenceError`, `SyntaxError`
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
  - `setInterval(...)`
  - `clearInterval(...)`

Current verification baseline:

- `.venv/bin/pytest -q`
- `tools/check_guardrails.sh`
- `tools/run_js_test262_subset.py --engine own`
- `tools/run_js_test262_subset.py --engine quickjs`
- `tools/run_js_wpt_subset.py --engine own`
- `tools/run_js_wpt_subset.py --engine quickjs`
- `tools/run_js_wpt_subset.py --engine own --manifest tests/fixtures/js/wpt_upstream_subset.txt`
- `tools/run_js_wpt_subset.py --engine quickjs --manifest tests/fixtures/js/wpt_upstream_subset.txt`

Related strategy docs:

- `docs/js_own.md`
- `docs/js_engines.md`
- `docs/js_test_strategy.md`

## What Is Still Missing

### Formal conformance

- broader Test262 coverage
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

#### Resolved: DOM-mutation → repaint coupling

Initial answer landed: every host-bridged DOM write publishes a
``DomMutated`` event, and shells debounce-repaint on the same queue
they use for ``ImageReady``. Hot-loop optimisation (commit-at-task-
boundary) is deferred until we measure a page that actually pays the
cost — debouncing already coalesces bursts within ~50ms, which covers
the common cases.

Currently bridged: ``element.textContent`` writes on id-bearing
elements. Not yet bridged: ``innerHTML``, ``setAttribute``, child
insertion / removal, style mutations. Each of these can land
incrementally without revisiting the cadence question.

### Language surface still deferred

In rough priority order — landing any one of these unlocks a real
chunk of programs.

1. **`for...of` / `for...in`** — iterator protocol or special-cased
   forms for arrays and objects
2. **`switch` / `case`** — fall-through, `default`, `break`
3. **destructuring** — `let { a, b } = obj`, `let [x, y] = arr`,
   defaults, rest
4. **default and rest function parameters** —
   `function f(x = 1, ...rest)`
5. **spread** — `f(...args)`, `[...a, ...b]`, `{...other}`
6. **computed object keys + shorthand** — `{ [k]: v }`, `{ x }`,
   method shorthand on object literals, getters/setters in object
   literals
7. **optional chaining `?.`** — pairs naturally with the existing
   `??`
8. **bitwise** — `& | ^ ~ << >> >>>` (JS uses 32-bit signed ints
   with ToInt32/ToUint32 coercions)
9. **`delete`, `void`** — small individual fixes
10. **regex literals + `RegExp` builtin** — could lean on Python
    `re`, but the `/` token disambiguation needs lookback context
    in the tokenizer (today `/` is always SLASH)
11. **iterators and generators** — `function*`, `yield`. Big.
12. **Symbol** — moderate. Required by full iterator protocol.
13. **`Map` / `Set` / `WeakMap` / `WeakSet`** — moderate
14. **`Date`** — small for basics, large for full impl
15. **modules** (`import` / `export`) — large
16. **classes**: private static method/field edge cases,
    decorators, `static {}` blocks
17. **labeled statements** + labeled `break` / `continue`

### Known limitations of currently-implemented features

These are landed but with caveats worth fixing in their own slices.

- **`for (let i = 0; ...)` does not yet create a per-iteration
  binding.** Closures over `i` see the final value (3,3,3 not
  0,1,2). Behavior matches `var`. Spec calls for per-iter scope:
  copy the let-bindings into a fresh child block at each iteration,
  and re-bind the update's result into the next iteration's child.
- **Async loops with `await` inside don't work.** The async path
  delegates `while` / `for` to the sync evaluator, which raises on
  `AwaitExpr`. Loops without await are fine. Fixing this needs a
  continuation-style loop in the async path — handle `await` as a
  resumption point, evaluate test/update through
  `_evaluate_async_expr`, re-enter the body lambda each iteration.
- **Compound assignment double-evaluates index targets.**
  `arr[fn()] += 1` calls `fn()` twice (read + write). Identifier
  and MemberExpr targets are safe. Fix: cache the index between
  the read and the write.
- **`-2 ** 3` parses to `-8`.** JS spec calls this a SyntaxError
  because of the unary-vs-binary ambiguity. We accept it.
- **`??` mixes freely with `||` and `&&`.** JS spec requires
  parentheses (`a ?? b || c` is a SyntaxError); we don't enforce
  the parse-time check.
- **Function self-name binding inside `JavaScriptFunction.call` is
  `kind="const"`.** A `var <fn-name> = ...` inside the function
  body would raise SyntaxError under the new redecl check. Rare
  but exists; demote to a special internal kind if a real program
  hits it.

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
   - widen the imported upstream WPT subset around:
     - more `queueMicrotask`
     - timer error behavior
     - promise rejection behavior

5. Host/DOM expansion
   - only after the runtime behavior is easier to observe and trust

## Explicit Non-Goals Right Now

- turning on JS execution broadly in the browser
- multi-threaded script execution
- performance tuning before we have stronger debug visibility
- chasing broad Test262 numbers before the runtime/debug path is easier to inspect
