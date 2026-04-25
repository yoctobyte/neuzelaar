# WPT Host Layer Plan

Web Platform Tests target more than the JavaScript language. They exercise the
browser environment around the language runtime.

## What WPT Wants To Test

For this project, WPT becomes relevant when script execution is no longer just
standalone JS semantics and starts touching browser behavior:

- timers and task ordering
- microtask ordering
- DOM mutation
- event listeners and dispatch
- location/history behavior
- HTML/script interaction

That means WPT is not primarily a parser/interpreter suite. It is a browser-host
suite.

## What Our Host Layer Needs

### Current minimum for local WPT-style checks

Already present or now scaffolded:

- `Promise`
- `queueMicrotask`
- `setTimeout`
- `clearTimeout`
- event-loop stepping
- scheduler/task debug state
- minimal browser-shaped globals from host stubs

That is enough for a tiny local subset around:

- microtasks before timers
- cancelled timers
- promise reaction ordering

### What real upstream-style WPT adoption will need

- `window` / `self` / `globalThis` shape
- more complete timer behavior
- DOM-backed `document` and element objects
- event listeners
- event dispatch semantics
- location/history integration with browser state
- HTML harness assumptions where applicable

## Practical Staging

1. local WPT-oriented subset for timers/microtasks
2. debug visibility for scheduler/event-loop state in the viewer
3. controlled browser-fixture integration
4. selected upstream WPT-inspired cases for DOM/events/history

## Current Scope

This repo now includes a tiny local WPT-oriented runner:

- `tools/run_js_wpt_subset.py`
- `tests/fixtures/js/wpt_subset.txt`
- `tests/fixtures/js/wpt/`

This is intentionally narrow. It is a host/runtime checkpoint, not a claim that
we can run the upstream WPT suite broadly yet.

## First Imported Upstream Frontier

We now have a first imported upstream manifest:

- `tests/fixtures/js/wpt_upstream_subset.txt`

Current imported focus:

- timer cancellation interoperability
- timeout delay normalization
- missing/undefined interval delay behavior
- `queueMicrotask` semantics

Current state:

- `quickjs` passes the current imported subset
- `own` also passes the current imported subset

That is still useful. It gives us:

- a real upstream reference path
- a narrower compatibility target than "all of WPT"
- a concrete next host/runtime backlog

## Current Imported Coverage

Current imported upstream cases:

- `html/webappapis/timers/cleartimeout-clearinterval.any.js`
- `html/webappapis/timers/negative-settimeout.any.js`
- `html/webappapis/timers/missing-timeout-setinterval.any.js`
- `html/webappapis/microtask-queuing/queue-microtask.any.js`

These are now passing on both:

- `own`
- `quickjs`

## Next Practical WPT Work

The next useful upstream WPT targets are:

1. more `queueMicrotask` / microtask cases
2. unhandled promise rejection behavior
3. DOM/event/history cases once the host surface grows

The order still matters. Timers and microtasks were the right first imported
frontier because they map cleanly to the current runtime.
