# Claude Task Notes

Claude and Codex are the main architecture/implementation leads for Neuzelaar 2.
Use this file as a handoff point when Claude is available again.

## Role

Claude should focus on hard design and implementation work:

- core architecture review
- page pipeline shape
- document model and handler boundaries
- policy/fetch correctness
- future layout/rendering abstractions
- code review of Codex implementation slices

Claude may edit core code, but should keep changes small and commit them with a
clear architectural rationale.

## Current High-Value Tasks

### 1. Review Page Pipeline Design

Context:

- `__main__.py` currently owns too much of the browser pipeline.
- `TODO.md` calls for `neuzelaar/core/page.py` or `neuzelaar/core/pipeline.py`.

Ask:

- Propose or implement a reusable page loading pipeline.
- Keep shell output separate from page-load decisions.
- Preserve the shell/core boundary.

Expected output:

- `PageLoadResult` or equivalent structured result.
- Tests that assert on structured decisions, not stdout parsing.
- `__main__.py` reduced to argument parsing and shell invocation.

### 2. Review Handler Boundary

Context:

- HTML/text handlers exist.
- Image/download handling is still mostly placeholder logic in the registry.

Ask:

- Make handler behavior explicit and safe.
- Confirm no third-party parser objects cross into core/document layers.
- Keep image decode deferred for M1.

### 3. Review Policy Semantics

Context:

- Strict policy blocks third-party scripts/iframes.
- Tracker host fragments are hardcoded.

Ask:

- Review whether `PolicyEngine.evaluate_fetch()` has enough context.
- Recommend fields needed before M2/M3, especially for cookies, forms, and external stylesheets.

## Before Starting

Run:

```sh
git status --short
git log --oneline -8
.venv/bin/pytest -q
tools/check_guardrails.sh
```

Read:

- `TODO.md`
- `PLAN.md`
- `concept_pub_talk.md`
- recent commits

## Handoff Format

After work, update or create `workdone-claude.md` with:

```text
# Work Done by Claude - YYYY-MM-DD

## Summary
- ...

## Files Changed
- ...

## Tests Run
- command: result

## Design Notes
- ...

## Risks / Follow-Ups
- ...
```

Commit important changes with small messages, for example:

```text
core: add reusable page load pipeline
review: document policy context gaps
```
