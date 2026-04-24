# Neuzelaar 2

Neuzelaar 2 is a policy-first modular browser experiment. Milestone 1 is the
headless skeleton: fetch a local page, classify it, parse it, render semantic
text, and report blocked planned subresources.

## Development

### Setup

Prepare the environment using the setup script:

```sh
chmod +x tools/setup.sh
./tools/setup.sh
```

This will create a virtual environment (`.venv`), install dependencies, and run architectural guardrails.

To activate the environment:

```sh
source .venv/bin/activate
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
./neuzelaar.sh tests/fixtures/sites/example.html
./neuzelaar.sh tests/fixtures/sites/third_party_script.html
```

The launcher will create or repair `.venv` via `tools/setup.sh` if needed, then run `python -m neuzelaar`.

Direct invocation still works:

```sh
.venv/bin/python -m neuzelaar tests/fixtures/sites/example.html
.venv/bin/python -m neuzelaar tests/fixtures/sites/third_party_script.html
```

To launch the Tk viewer:

```sh
./neuzelaar-ui.sh
./neuzelaar-ui.sh tests/fixtures/sites/example.html
./neuzelaar-ui.sh https://msn.com
```

The UI launcher uses the same local `.venv` bootstrap behavior and runs `python -m neuzelaar.viewer`.
If no URL is provided, it starts at `https://example.com`.

The viewer currently has:

- a browser pane with one tab, address bar, back/forward, reload, and scrolling
- a debug pane with DOM tree, HTML source, and request diagnostics
- automatic UI error capture in the debug pane and on disk

Address bar behavior:

- plain hostnames like `msn.com` default to `https://`
- local paths still open as local files

Error handling:

- viewer errors still print to stderr
- the latest UI error is also written to:
  - `.neuzelaar/logs/latest.log`
  - `.neuzelaar/logs/ui-error-*.log`
- the left-side `Errors` tab shows the latest captured report

The M2 console shell can also be used from Python:

```sh
.venv/bin/python -q
```

```python
from neuzelaar.shells.console.shell import ConsoleShell

shell = ConsoleShell()
print(shell.run_command("open tests/fixtures/sites/basic_links.html"))
print(shell.run_command("links"))
print(shell.run_command("follow 2"))
print(shell.run_command("back"))
```

The initial implementation is intentionally small. CI-style tests should use
offline fixtures rather than live websites.
