# Work Done by Gemini Flash - 2026-04-24

## Summary
- Ran standing test commands to verify M1 core health.
- Added 3 new offline HTML fixtures for deeper verification.
- Expanded unit test suite to cover nested rendering, script/style ignoring, subresource extraction, and URL resolution edge cases.
- Created `tools/setup.sh` for one-click "single venv per platform" environment preparation.
- Fixed a build-time package discovery issue in `pyproject.toml` where `chat/` was incorrectly identified as a package.
- Identified a crash bug in `PageLoader` when subresources fail to fetch (fixed by Codex in `a175d2f`).
- **Implemented safety limits across the pipeline** to prevent X11 BadAlloc crashes and runaway computation:
  - Rasterizer height cap (`MAX_RASTER_HEIGHT = 16,384`)
  - Layout item budget (`MAX_LAYOUT_ITEMS = 10,000`)
  - Tk pixmap cleanup (explicit deref before new allocation)
  - DOM node cap (`MAX_DOM_NODES = 20,000`) with tree truncation
  - Redirect enforcement via custom urllib opener (`max_redirects = 5`)
  - 4 unit tests covering all limits

## Commands Run
- `.venv/bin/pytest -q`: **PASS** (283 passed)
- `tools/check_guardrails.sh`: **PASS**
- `.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html`: **PASS**
- `.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html`: **PASS**

## Observed Behavior
- `nested_blocks.html`: Correctly rendered nested structure.
- `script_and_style_ignored.html`: Correctly omitted hidden content from text rendering.
- `stylesheet_link.html`: Now loads successfully (subresource fetch error is caught).

## Bugs Found
### Bug 1: X11 BadAlloc on large pages (FIXED)
- **Severity**: critical
- **Repro command**: `./neuzelaar-ui.sh https://slashdot.org/`
- **Root cause**: Software rasterizer created a full-height Pillow image and Tk converted it to an X11 pixmap, exhausting server memory.
- **Fix**: Clamped rasterizer output to 16,384px height + layout item budget + DOM node cap + pixmap cleanup.

## Files Changed
- `neuzelaar/render/software.py` [MODIFIED] — rasterizer height cap
- `neuzelaar/document/bfc.py` [MODIFIED] — layout item budget
- `neuzelaar/shells/tk/shell.py` [MODIFIED] — pixmap cleanup
- `neuzelaar/core/handlers/html_handler.py` [MODIFIED] — DOM node cap
- `neuzelaar/core/fetch/client.py` [MODIFIED] — redirect enforcement
- `tests/unit/test_safety_limits.py` [NEW] — safety limit tests

## Follow-Up Suggestions
- **Tiled rendering**: For future milestones, render only the visible viewport region instead of the full document height.
- **Memory monitoring**: Add a process-level memory watermark check before rasterization.

---

# Work Done by Gemini Flash - 2026-05-21

## Summary
- **Implemented `QuickJsTickedJavaScriptEngine`**: Exposed a host-ticked, ultra-high-performance QuickJS backend utilizing native QuickJS C bindings.
  - Implemented standard browser API shims in pure ES6/JS: global `console` forwarding, virtual DOM mirror, location and history properties, and setTimeout/setInterval event queue management.
  - Plugs directly into the central command/event bus and routes UI repaint triggers (`DomMutated`) for reactive rendering on script-driven page mutations.
  - Built ES6 `Proxy`-based styles and class listeners so that DOM node attribute/class/style changes dynamically bridge back to the host page DOM.
- **Enabled Swappable JS backend flag**:
  - Added `--js-engine quickjs-ticked` to CLI and UI launchers (`neuzelaar/viewer.py`) to let the user select between `noop`, `own-ticked` (standalone pure-Python engine), and `quickjs-ticked` (ultra-fast QuickJS).
- **Harkened test suite validation**:
  - Added full test suite `tests/unit/test_js_quickjs_ticked_engine.py` (9 tests) verifying sync execution, async `setTimeout`, recurrent `setInterval`, global scopes, `reset_for_page`, event-loop snapshots, and DOM mutation bridge behavior under QuickJS.
  - All 662 tests pass perfectly, and architectural guardrails remain fully intact.

## Commands Run
- `.venv/bin/pytest tests/unit/test_js_quickjs_ticked_engine.py`: **PASS** (9 passed)
- `.venv/bin/pytest`: **PASS** (662 passed)
- `tools/check_guardrails.sh`: **PASS**

## Files Changed
- `neuzelaar/engines/js/quickjs_engine.py` [MODIFIED] — Implemented ticked QuickJS engine wrapper
- `neuzelaar/viewer.py` [MODIFIED] — Registered `quickjs-ticked` CLI option
- `tests/unit/test_js_quickjs_ticked_engine.py` [NEW] — Tests for ticked QuickJS engine
- `workdone-gemini-flash.md` [MODIFIED] — Updated work done log
