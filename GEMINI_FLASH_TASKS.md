# Gemini Flash Task Notes

Gemini Flash is most useful as the testing, verification, fixture, docs, and GUI
behavior agent. Codex and Claude are the primary architecture/implementation
leads; Gemini Flash should amplify them by finding regressions, checking user
behavior, expanding fixtures, and reporting clearly.

Avoid editing core behavior unless explicitly reassigned.

## Standing Test Commands

Run these after pulling latest changes:

```sh
git status --short
git log --oneline -5
.venv/bin/pytest -q
tools/check_guardrails.sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

Expected today:

- pytest passes.
- guardrails pass.
- `example.html` prints readable semantic text.
- `third_party_script.html` prints a `[block] script ...` line.

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

9. Test Report Pass: [DONE]
   - Run the standing test commands.
   - Create or update `workdone-gemini-flash.md`.
   - Report exact commands, pass/fail, stdout snippets for CLI behavior, and any suspected bug.

10. Fixture Expansion: [DONE]
   - Add small offline fixtures only under `tests/fixtures/sites/`.
   - Good candidates: `nested_blocks.html`, `script_and_style_ignored.html`, `stylesheet_link.html`.
   - If adding fixtures, add or request tests that use them.

11. GUI Behavior Verification Later:
   - When M3 visual shell exists, run manual GUI smoke tests.
   - Check window opens, text is visible, scrolling works, no overlap in basic fixtures.
   - Take notes in `workdone-gemini-flash.md`; screenshots are useful if available.

12. Unit Test Expansion: [DONE]
   - Expand `tests/unit/` to cover new fixtures and edge cases.
   - Verify `text_only` rendering of nested blocks and hidden tags.
   - Verify `subresources` extraction from real fixtures.
   - Add URL resolution edge cases to `test_origin`.

13. Single Venv Setup Tool: [DONE]
   - Create `tools/setup.sh` to bootstrap a single platform-native venv.
   - Fix `pyproject.toml` package discovery.
   - Ensure the script runs guardrails and provides clear usage instructions.

## Report Format

Use this exact shape in `workdone-gemini-flash.md`:

```text
# Work Done by Gemini Flash - YYYY-MM-DD

## Summary
- ...

## Commands Run
- `.venv/bin/pytest -q`: PASS/FAIL
- `tools/check_guardrails.sh`: PASS/FAIL
- `.venv/bin/python -m neuzelaar ...`: PASS/FAIL

## Observed Behavior
- ...

## Bugs Found
- Severity: high/medium/low
- Repro command:
- Expected:
- Actual:
- Suspected area:

## Files Changed
- ...

## Follow-Up Suggestions
- ...
```

## Do Not Touch For Now

- `neuzelaar/core/`
- `neuzelaar/document/`
- `neuzelaar/engines/`
- `neuzelaar/render/`
- `PLAN.md`

If a trivial task seems to require touching those areas, leave a note instead
of changing code.
