# Neuzelaar 2

Neuzelaar 2 is a policy-first modular browser experiment. The current codebase
is in Milestone 1: headless skeleton and core contracts.

## Development

```sh
python -m pip install -e ".[dev]"
pytest
```

The initial implementation is intentionally small. CI-style tests should use
offline fixtures rather than live websites.
