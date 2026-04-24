"""Evaluator for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.errors import JavaScriptThrownValue
from neuzelaar.engines.js_own.host import HostCallable
from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    ArrowFunctionExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    CallExpr,
    ClassDeclaration,
    ClassMethod,
    Expr,
    ExpressionStatement,
    FunctionDeclaration,
    FunctionExpr,
    Identifier,
    IndexExpr,
    IfStatement,
    MemberExpr,
    NewExpr,
    NullLiteral,
    NumberLiteral,
    ObjectLiteral,
    Program,
    ReturnStatement,
    Stmt,
    StringLiteral,
    ThisExpr,
    ThrowStatement,
    TryStatement,
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
from neuzelaar.engines.js_own.values import (
    is_callable,
    read_index,
    read_property,
    write_index,
    write_property,
)


class ReturnSignal(Exception):
    def __init__(self, value: object) -> None:
        super().__init__("return")
        self.value = value


class ThrowSignal(Exception):
    def __init__(self, value: object) -> None:
        super().__init__("throw")
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


class JavaScriptArrowFunction:
    def __init__(
        self,
        *,
        params: tuple[str, ...],
        body: BlockStatement | Expr,
        closure: Environment,
        lexical_this: object,
    ) -> None:
        self.params = params
        self.body = body
        self.closure = closure
        self.lexical_this = lexical_this

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        call_env = Environment(parent=self.closure)
        call_env.declare("this", self.lexical_this, kind="const")
        for index, param in enumerate(self.params):
            value = arguments[index] if index < len(arguments) else None
            call_env.declare(param, value, kind="var")
        if isinstance(self.body, BlockStatement):
            try:
                return evaluate_statement(self.body, call_env)
            except ReturnSignal as signal:
                return signal.value
        return evaluate_expr(self.body, call_env)


class JavaScriptClass:
    def __init__(
        self,
        *,
        name: str,
        methods: tuple[ClassMethod, ...],
        closure: Environment,
    ) -> None:
        self.name = name
        self.prototype: dict[str, object] = {}
        self.constructor: JavaScriptFunction | None = None
        for method in methods:
            function = JavaScriptFunction(
                name=method.name,
                params=method.params,
                body=method.body,
                closure=closure,
            )
            if method.name == "constructor":
                self.constructor = function
            else:
                self.prototype[method.name] = function

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        instance: dict[str, object] = {"__proto__": self.prototype}
        if self.constructor is None:
            return instance
        result = self.constructor.call(arguments, this_value=instance)
        if isinstance(result, (dict, list)):
            return result
        return instance


def create_global_environment() -> Environment:
    env = Environment()
    env.declare("this", None, kind="const")
    install_builtins(env)
    return env


def evaluate_expression(source: str, environment: Environment | None = None) -> object:
    env = environment or create_global_environment()
    try:
        return evaluate_expr(parse_expression_ast(source), env)
    except ThrowSignal as signal:
        raise JavaScriptThrownValue(signal.value) from None


def evaluate_program(source: str, environment: Environment | None = None) -> object:
    env = environment or create_global_environment()
    program = parse_program_ast(source)
    try:
        return evaluate_ast_program(program, env)
    except ThrowSignal as signal:
        raise JavaScriptThrownValue(signal.value) from None


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
    if isinstance(statement, ClassDeclaration):
        js_class = JavaScriptClass(
            name=statement.name,
            methods=statement.methods,
            closure=environment,
        )
        environment.declare(statement.name, js_class, kind="let")
        return js_class
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
    if isinstance(statement, ThrowStatement):
        raise ThrowSignal(evaluate_expr(statement.value, environment))
    if isinstance(statement, TryStatement):
        pending_return: ReturnSignal | None = None
        pending_throw: ThrowSignal | None = None
        value: object = None
        try:
            try:
                value = evaluate_statement(statement.body, environment)
            except ThrowSignal as thrown:
                if statement.catch_body is None:
                    pending_throw = thrown
                else:
                    catch_env = environment.child_block()
                    assert statement.catch_name is not None
                    catch_env.declare(statement.catch_name, thrown.value, kind="let")
                    value = evaluate_statement(statement.catch_body, catch_env)
        except ReturnSignal as signal:
            pending_return = signal
        finally:
            if statement.finally_body is not None:
                value = evaluate_statement(statement.finally_body, environment)
        if pending_return is not None:
            raise pending_return
        if pending_throw is not None:
            raise pending_throw
        return value
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
    if isinstance(expr, ArrowFunctionExpr):
        return JavaScriptArrowFunction(
            params=expr.params,
            body=expr.body,
            closure=environment,
            lexical_this=environment.get("this"),
        )
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
            callee = read_property(this_value, expr.callee.property_name)
        elif isinstance(expr.callee, IndexExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = read_index(this_value, evaluate_expr(expr.callee.index, environment))
        else:
            callee = evaluate_expr(expr.callee, environment)
        if not is_callable(callee):
            raise TypeError("Value is not callable")
        arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
        return callee.call(arguments, this_value=this_value)
    if isinstance(expr, NewExpr):
        callee = evaluate_expr(expr.callee, environment)
        if not isinstance(callee, JavaScriptClass):
            raise TypeError("Value is not a constructor")
        arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
        return callee.call(arguments)
    if isinstance(expr, AssignmentExpr):
        value = evaluate_expr(expr.value, environment)
        if isinstance(expr.target, Identifier):
            return environment.assign(expr.target.name, value)
        if isinstance(expr.target, MemberExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            write_property(target_object, expr.target.property_name, value)
            return value
        if isinstance(expr.target, IndexExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            index = evaluate_expr(expr.target.index, environment)
            write_index(target_object, index, value)
            return value
        raise RuntimeError(f"Unsupported assignment target: {type(expr.target).__name__}")
    if isinstance(expr, MemberExpr):
        return read_property(evaluate_expr(expr.object, environment), expr.property_name)
    if isinstance(expr, IndexExpr):
        return read_index(
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
