from pathlib import Path

import pytest

from neuzelaar.engines.js.wpt import load_case, run_case, run_cases


def test_run_single_wpt_case_passes() -> None:
    case = load_case("tests/fixtures/js/wpt/microtask-before-timeout.js")

    outcome = run_case(case)

    assert outcome.status == "passed"
    assert len(outcome.test_results) == 1
    assert outcome.test_results[0].status == "PASS"


def test_run_wpt_subset_manifest_passes() -> None:
    manifest = Path("tests/fixtures/js/wpt_subset.txt")
    cases = [
        load_case(line.strip())
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    summary = run_cases(cases)

    assert summary.failed == 0
    assert summary.passed == 4


@pytest.mark.skipif(__import__("importlib").util.find_spec("quickjs") is None, reason="quickjs not installed")
def test_run_wpt_subset_manifest_passes_on_quickjs() -> None:
    manifest = Path("tests/fixtures/js/wpt_subset.txt")
    cases = [
        load_case(line.strip())
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    summary = run_cases(cases, engine="quickjs")

    assert summary.failed == 0
    assert summary.passed == 4
