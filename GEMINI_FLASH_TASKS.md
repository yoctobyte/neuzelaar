# Gemini Flash Task Notes

These are low-risk tasks suitable for Gemini Flash while Codex continues core
implementation. Avoid editing core behavior unless explicitly reassigned.

## Safe Tasks

1. Expand README development notes:
   - Explain `.venv` setup.
   - Show `.venv/bin/pytest`.
   - Show `.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html`.

2. Add more offline HTML fixtures under `tests/fixtures/sites/`:
   - `basic_links.html`
   - `basic_lists.html`
   - `basic_images.html`
   Keep them tiny and hand-written.

3. Add fixture documentation:
   - Create `tests/fixtures/README.md`.
   - State fixtures must be offline, stable, and small.

4. Check for stale generated files:
   - Run `git status --short`.
   - Do not commit `.venv`, `__pycache__`, or `.pytest_cache`.

## Do Not Touch For Now

- `neuzelaar/core/`
- `neuzelaar/document/`
- `neuzelaar/engines/`
- `neuzelaar/render/`
- `PLAN.md`

If a trivial task seems to require touching those areas, leave a note instead
of changing code.
