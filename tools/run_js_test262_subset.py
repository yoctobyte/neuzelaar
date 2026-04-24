#!/usr/bin/env python3
"""Run a small curated Test262 subset against a configured JS backend."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuzelaar.engines.js.factory import EngineUnavailableError, create_javascript_engine, engine_specs
from neuzelaar.engines.js.test262 import load_case, run_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--engine",
        default="noop",
        help="JS engine name: " + ", ".join(spec.name for spec in engine_specs()),
    )
    parser.add_argument(
        "--manifest",
        default="tests/fixtures/js/test262_subset.txt",
        help="Path to a newline-separated manifest of Test262 files.",
    )
    parser.add_argument(
        "--test262-root",
        default=".cache/test262",
        help="Path to a local tc39/test262 checkout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        engine = create_javascript_engine(args.engine)
    except EngineUnavailableError as exc:
        print(f"engine unavailable: {exc}", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    test262_root = Path(args.test262_root)
    case_paths = [
        test262_root / line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    cases = [load_case(path) for path in case_paths]
    summary = run_cases(engine, cases)
    print(
        f"{summary.engine_name}: {summary.passed} passed, "
        f"{summary.failed} failed, {summary.skipped} skipped, {summary.total} total"
    )
    for outcome in summary.outcomes:
        marker = {
            "passed": "PASS",
            "failed": "FAIL",
            "skipped": "SKIP",
        }[outcome.status]
        print(f"{marker} {outcome.case.display_name}: {outcome.reason}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
