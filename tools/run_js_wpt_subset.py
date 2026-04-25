#!/usr/bin/env python3
"""Run a tiny curated WPT-oriented subset against the local standalone runtime."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuzelaar.engines.js.wpt import load_case, run_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine",
        default="own",
        help="Engine name: own or quickjs",
    )
    parser.add_argument(
        "--manifest",
        default="tests/fixtures/js/wpt_subset.txt",
        help="Path to a newline-separated manifest of local WPT-style fixture files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest)
    case_paths = [
        Path(line.strip())
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    cases = [load_case(path) for path in case_paths]
    summary = run_cases(cases, engine=args.engine)
    print(f"{summary.engine}: {summary.passed} passed, {summary.failed} failed, {summary.total} total")
    for outcome in summary.outcomes:
        marker = "PASS" if outcome.status == "passed" else "FAIL"
        print(f"{marker} {outcome.case.display_name}: {outcome.reason}")
        for test_result in outcome.test_results:
            test_marker = "PASS" if test_result.status == "PASS" else "FAIL"
            suffix = f": {test_result.message}" if test_result.message else ""
            print(f"  {test_marker} {test_result.name}{suffix}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
