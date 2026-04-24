from neuzelaar.engines.js_own.ast import (
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    Identifier,
    IfStatement,
    NumberLiteral,
    UnaryExpr,
    VariableDeclaration,
)
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

    assert len(program.statements) == 2


def test_parse_assignment_expression() -> None:
    expr = parse_expression("x = 3")

    assert isinstance(expr, AssignmentExpr)
    assert expr.target.name == "x"


def test_parse_variable_declaration_and_if_block() -> None:
    program = parse_program("let x = 1; if (x) { const y = 2; }")

    assert isinstance(program.statements[0], VariableDeclaration)
    assert isinstance(program.statements[1], IfStatement)
    assert isinstance(program.statements[1].consequent, BlockStatement)
