import pytest

from neuzelaar.engines.js_own.interpreter import evaluate_program

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
    "var x = 1; x = x + 2; x;",
    "let x = 1; { let x = 2; x; } x;",
    "{ var x = 4; } x;",
    'if (false) { "a"; } else { "b"; }',
]


@pytest.mark.parametrize("source", CASES)
def test_own_interpreter_matches_quickjs_for_supported_cases(source: str) -> None:
    context = quickjs.Context()
    actual = evaluate_program(source)
    expected = context.eval(source)

    assert actual == expected
