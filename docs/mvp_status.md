# MVP Status

The MVP code path is implemented for internal testing.

Implemented:

- top-level page loading
- conservative MIME classification
- HTML parsing through an adapter
- internal document model
- semantic text renderer
- link extraction and following
- in-memory history
- session-only cookies
- planned subresource policy decisions
- strict third-party resource blocking
- form extraction
- GET and POST form submission
- local fixture-server form flow
- tiny CSS model for inline styles and style blocks
- display list generation
- Pillow-backed software rasterization into neutral `Frame`
- Tk viewer with split debug/browser panes, address bar, back/forward/reload, and scrolling
- console shell commands
- JS/WASM no-op blocked engines
- guardrail tests

Verification:

```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

Current result:

- 80 tests pass.
- Guardrails pass.
- CLI smoke tests pass.

Manual verification still needed:

- Open the Tk shell on a machine with a working display.
- Confirm a fixture page is visible.
- Confirm scrolling works on a page taller than the viewport.
- Confirm no obvious text overlap in the simple fixtures.

Known MVP limits:

- CSS is intentionally tiny.
- Image decoding is metadata-only for now; visual rendering still uses placeholders.
- No JavaScript execution.
- No WASM execution.
- No multi-tab UI.
- No full accessibility layer.
