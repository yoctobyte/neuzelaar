# Own JavaScript Interpreter

This is the in-repo interpreter track. It is intentionally separate from the
browser execution path.

## Goal

Build a small JavaScript interpreter we understand end to end, then wire it
into the browser only after the language core is credible enough.

## Package

- `neuzelaar/engines/js_own/tokenizer.py`
- `neuzelaar/engines/js_own/parser.py`
- `neuzelaar/engines/js_own/ast.py`
- `neuzelaar/engines/js_own/environment.py`
- `neuzelaar/engines/js_own/runtime.py`
- `neuzelaar/engines/js_own/interpreter.py`

## Stages

### JS0

Scope:

- numeric literals
- string literals
- `true`, `false`, `null`
- identifiers
- grouping
- unary `!`, unary `+`, unary `-`
- arithmetic `+ - * / %`
- comparison `< > <= >=`
- equality `== != === !==`
- logical `&& ||`
- semicolon-separated expression programs

Out of scope:

- declarations
- assignment
- objects
- arrays
- functions
- property access
- statements beyond expression sequencing

### JS1

Scope:

- `var`, `let`, `const`
- assignment to existing bindings
- block statements
- `if` / `else`

Notes:

- `let` / `const` use block scope
- `var` binds in the current var-scope root
- functions are still out of scope, so there is no function-scope behavior yet

Status:

- implemented

### JS2

Scope:

- function declarations
- function expressions
- arrow functions
- calls
- `return`
- lexical closure capture

Status:

- implemented

### JS3

Scope:

- array literals
- object literals
- property access
- indexing
- method-call `this` binding

Status:

- implemented

### Class Core

Scope:

- class declarations
- class expressions
- `extends`
- method declarations
- instance fields
- getters/setters
- static fields
- static methods
- computed method and field names
- private fields
- private methods/accessors
- `constructor`
- `new`
- prototype-based method lookup for plain JS objects
- `super(...)` in constructors
- `super.method(...)` in methods

Out of scope:

- private fields or methods in live browser wiring

Status:

- implemented

### JS4

Scope:

- `throw`
- `try` / `catch` / `finally`
- template literals
- small builtin surface:
  - `Math.abs`
  - `Math.max`
  - `Number`
- `String`
- `Error`

Status:

- implemented

### JS5

Scope:

- explicit host-callable wrapper
- explicit host-object wrapper
- host property/index bridge helpers
- builtin installation via the host bridge
- meaningful standalone browser-shaped stubs:
  - `console`
  - timers
  - `document`
  - `location`
  - `history`
- fixture-driven host scenarios that assemble coherent fake page state

Status:

- in progress
- initial host bridge implemented
- thin `JavaScriptEngine` adapter implemented for isolated tests

## Runtime Control

The standalone interpreter now has a minimal runtime-control surface:

- `ScriptRuntimeConfig.max_steps`
- `ScriptRuntimeConfig.max_wall_ms`

These are intentionally local to `js_own` for now. They are the first step
toward later scheduler, fairness, and async work, but they do not yet imply a
task queue or browser event loop.

## Scheduler Debug Groundwork

The standalone host/test layer now also has a minimal scheduler/task model in
`neuzelaar/engines/js_own/scheduler.py`.

Current scope:

- queue task records
- task snapshots
- optional retained history
- timer stubs can publish `setTimeout` work into the scheduler for debug

This is still debug/runtime-plumbing only:

- no promise queue
- no microtask semantics
- no async/await lowering
- no live browser scheduler yet

## Current Reference

Use `quickjs` as the current oracle backend for supported snippets.

For JS0 and JS1, the comparison strategy is:

- keep a narrow list of supported expressions
- compare our evaluator against `quickjs`
- grow coverage only when semantics are deliberate and tested
