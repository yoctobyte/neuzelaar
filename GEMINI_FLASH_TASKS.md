# Gemini Flash Task Notes

These are low-risk tasks suitable for Gemini Flash while Codex continues core
implementation. Avoid editing core behavior unless explicitly reassigned.

## Safe Tasks

1. Expand README development notes: [DONE]
   - Explain `.venv` setup.
   - Show `.venv/bin/pytest`.
   - Show `.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html`.

2. Add more offline HTML fixtures under `tests/fixtures/sites/`:
   - `basic_links.html` [DONE]
   - `basic_lists.html` [DONE]
   - `basic_images.html` [DONE]
   Keep them tiny and hand-written.

3. Add fixture documentation: [DONE]
   - Create `tests/fixtures/README.md`.
   - State fixtures must be offline, stable, and small.

4. Check for stale generated files: [DONE]
   - Run `git status --short`.
   - Do not commit `.venv`, `__pycache__`, or `.pytest_cache`.

5. [NEW - Approved by USER 2026-04-23] Architectural Guardrail Script: [DONE]
   - Create `tools/check_guardrails.sh`.
   - Check core for GUI imports and leaked library objects.

6. [NEW - Approved by USER 2026-04-23] Contract Docstring Audit: [DONE]
   - Add/verify docstrings in `neuzelaar/` modules stating responsibilities.

7. [NEW - Approved by USER 2026-04-23] Integration Test Alignment: [DONE]
   - Ensure `tests/integration/` matches the M1 naming/scope in `PLAN.md`.

8. [NEW - Approved by USER 2026-04-23] Smoke Test Documentation: [DONE]
   - Create `docs/smoke_tests.md` for manual M1 verification.

## Do Not Touch For Now

- `neuzelaar/core/`
- `neuzelaar/document/`
- `neuzelaar/engines/`
- `neuzelaar/render/`
- `PLAN.md`

If a trivial task seems to require touching those areas, leave a note instead
of changing code.
