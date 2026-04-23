# Neuzelaar 2

Neuzelaar 2 is a policy-first modular browser experiment. The current codebase
is in Milestone 1: headless skeleton and core contracts.

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
.venv/bin/pytest
```

### Running the Browser

The current Milestone 1 implementation is a headless skeleton. You can run it against local HTML fixtures:

```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
```

The initial implementation is intentionally small. CI-style tests should use
offline fixtures rather than live websites.

