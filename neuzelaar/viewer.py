"""Simple GUI entrypoint for the Tk viewer."""

from __future__ import annotations

import argparse

from neuzelaar.core.bus import Bus
from neuzelaar.core.session import BrowserSession
from neuzelaar.engines.js.interface import JavaScriptEngine
from neuzelaar.engines.js.noop import NoopJavaScriptEngine
from neuzelaar.engines.js.own_ticked_engine import OwnTickedJavaScriptEngine
from neuzelaar.shells.tk.shell import TkShell


def _build_js_engine(name: str, bus: Bus) -> JavaScriptEngine:
    if name == "noop":
        return NoopJavaScriptEngine()
    if name == "own-ticked":
        # No fixture: the loader will hand a real PageContext on every
        # navigation. The bus lets HostConsole forward log/warn/error
        # to the Tk JavaScript debug tab.
        return OwnTickedJavaScriptEngine(bus=bus)
    if name == "quickjs-ticked":
        from neuzelaar.engines.js.quickjs_engine import QuickJsTickedJavaScriptEngine
        return QuickJsTickedJavaScriptEngine(bus=bus)
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
        choices=("noop", "own-ticked", "quickjs-ticked"),
        default="noop",
        help="JavaScript engine to use. 'noop' (default) blocks all scripts; "
        "'own-ticked' runs the in-repo interpreter with host-driven ticks; "
        "'quickjs-ticked' runs QuickJS with host-driven ticks.",
    )
    args = parser.parse_args()

    bus = Bus()
    session = BrowserSession(bus=bus, js_engine=_build_js_engine(args.js_engine, bus))
    TkShell(
        session=session,
        width=args.width,
        height=args.height,
        verbose=args.verbose,
    ).run(args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
