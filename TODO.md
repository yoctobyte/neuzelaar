# Neuzelaar 2 TODO

Day-to-day execution tracker. `PLAN.md` is the architecture reference;
`*_TASKS.md` files define agent roles; `chat/` is async agent messaging.

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

## Active Backlog

### P0: Final M1 Docs And Smoke Verification

Owner: Gemini Flash

Status: DONE

Files:

- `README.md`
- `docs/smoke_tests.md`
- `workdone-gemini-flash.md` or `workdone.md`

Tasks:

- Run the standing test commands from `GEMINI_FLASH_TASKS.md`.
- Confirm README commands match current reality.
- Confirm smoke docs reflect current CLI output.
- Report exact commands and pass/fail results.

Acceptance:

- [x] pytest passes.
- [x] guardrails pass.
- [x] CLI smoke commands match documented expectations.
- [x] No core code edited.

### P1: M1 Completion Tag/Note

Owner: Codex

Status: DONE

Tasks:

- Review Gemini Flash verification report.
- If clean, mark M1 complete in this file and optionally add a short `docs/milestone_1.md`.
- Commit the milestone note.

Acceptance:

- [x] M1 criteria below are all checked.
- [x] No hidden uncommitted changes.

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

## M2 Path: Minimal Document Browser

Theme: make headless/console browsing feel like a small browser, not a one-shot parser.

Work:

- [x] in-memory session and single-tab page state
- [x] navigation history
- [x] link following by URL or link index in console mode
- [x] session-only cookie jar
- [x] console shell commands: `open`, `back`, `forward`, `links`, `resources`, `quit`
- [x] page summary: title, URL, links, blocked resources
- [x] optional bus events from `PageLoader`: load started/finished/failed/resource blocked

Acceptance:

- User can open a fixture page, list links, follow one, go back, and inspect blocked resources.
- No GUI yet.

## M3 Path: Basic Visual Browser

Theme: first actual viewport.

Work:

- [x] lock Tk as first shell unless explicitly changed
- [x] software frame generation and neutral `Frame` presentation
- [x] display list types
- [x] basic block/inline/text layout
- [x] decoded images via Pillow adapter
- scroll support
- [x] tiny CSS slice: inline styles, `<style>`, limited properties

Acceptance:

- A blog/docs fixture renders readably in a window.
- [x] Shell remains thin and imports no core internals beyond shell API.
- Rendering can still be tested headlessly.
- Gemini Flash verifies GUI behavior with screenshots/notes when available.

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

## M4b Path: Persistence And Tabs

Theme: browser state.

Work:

- persistent cookie jar
- multi-tab model
- per-tab history
- tab/session isolation tests

Acceptance:

- Two tabs can hold independent state and history.

## M5 Path: Styling And Policy Maturity

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

- JS engine integration point
- capability bridge
- permission events/prompts
- no-op/stub engine that logs blocked or requested capabilities
- inline script planning alongside `<script src>` planning

Acceptance:

- JS-heavy fixture produces a useful capability/block report without executing JS.

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
