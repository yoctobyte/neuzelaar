from neuzelaar.engines.js_own.ast import BinaryExpr, Identifier, NumberLiteral, UnaryExpr
from neuzelaar.engines.js_own.parser import parse_expression, parse_program


def test_parse_expression_obeys_operator_precedence() -> None:
    expr = parse_expression("1 + 2 * 3")

    assert isinstance(expr, BinaryExpr)
    assert expr.operator == "+"
    assert isinstance(expr.left, NumberLiteral)
    assert isinstance(expr.right, BinaryExpr)
    assert expr.right.operator == "*"


def test_parse_expression_handles_grouping_and_unary() -> None:
    expr = parse_expression("-(a + 2)")

    assert isinstance(expr, UnaryExpr)
    assert expr.operator == "-"
    assert isinstance(expr.operand, BinaryExpr)
    assert isinstance(expr.operand.left, Identifier)


def test_parse_program_handles_expression_sequence() -> None:
    program = parse_program("1 + 2; 3 + 4;")

    assert len(program.expressions) == 2
