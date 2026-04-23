# Neuzelaar 2 TODO and Project Path

This file is the day-to-day execution list. `PLAN.md` remains the deeper design
and architecture reference.

## Current State

Milestone 1 is partially implemented.

Done:

- Python package skeleton and `pyproject.toml`
- local `.venv` workflow documented
- command/event/frame/surface shell API contracts
- synchronous `Bus`
- URL/origin normalization and 1p/3p classification
- `Request`, `Resource`, `FetchReason`, `TrustDecision`
- `urllib`/file fetch client with byte cap
- conservative MIME classifier
- html5lib adapter into internal `Document`
- internal DOM-like tree and tree walking
- subresource planning for scripts/images/stylesheets/iframes
- strict policy engine for top-level allow, tracker block, third-party script/iframe block
- handler registry for HTML/text/image/download placeholders
- text-only semantic renderer
- CLI path: `python -m neuzelaar <fixture>`
- offline fixtures and smoke docs
- guardrail script and pytest guardrail wrapper
- M1-focused test suite

Current verification command:

```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

## Immediate M1 TODO

These are the remaining items before calling M1 complete.

### 1. Create Real Headless Shell

Owner: Codex

Status: DONE

Files:

- `neuzelaar/shells/headless/shell.py`
- `neuzelaar/shells/headless/__init__.py`
- maybe `neuzelaar/core/page.py` or `neuzelaar/core/pipeline.py`

Goal:

- Move the pipeline currently inside `__main__.py` into a reusable headless shell or page loader.
- `__main__.py` should become thin argument parsing.
- Emit structured events through `Bus` where practical.

Acceptance:

- [x] CLI output stays equivalent or better.
- [x] Tests cover success and blocked-resource output.
- [x] `__main__.py` no longer owns browser pipeline logic.

### 2. Add Page Load Pipeline Object

Owner: Codex or Claude

Status: DONE

Files:

- `neuzelaar/core/page.py` or `neuzelaar/core/pipeline.py`
- `tests/unit/test_page_pipeline.py`

Goal:

- Centralize fetch -> classify -> handle -> render/subresource-policy planning.
- Return a structured result instead of only printing.

Suggested result:

```text
PageLoadResult:
  resource
  mime_decision
  handler_result
  rendered_text
  planned_subresources
  subresource_policy_decisions
  events
