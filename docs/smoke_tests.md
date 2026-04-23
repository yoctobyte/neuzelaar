# Neuzelaar 2 Milestone 1 Smoke Tests

This document describes how to manually verify the functionality of the Milestone 1 "headless skeleton".

## Prerequisites

Ensure you have installed the project in editable mode:

```sh
python -m pip install -e ".[dev]"
```

## 1. Local HTML Rendering

Verify that the browser can fetch, parse, and render a local HTML file into a semantic text dump.

**Command:**
```sh
python -m neuzelaar tests/fixtures/sites/example.html
```

**Expected Output:**
- Logs showing the fetch request for the local file.
- Logs showing MIME classification as `text/html`.
- A text dump starting with `# Example Fixture`.
- Content should include "Example Domain".

## 2. Link Extraction (Subresource Discovery)

Verify that the browser discovers subresources in the HTML.

**Command:**
```sh
python -m neuzelaar tests/fixtures/sites/basic_links.html
```

**Expected Output:**
- Text dump showing the links and their URLs in `< >`.

## 3. Policy Blocking (Third-Party Scripts)

Verify that the browser correctly identifies and blocks third-party scripts before they are fetched.

**Command:**
```sh
python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

**Expected Output:**
- Logs showing that the third-party script was discovered.
- Logs showing a `BLOCK` decision for the script fetch.
- The script content should NOT be fetched.

## 4. Headless Shell Execution

Verify that the headless shell runs the full pipeline and exits cleanly.

**Command:**
```sh
python -m neuzelaar tests/fixtures/sites/basic_lists.html
```

**Expected Output:**
- Clean exit (status 0).
- Readable list representation in the terminal.
