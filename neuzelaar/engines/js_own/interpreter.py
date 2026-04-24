"""Evaluator for the standalone JS expression interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.ast import (
    BinaryExpr,
    BooleanLiteral,
    Expr,
    Identifier,
    NullLiteral,
    NumberLiteral,
    Program,
    StringLiteral,
    UnaryExpr,
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
    for expr in program.expressions:
        value = evaluate_expr(expr, env)
    return value


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
