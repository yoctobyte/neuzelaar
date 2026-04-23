"""Command line entry point for early Neuzelaar milestones."""

from __future__ import annotations

import argparse

from neuzelaar.shells.headless.shell import HeadlessShell


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m neuzelaar")
    parser.add_argument("url", help="URL or local path to fetch")
    args = parser.parse_args()

    shell = HeadlessShell()
    print(shell.format_result(shell.open_url(args.url)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
