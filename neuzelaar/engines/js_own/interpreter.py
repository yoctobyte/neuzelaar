"""Evaluator for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.ast import (
    AssignmentExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    Expr,
    ExpressionStatement,
    Identifier,
    IfStatement,
    NullLiteral,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
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
    if isinstance(expr, UnaryExpr):
        operand = evaluate_expr(expr.operand, environment)
        if expr.operator == "!":
            return not js_truthy(operand)
        if expr.operator == "+":
            return js_to_number(operand)
        if expr.operator == "-":
            return -js_to_number(operand)
    if isinstance(expr, AssignmentExpr):
        value = evaluate_expr(expr.value, environment)
        return environment.assign(expr.target.name, value)
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
