# Neuzelaar 2 TODO

Day-to-day execution tracker. `PLAN.md` is the architecture reference;
`docs/projects.md` is the work-package view; `docs/deferred_details.md`
captures later details; `*_TASKS.md` files define agent roles; `chat/` is
async agent messaging.

## Start Here

Run before development:

```sh
git status --short
git log --oneline -8
.venv/bin/pytest -q
tools/check_guardrails.sh
```

Current verification target:

```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

Expected:

- `example.html` prints readable semantic text.
- `third_party_script.html` reports the third-party script as blocked before fetch.
- pytest and guardrails pass.

## Status Dashboard

| Area | Status | Notes |
|---|---|---|
| M1 headless skeleton | Done | Final docs/smoke verification complete. |
| Package/test setup | Done | `pyproject.toml`, `.venv` workflow, pytest suite. |
| Core contracts | Done | commands/events/frame/surface, bus, resource/request types. |
| URL/origin policy base | Done | `core/origin.py`, strict 1p/3p decisions. |
| Fetch client basics | Done | local/HTTP GET, byte cap, structured `FetchError`; POST deferred. |
| MIME/handlers | Done | HTML/text/image/download safe handlers. |
| Document pipeline | Done | html5lib adapter, internal DOM, subresource planning. |
| Headless pipeline | Done | reusable `PageLoader`, `HeadlessShell`, thin CLI. |
| Active content hooks | Done | JS/WASM interfaces and no-op blocked engines. |
| Guardrails | Done | pytest invokes `tools/check_guardrails.sh`. |
| M1 docs verification | Done | See `workdone-gemini-flash.md`. |
| M2 minimal document browser | Done | Session/history/link listing/console commands/cookies/events implemented. |
| M3 rendering foundation | In progress | Display list, software rasterizer, and Tk shell frame path implemented; GUI smoke pending. |
| M4a forms | Done | Form extraction, GET/POST submission, and fixture-server flow implemented. |
| MVP code path | Done | Headless/console/Tk frame path, forms, cookies, policy, basic CSS, and tests implemented. |
| P8 browser state hardening | Done | Persistent cookies, multi-tab model, and per-tab history isolation implemented. |
| P9 styling and compatibility | In progress | Same-origin stylesheet fetch, descendant selectors, local image rendering, basic margin/padding/font-size layout, and passive asset budgets are in; broader CSS/layout still open. |

## Active Backlog

Work from complete packages. Keep details that do not affect the current
boundary in `docs/deferred_details.md`.

### P0: MVP GUI Verification

Owner: Gemini Flash

Status: Open

Files:

- `neuzelaar/shells/tk/shell.py`
- `docs/mvp_status.md`
- `docs/projects.md`
- `workdone-gemini-flash.md`

Tasks:

- run the Tk shell on a machine with a working display
- verify page visibility, scrolling, and no obvious overlap on simple fixtures
- record exact results

Acceptance:

- a real display smoke report exists
- MVP docs can say visual shell behavior was manually checked

### P1: MVP Release Note

Owner: Codex

Status: Open

Files:

- `docs/mvp_status.md`
- optionally `docs/releases/mvp.md` later

Tasks:

- once GUI smoke is done, write one concise MVP checkpoint note
- keep it factual: what works, what is deferred, how to verify

Acceptance:

- one stable document to hand someone who wants the current state quickly

### P1: Next Package Selection

Owner: Codex + user

Status: Open

Choices:

- P8 browser state hardening
- P9 styling and compatibility
- P10 active content

Acceptance:

- next package is chosen explicitly
- `TODO.md` backlog reflects that choice

### P9: Styling And Compatibility

Owner: Codex

Status: In progress

Files:

- `neuzelaar/core/page.py`
- `neuzelaar/document/styles.py`
- `neuzelaar/document/layout.py`
- `neuzelaar/render/display_builder.py`
- `neuzelaar/render/software.py`

Tasks:

- expand CSS support beyond tag/class/id plus descendant matching
- keep improving visual layout beyond simple stacked blocks
- add resource-budget controls for fetched passive assets

Acceptance:

- more styled fixtures render materially closer to author intent
- local passive assets stay policy-visible and budgeted
- tests cover the added CSS/rendering behavior

### P1: Claude Review Of Pipeline Shape

Owner: Claude

Files:

- `CLAUDE_TASKS.md`
- `chat/claude-to-codex.md`
- `neuzelaar/core/page.py`

Tasks:

- Review `PageLoader` and `PageLoadResult` shape.
- Confirm whether optional bus emission should wait until M2.
- Leave notes in `chat/claude-to-codex.md` or implement a small reviewed change.

Acceptance:

- Either "looks good for M1" note, or a small patch with tests.

## Completed Packages

- P1 Headless Core: done
- P2 Minimal Browser State: done
- P3 Visual Foundation: MVP baseline done, GUI smoke pending
- P4 Traditional Web Workflows: MVP baseline done
- P5 Tiny Styling Layer: MVP baseline done
- P6 Active Content Boundary: MVP baseline done
- P8 Post-MVP Browser State: done for current package scope

## M1 Completion Criteria

M1 is complete when all are checked:

- [x] `.venv/bin/pytest -q` passes.
- [x] `tools/check_guardrails.sh` passes.
- [x] `python -m neuzelaar tests/fixtures/sites/example.html` prints readable semantic text.
- [x] `python -m neuzelaar tests/fixtures/sites/third_party_script.html` reports the script blocked before fetch.
- [x] Browser pipeline is reusable outside `__main__.py`.
- [x] No GUI, CSS cascade, JS execution, image decode, forms, cookies, or history are required.
- [x] Final docs/smoke verification report exists.

## Completed M1 Work

- [x] Python package skeleton and `pyproject.toml`
- [x] local `.venv` workflow documented
- [x] command/event/frame/surface shell API contracts
- [x] synchronous `Bus`
- [x] URL/origin normalization and 1p/3p classification
- [x] `Request`, `Resource`, `FetchReason`, `TrustDecision`
- [x] `urllib`/file fetch client with byte cap and structured fetch errors
- [x] conservative MIME classifier
- [x] html5lib adapter into internal `Document`
- [x] internal DOM-like tree and tree walking
- [x] subresource planning for scripts/images/stylesheets/iframes
- [x] strict policy engine for top-level allow, tracker block, third-party script/iframe block
- [x] explicit handlers for HTML, text, image placeholder, and download fallback
- [x] text-only semantic renderer
- [x] reusable `PageLoader` / `PageLoadResult`
- [x] `HeadlessShell`
- [x] CLI path: `python -m neuzelaar <fixture>`
- [x] offline fixtures and smoke docs
- [x] guardrail script and pytest guardrail wrapper
- [x] M1-focused test suite
- [x] JS/WASM no-op active-content engines

## MVP Status

MVP code path is complete enough for internal testing:

- [x] open URL / local path
- [x] fetch top-level HTML
- [x] parse into internal document tree
- [x] semantic text rendering
- [x] links, headings, paragraphs, lists, image placeholders
- [x] simple forms
- [x] tiny CSS slice
- [x] navigation and history
- [x] GET/POST form submission
- [x] session cookies
- [x] strict third-party resource blocking
- [x] headless diagnostics
- [x] console shell
- [x] Tk visual frame path
- [x] software rasterization
- [ ] manual GUI smoke verification on a machine with a display

## Coordination Rules

- Commit small, coherent slices.
- Run `.venv/bin/pytest -q` before commits touching behavior.
- Run `tools/check_guardrails.sh` before commits touching architecture boundaries.
- Read relevant `chat/*-to-<you>.md` messages before starting.
- Do not edit or delete another agent's `chat/` messages.
- Do not revert another agent's changes; inspect and adapt.
- Codex and Claude are architecture/implementation leads.
- Gemini Flash focuses on testing, fixtures, smoke verification, GUI behavior checks, docs alignment, and bug reports.
- Antigravity can own bounded implementation or verification tasks when available.
