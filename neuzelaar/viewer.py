"""Simple GUI entrypoint for the Tk viewer."""

from __future__ import annotations

import argparse

from neuzelaar.shells.tk.shell import TkShell


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
    args = parser.parse_args()

    TkShell(width=args.width, height=args.height, verbose=args.verbose).run(args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
