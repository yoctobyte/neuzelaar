import pytest

from neuzelaar.engines.js_own.interpreter import evaluate_expression

quickjs = pytest.importorskip("quickjs")


CASES = [
    "1 + 2 * 3",
    '"a" + 2',
    '"2" == 2',
    '"2" === 2',
    "null + 2",
    '"" || "fallback"',
    '"left" && "right"',
    "!(1 < 2)",
]


@pytest.mark.parametrize("source", CASES)
def test_own_interpreter_matches_quickjs_for_js0_cases(source: str) -> None:
    context = quickjs.Context()
    actual = evaluate_expression(source)
    expected = context.eval(source)

    assert actual == expected
