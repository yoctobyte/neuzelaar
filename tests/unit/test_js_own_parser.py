from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    CallExpr,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NumberLiteral,
    ObjectLiteral,
    ReturnStatement,
    ThrowStatement,
    ThisExpr,
    TryStatement,
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


def test_parse_function_declaration_and_return() -> None:
    program = parse_program("function add(a, b) { return a + b; }")

    assert isinstance(program.statements[0], FunctionDeclaration)
    assert program.statements[0].params == ("a", "b")
    assert isinstance(program.statements[0].body.statements[0], ReturnStatement)


def test_parse_function_expression_call() -> None:
    expr = parse_expression("(function (x) { return x; })(1)")

    assert isinstance(expr, CallExpr)
    assert isinstance(expr.callee, FunctionExpr)


def test_parse_array_object_member_and_index_expressions() -> None:
    array_expr = parse_expression("[1, 2, 3]")
    object_expr = parse_expression('{ x: 1, "y": 2 }')
    member_expr = parse_expression("obj.value")
    index_expr = parse_expression("arr[1]")
    this_expr = parse_expression("this")

    assert isinstance(array_expr, ArrayLiteral)
    assert isinstance(object_expr, ObjectLiteral)
    assert isinstance(member_expr, MemberExpr)
    assert isinstance(index_expr, IndexExpr)
    assert isinstance(this_expr, ThisExpr)


def test_parse_throw_and_try_statement() -> None:
    program = parse_program('try { throw "x"; } catch (e) { e; } finally { 1; }')

    assert isinstance(program.statements[0], TryStatement)
    assert isinstance(program.statements[0].body.statements[0], ThrowStatement)
