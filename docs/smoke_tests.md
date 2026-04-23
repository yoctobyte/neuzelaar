# Neuzelaar 2 Milestone 1 Smoke Tests

This document describes how to manually verify the Milestone 1 headless skeleton.

## Prerequisites

Ensure you have installed the project in editable mode:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run commands below from the repository root.

## 1. Local HTML Rendering

Verify that the browser can fetch, parse, and render a local HTML file into a semantic text dump.

**Command:**
```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
```

**Expected Output:**
- A first line like `200 file:///.../tests/fixtures/sites/example.html [html]`.
- A text dump starting with `# Example Fixture`.
- Content should include "Example Domain".

## 2. Link Extraction (Subresource Discovery)

Verify that the browser discovers subresources in the HTML.

**Command:**
```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/basic_links.html
```

**Expected Output:**
- Text dump showing the links and their URLs in `< >`.
- Output includes `External Link <https://example.com>`.
- Output includes `Relative Link <example.html>`.

## 3. Policy Blocking (Third-Party Scripts)

Verify that the browser correctly identifies and blocks third-party scripts before they are fetched.

**Command:**
```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

**Expected Output:**
- A first line like `200 file:///.../tests/fixtures/sites/third_party_script.html [html]`.
- A policy line containing `[block] script https://cdn.third-party.test/app.js`.
- The policy line says `strict mode blocks third-party scripts`.
- The script content should NOT be fetched.

## 4. Headless Shell Execution

Verify that the headless shell runs the full pipeline and exits cleanly.

**Command:**
```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/basic_lists.html
```

**Expected Output:**
- Clean exit (status 0).
- Readable list representation in the terminal.

## 5. Automated Suite

Verify the test suite and architectural guardrails.

**Command:**
```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
```

**Expected Output:**
- Pytest passes.
- Guardrails report no GUI imports in core/document/render.
- Guardrails report no leaked third-party library objects in core/document/shell_api.
- Guardrails report no tracked generated Python files.
