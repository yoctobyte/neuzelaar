import math

import pytest

from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.errors import JavaScriptReferenceError, JavaScriptSyntaxError
from neuzelaar.engines.js_own.interpreter import evaluate_expression, evaluate_program


def test_evaluate_numeric_precedence() -> None:
    assert evaluate_expression("1 + 2 * 3") == 7.0


def test_evaluate_string_concatenation() -> None:
    assert evaluate_expression('"a" + 2') == "a2"


def test_evaluate_unary_and_comparison() -> None:
    assert evaluate_expression("!(1 < 2)") is False


def test_evaluate_loose_and_strict_equality() -> None:
    assert evaluate_expression('"2" == 2') is True
    assert evaluate_expression('"2" === 2') is False


def test_evaluate_logical_short_circuit_returns_operand() -> None:
    assert evaluate_expression('"" || "fallback"') == "fallback"
    assert evaluate_expression('"left" && "right"') == "right"


def test_evaluate_null_and_number_coercion() -> None:
    assert evaluate_expression("null + 2") == 2.0
    value = evaluate_expression('"abc" - 1')
    assert isinstance(value, float)
    assert math.isnan(value)


def test_evaluate_identifier_lookup() -> None:
    env = Environment(values={"x": 4.0, "y": 5.0})

    assert evaluate_expression("x * y", env) == 20.0


def test_evaluate_program_returns_last_expression_value() -> None:
    assert evaluate_program('1 + 2; "x" + 1;') == "x1"


def test_unknown_identifier_raises_reference_error() -> None:
    with pytest.raises(JavaScriptReferenceError):
        evaluate_expression("missing")


def test_var_declaration_and_assignment_work() -> None:
    env = Environment()

    result = evaluate_program("var x = 1; x = x + 2; x;", env)

    assert result == 3.0
    assert env.get("x") == 3.0


def test_let_is_block_scoped() -> None:
    env = Environment()

    result = evaluate_program("let x = 1; { let x = 2; x; } x;", env)

    assert result == 1.0
    assert env.get("x") == 1.0


def test_var_declared_in_block_escapes_to_var_scope() -> None:
    env = Environment()

    result = evaluate_program("{ var x = 4; } x;", env)

    assert result == 4.0
    assert env.get("x") == 4.0


def test_const_requires_initializer() -> None:
    with pytest.raises(JavaScriptSyntaxError):
        evaluate_program("const x;")


def test_const_assignment_raises() -> None:
    with pytest.raises(TypeError):
        evaluate_program("const x = 1; x = 2;")


def test_if_statement_selects_correct_branch() -> None:
    assert evaluate_program('if (false) { "a"; } else { "b"; }') == "b"


def test_if_without_else_can_mutate_existing_binding() -> None:
    env = Environment(values={"x": 0.0})

    result = evaluate_program("if (1) x = 9; x;", env)

    assert result == 9.0


def test_function_declaration_call_works() -> None:
    result = evaluate_program("function add(a, b) { return a + b; } add(2, 3);")

    assert result == 5.0


def test_function_expression_call_works() -> None:
    result = evaluate_program("(function (x) { return x + 1; })(2);")

    assert result == 3.0


def test_closure_captures_outer_binding() -> None:
    result = evaluate_program(
        "function outer(x) { function inner(y) { return x + y; } return inner; } "
        "var add2 = outer(2); add2(3);"
    )

    assert result == 5.0


def test_recursive_named_function_works() -> None:
    result = evaluate_program(
        "function fact(n) { if (n === 0) { return 1; } return n * fact(n - 1); } fact(5);"
    )

    assert result == 120.0


def test_return_without_value_produces_nullish_python_none() -> None:
    result = evaluate_program("function f() { return; } f();")

    assert result is None


def test_calling_non_callable_raises() -> None:
    with pytest.raises(TypeError):
        evaluate_program("var x = 1; x();")