```

Acceptance:

- [x] CLI uses this object.
- [x] Tests can assert on structured decisions without parsing stdout.

### 3. Finish M1 Handler Set

Owner: Codex

Status: DONE

Files:

- `neuzelaar/core/handlers/image_handler.py`
- `neuzelaar/core/handlers/download_handler.py`
- `tests/unit/test_handlers.py`

Goal:

- Replace inline placeholder logic in `HandlerRegistry` with named handlers.
- Keep image decoding out of M1; return metadata/placeholder only.

Acceptance:

- [x] Registry has explicit handlers for `html`, `text`, `image`, `download`.
- [x] Unsupported content degrades safely.

### 4. Improve Fetch Client Basics

Owner: Antigravity or Codex

Status: DONE

Files:

- `neuzelaar/core/fetch/client.py`
- `tests/unit/test_fetch_client.py`

Goal:

- Add redirect cap behavior explicitly.
- Better error object for unsupported methods, oversize responses/files, missing files.
- Decide whether M1 supports `POST` in fetch client now or defers it to M4a.

Acceptance:

- [x] Tests cover local file success, missing file failure, byte cap failure, unsupported method.
- [x] No live network required.

### 5. Add Minimal Capability Noops

Owner: Codex

Status: DONE

Files:

- `neuzelaar/core/policy/capability.py`
- `neuzelaar/engines/js/interface.py`
- `neuzelaar/engines/js/noop.py`
- `neuzelaar/engines/wasm/interface.py`
- `neuzelaar/engines/wasm/noop.py`

Goal:

- Reserve active-content hooks without executing anything.

Acceptance:

- [x] Script/WASM execution requests return structured blocked/noop results.
- [x] Tests prove JS/WASM are unavailable by default.

### 6. M1 Documentation Pass

Owner: Gemini Flash

Files:

- `README.md`
- `docs/smoke_tests.md`
- `workdone.md`

Goal:

- Keep docs aligned with the new headless shell/pipeline after it lands.
- Do not edit core code.

Acceptance:

- README setup/run/test commands match reality.
- Smoke tests describe current CLI output accurately.

## M1 Completion Criteria

M1 is complete when:

- `.venv/bin/pytest -q` passes.
- `tools/check_guardrails.sh` passes.
- `python -m neuzelaar tests/fixtures/sites/example.html` prints readable semantic text.
- `python -m neuzelaar tests/fixtures/sites/third_party_script.html` reports the script blocked before fetch.
- Browser pipeline is reusable outside `__main__.py`.
- No GUI, CSS cascade, JS execution, image decode, forms, cookies, or history are required.

## M2 Path: Minimal Document Browser

Theme: make headless/console browsing feel like a small browser, not a one-shot parser.

Work:

- in-memory session and single-tab page state
- navigation history
- link following by URL or link index in console mode
- session-only cookie jar
- console shell with simple commands: open, back, forward, links, resources, quit
- page summary: title, URL, links, blocked resources

Acceptance:

- User can open a fixture page, list links, follow one, go back, and inspect blocked resources.
- No GUI yet.

## M3 Path: Basic Visual Browser

Theme: first actual viewport.

Work:

- choose/lock Tk as first shell unless explicitly changed
- software frame generation and neutral `Frame` presentation
- display list types
- basic block/inline/text layout
- decoded images via Pillow adapter
- scroll support
- tiny CSS slice: inline styles, `<style>`, limited properties

Acceptance:

- A blog/docs fixture renders readably in a window.
- Shell remains thin and imports no core internals beyond shell API.
- Rendering can still be tested headlessly.

## M4a Path: Forms

Theme: traditional web workflows.

Work:

- form model extraction
- GET and POST submission
- input/textarea/select/button state
- focus and text entry
- session cookies sufficient for fixture login/comment flow
- local fixture server for tests

Acceptance:

- Fixture login/comment flow works without JS.

## M4b Path: Persistence and Tabs

Theme: browser state.

Work:

- persistent cookie jar
- multi-tab model
- per-tab history
- tab/session isolation tests

Acceptance:

- Two tabs can hold independent state and history.

## M5 Path: Styling and Policy Maturity

Theme: safe browsing with usable rendering.

Work:

- CSS subset from `PLAN.md`
- external stylesheet fetch/apply under policy
- strict/balanced/compat profile switch
- external blocklist file
- resource budgets
- blocked-resource UI/panel for console and visual shell

Acceptance:

- HN/docs/blog fixtures are readable with basic styling.
- Policy decisions are inspectable.

## M6 Path: Active Content Framework

Theme: permissions before execution.

Work:

- JS engine interface
- capability bridge
- permission events/prompts
- no-op/stub engine that logs blocked or requested capabilities

Acceptance:

- JS-heavy fixture produces a useful capability/block report without executing JS.

## Coordination Notes

- Commit small, coherent slices.
- Run `.venv/bin/pytest -q` before commits touching behavior.
- Run `tools/check_guardrails.sh` before commits touching architecture boundaries.
- Do not revert another agent's changes; inspect and adapt.
- Codex and Claude are the main architecture/implementation leads. Either may change core architecture, but should leave a rationale in commit messages or handoff notes for non-trivial design moves.
- Gemini Flash should focus on testing, fixtures, smoke-test verification, GUI behavior confirmation, docs alignment, and clear bug reports. It should not fight core architecture unless explicitly reassigned.
- Antigravity can own bounded implementation or verification tasks when available, especially fetch/policy integration and end-to-end checks.
