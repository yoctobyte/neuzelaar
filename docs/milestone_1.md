# Milestone 1 Complete

Milestone 1 establishes the headless browser skeleton.

Completed behavior:

- fetch local HTML fixtures
- classify MIME conservatively
- parse HTML through an adapter into internal document nodes
- render semantic text
- plan subresource fetches before network access
- block third-party scripts under strict policy before fetch
- expose reusable `PageLoader` and `HeadlessShell`
- provide no-op JS and WASM engines
- verify architecture guardrails through tests

Verification:

```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

Result on 2026-04-23:

- 42 tests passed.
- Guardrails passed.
- CLI smoke tests passed.

Deferred by design:

- GUI
- CSS cascade
- image decoding
- JavaScript execution
- WASM execution
- forms
- cookies
- history
