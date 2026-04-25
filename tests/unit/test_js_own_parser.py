from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    ArrowFunctionExpr,
    BinaryExpr,
    BlockStatement,
    CallExpr,
    ClassDeclaration,
    ClassExpr,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NewExpr,
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


def test_parse_arrow_function_expressions() -> None:
    expr1 = parse_expression("x => x + 1")
    expr2 = parse_expression("(x, y) => { return x + y; }")

    assert isinstance(expr1, ArrowFunctionExpr)
    assert expr1.params == ("x",)
    assert isinstance(expr2, ArrowFunctionExpr)
    assert expr2.params == ("x", "y")


def test_parse_class_declaration_and_new_expression() -> None:
    program = parse_program(
        "class Point { constructor(x) { this.x = x; } getX() { return this.x; } }"
    )
    expr = parse_expression("new Point(1)")

    assert isinstance(program.statements[0], ClassDeclaration)
    assert program.statements[0].name == "Point"
    assert tuple(method.name for method in program.statements[0].methods) == ("constructor", "getX")
    assert isinstance(expr, NewExpr)
    assert isinstance(expr.callee, Identifier)


def test_parse_class_extends_clause() -> None:
    program = parse_program("class Child extends Parent { speak() { return super.speak(); } }")

    assert isinstance(program.statements[0], ClassDeclaration)
    assert isinstance(program.statements[0].superclass, Identifier)
    assert program.statements[0].superclass.name == "Parent"


def test_parse_class_expression_and_static_method() -> None:
    expr = parse_expression("class Named { static make() { return 1; } }")

    assert isinstance(expr, ClassExpr)
    assert expr.name == "Named"
    assert expr.methods[0].is_static is True


def test_parse_class_field() -> None:
    program = parse_program("class Point { x = 1; y; }")

    assert isinstance(program.statements[0], ClassDeclaration)
    assert tuple(field.name for field in program.statements[0].fields) == ("x", "y")


def test_parse_class_getter_and_setter() -> None:
    program = parse_program("class Box { get value() { return 1; } set value(x) { this.x = x; } }")

    assert isinstance(program.statements[0], ClassDeclaration)
    assert [method.accessor_kind for method in program.statements[0].methods] == ["get", "set"]


def test_parse_static_field() -> None:
    program = parse_program("class Box { static answer = 42; }")

    assert isinstance(program.statements[0], ClassDeclaration)
    assert program.statements[0].fields[0].is_static is True


def test_parse_computed_class_members() -> None:
    program = parse_program('class Box { ["x"]() { return 1; } [name] = 2; }')

    assert isinstance(program.statements[0], ClassDeclaration)
    assert program.statements[0].methods[0].key_expr is not None
    assert program.statements[0].fields[0].key_expr is not None
