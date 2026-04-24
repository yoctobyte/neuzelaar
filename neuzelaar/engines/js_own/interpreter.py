"""Evaluator for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    CallExpr,
    Expr,
    ExpressionStatement,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    Program,
    ReturnStatement,
    Stmt,
    StringLiteral,
    ThisExpr,
    UnaryExpr,
    VariableDeclaration,
)
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.parser import parse_expression as parse_expression_ast
from neuzelaar.engines.js_own.parser import parse_program as parse_program_ast
from neuzelaar.engines.js_own.runtime import (
    js_add,
    js_loose_equal,
    js_strict_equal,
    js_to_number,
    js_truthy,
)


class ReturnSignal(Exception):
    def __init__(self, value: object) -> None:
        super().__init__("return")
        self.value = value


class JavaScriptFunction:
    def __init__(
        self,
        *,
        name: str | None,
        params: tuple[str, ...],
        body: BlockStatement,
        closure: Environment,
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        call_env = Environment(parent=self.closure)
        call_env.declare("this", this_value, kind="const")
        if self.name is not None:
            call_env.declare(self.name, self, kind="const")
        for index, param in enumerate(self.params):
            value = arguments[index] if index < len(arguments) else None
            call_env.declare(param, value, kind="var")
        try:
            return evaluate_statement(self.body, call_env)
        except ReturnSignal as signal:
            return signal.value


def evaluate_expression(source: str, environment: Environment | None = None) -> object:
    env = environment or Environment()
    return evaluate_expr(parse_expression_ast(source), env)


def evaluate_program(source: str, environment: Environment | None = None) -> object:
    env = environment or Environment()
    program = parse_program_ast(source)
    return evaluate_ast_program(program, env)


def evaluate_ast_program(program: Program, environment: Environment | None = None) -> object:
    env = environment or Environment()
    value: object = None
    for statement in program.statements:
        value = evaluate_statement(statement, env)
    return value


def evaluate_statement(statement: Stmt, environment: Environment) -> object:
    if isinstance(statement, ExpressionStatement):
        return evaluate_expr(statement.expression, environment)
    if isinstance(statement, VariableDeclaration):
        value = None if statement.initializer is None else evaluate_expr(statement.initializer, environment)
        environment.declare(statement.name, value, kind=statement.kind)
        return value
    if isinstance(statement, FunctionDeclaration):
        function = JavaScriptFunction(
            name=statement.name,
            params=statement.params,
            body=statement.body,
            closure=environment,
        )
        environment.declare(statement.name, function, kind="var")
        return function
    if isinstance(statement, BlockStatement):
        block_env = environment.child_block()
        value: object = None
        for nested in statement.statements:
            value = evaluate_statement(nested, block_env)
        return value
    if isinstance(statement, IfStatement):
        if js_truthy(evaluate_expr(statement.test, environment)):
            return evaluate_statement(statement.consequent, environment)
        if statement.alternate is not None:
            return evaluate_statement(statement.alternate, environment)
        return None
    if isinstance(statement, ReturnStatement):
        value = None if statement.value is None else evaluate_expr(statement.value, environment)
        raise ReturnSignal(value)
    raise RuntimeError(f"Unsupported statement node: {type(statement).__name__}")


def evaluate_expr(expr: Expr, environment: Environment) -> object:
    if isinstance(expr, NumberLiteral):
        return expr.value
    if isinstance(expr, StringLiteral):
        return expr.value
    if isinstance(expr, BooleanLiteral):
        return expr.value
    if isinstance(expr, NullLiteral):
        return None
    if isinstance(expr, Identifier):
        return environment.get(expr.name)
    if isinstance(expr, ThisExpr):
        return environment.get("this")
    if isinstance(expr, FunctionExpr):
        function = JavaScriptFunction(
            name=expr.name,
            params=expr.params,
            body=expr.body,
            closure=environment,
        )
        return function
    if isinstance(expr, ArrayLiteral):
        return [evaluate_expr(element, environment) for element in expr.elements]
    if isinstance(expr, ObjectLiteral):
        return {
            prop.key: evaluate_expr(prop.value, environment)
            for prop in expr.properties
        }
    if isinstance(expr, UnaryExpr):
        operand = evaluate_expr(expr.operand, environment)
        if expr.operator == "!":
            return not js_truthy(operand)
        if expr.operator == "+":
            return js_to_number(operand)
        if expr.operator == "-":
            return -js_to_number(operand)
    if isinstance(expr, CallExpr):
        this_value = None
        if isinstance(expr.callee, MemberExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = _read_property(this_value, expr.callee.property_name)
        elif isinstance(expr.callee, IndexExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = _read_index(this_value, evaluate_expr(expr.callee.index, environment))
        else:
            callee = evaluate_expr(expr.callee, environment)
        if not isinstance(callee, JavaScriptFunction):
            raise TypeError("Value is not callable")
        arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
        return callee.call(arguments, this_value=this_value)
    if isinstance(expr, AssignmentExpr):
        value = evaluate_expr(expr.value, environment)
        if isinstance(expr.target, Identifier):
            return environment.assign(expr.target.name, value)
        if isinstance(expr.target, MemberExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            _write_property(target_object, expr.target.property_name, value)
            return value
        if isinstance(expr.target, IndexExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            index = evaluate_expr(expr.target.index, environment)
            _write_index(target_object, index, value)
            return value
        raise RuntimeError(f"Unsupported assignment target: {type(expr.target).__name__}")
    if isinstance(expr, MemberExpr):
        return _read_property(evaluate_expr(expr.object, environment), expr.property_name)
    if isinstance(expr, IndexExpr):
        return _read_index(
            evaluate_expr(expr.object, environment),
            evaluate_expr(expr.index, environment),
        )
    if isinstance(expr, BinaryExpr):
        if expr.operator == "&&":
            left = evaluate_expr(expr.left, environment)
            if not js_truthy(left):
                return left
            return evaluate_expr(expr.right, environment)
        if expr.operator == "||":
            left = evaluate_expr(expr.left, environment)
            if js_truthy(left):
                return left
            return evaluate_expr(expr.right, environment)
        left = evaluate_expr(expr.left, environment)
        right = evaluate_expr(expr.right, environment)
        if expr.operator == "+":
            return js_add(left, right)
        if expr.operator == "-":
            return js_to_number(left) - js_to_number(right)
        if expr.operator == "*":
            return js_to_number(left) * js_to_number(right)
        if expr.operator == "/":
            return js_to_number(left) / js_to_number(right)
        if expr.operator == "%":
            return js_to_number(left) % js_to_number(right)
        if expr.operator == "<":
            return js_to_number(left) < js_to_number(right)
        if expr.operator == ">":
            return js_to_number(left) > js_to_number(right)
        if expr.operator == "<=":
            return js_to_number(left) <= js_to_number(right)
        if expr.operator == ">=":
            return js_to_number(left) >= js_to_number(right)
        if expr.operator == "===":
            return js_strict_equal(left, right)
        if expr.operator == "!==":
            return not js_strict_equal(left, right)
        if expr.operator == "==":
            return js_loose_equal(left, right)
        if expr.operator == "!=":
            return not js_loose_equal(left, right)
    raise RuntimeError(f"Unsupported expression node: {type(expr).__name__}")


def _read_property(target: object, property_name: str) -> object:
    if isinstance(target, dict):
        return target.get(property_name)
    if isinstance(target, list) and property_name == "length":
        return float(len(target))
    raise TypeError(f"Cannot read property {property_name!r}")


def _read_index(target: object, index: object) -> object:
    if isinstance(target, list):
        resolved = _to_index(index)
        return target[resolved]
    if isinstance(target, dict):
        return target.get(str(index))
    raise TypeError("Cannot index value")


def _write_property(target: object, property_name: str, value: object) -> None:
    if isinstance(target, dict):
        target[property_name] = value
        return
    raise TypeError(f"Cannot write property {property_name!r}")


def _write_index(target: object, index: object, value: object) -> None:
    if isinstance(target, list):
        resolved = _to_index(index)
        target[resolved] = value
        return
    if isinstance(target, dict):
        target[str(index)] = value
        return
    raise TypeError("Cannot index-assign value")


def _to_index(value: object) -> int:
    if isinstance(value, float):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(float(value))
    raise TypeError("Invalid index")
