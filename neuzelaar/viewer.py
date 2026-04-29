"""Simple GUI entrypoint for the Tk viewer."""

from __future__ import annotations

import argparse

from neuzelaar.core.session import BrowserSession
from neuzelaar.engines.js.interface import JavaScriptEngine
from neuzelaar.engines.js.noop import NoopJavaScriptEngine
from neuzelaar.engines.js.own_ticked_engine import OwnTickedJavaScriptEngine
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture
from neuzelaar.shells.tk.shell import TkShell


def _build_js_engine(name: str) -> JavaScriptEngine:
    if name == "noop":
        return NoopJavaScriptEngine()
    if name == "own-ticked":
        # Plain fixture: no canned DOM nodes, but installs the host
        # stubs so setTimeout / setInterval / console exist as globals.
        return OwnTickedJavaScriptEngine(scenario_fixture=BrowserScenarioFixture())
    raise ValueError(f"Unknown --js-engine value: {name!r}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m neuzelaar.viewer")
    parser.add_argument("url", nargs="?", default="example.com", help="URL or local path to open")
    parser.add_argument("--width", type=int, default=1200, help="Initial viewport width")
    parser.add_argument("--height", type=int, default=800, help="Initial viewport height")
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Print page-load phase markers with elapsed-ms timestamps to stderr",
    )
    parser.add_argument(
        "--js-engine",
        choices=("noop", "own-ticked"),
        default="noop",
        help="JavaScript engine to use. 'noop' (default) blocks all scripts; "
        "'own-ticked' runs the in-repo interpreter with host-driven ticks.",
    )
    args = parser.parse_args()

    session = BrowserSession(js_engine=_build_js_engine(args.js_engine))
    TkShell(
        session=session,
        width=args.width,
        height=args.height,
        verbose=args.verbose,
    ).run(args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
