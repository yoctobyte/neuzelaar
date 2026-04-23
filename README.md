# Neuzelaar 2

Neuzelaar 2 is a policy-first modular browser experiment. Milestone 1 is the
headless skeleton: fetch a local page, classify it, parse it, render semantic
text, and report blocked planned subresources.

## Development

### Setup

It is recommended to use a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
python -m pip install -e ".[dev]"
```

### Running Tests

Run tests using the virtual environment's pytest:

```sh
.venv/bin/pytest -q
tools/check_guardrails.sh
```

### Running the Browser

The current Milestone 1 implementation is a headless skeleton. You can run it against local HTML fixtures:

```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

The initial implementation is intentionally small. CI-style tests should use
offline fixtures rather than live websites.
