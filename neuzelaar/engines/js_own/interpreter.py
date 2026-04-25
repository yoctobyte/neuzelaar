"""Evaluator for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.execution import budget_tick, execution_budget
from neuzelaar.engines.js_own.promises import JavaScriptPromise, await_value, promise_resolve
from neuzelaar.engines.js_own.errors import JavaScriptThrownValue
from neuzelaar.engines.js_own.host import HostCallable
from neuzelaar.engines.js_own.runtime_state import current_runtime_state, runtime_session
from neuzelaar.engines.js_own.ast import (
    ArrayLiteral,
    AssignmentExpr,
    ArrowFunctionExpr,
    AwaitExpr,
    BinaryExpr,
    BlockStatement,
    BooleanLiteral,
    CallExpr,
    ClassDeclaration,
    ClassExpr,
    ClassField,
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
    SuperExpr,
    TemplateLiteral,
    TaggedTemplateExpr,
    ThisExpr,
    ThrowStatement,
    TryStatement,
    UnaryExpr,
    UpdateExpr,
    VariableDeclaration,
)
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.parser import parse_expression as parse_expression_ast
from neuzelaar.engines.js_own.parser import parse_program as parse_program_ast
from neuzelaar.engines.js_own.runtime import (
    js_add,
    js_loose_equal,
    js_strict_equal,
    js_to_string,
    js_to_number,
    js_truthy,
    is_js_object,
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
        super_class: "JavaScriptClass | None" = None,
        super_prototype: dict[str, object] | None = None,
        owner_class: "JavaScriptClass | None" = None,
    ) -> None:
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.super_class = super_class
        self.super_prototype = super_prototype
        self.owner_class = owner_class
        self.prototype: dict[str, object] = {"constructor": self}

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        call_env = Environment(parent=self.closure)
        call_env.declare("this", this_value, kind="const")
        call_env.declare("arguments", list(arguments), kind="var")
        if self.super_class is not None:
            call_env.declare("__super_class__", self.super_class, kind="const")
        if self.super_prototype is not None:
            call_env.declare("__super_prototype__", self.super_prototype, kind="const")
        if self.owner_class is not None:
            call_env.declare("__current_class__", self.owner_class, kind="const")
        if self.name is not None:
            call_env.declare(self.name, self, kind="const")
        for index, param in enumerate(self.params):
            value = arguments[index] if index < len(arguments) else None
            call_env.declare(param, value, kind="var")
        try:
            evaluate_statement(self.body, call_env)
            return None
        except ReturnSignal as signal:
            return signal.value

    def construct(self, arguments: tuple[object, ...]) -> object:
        instance = {"__proto__": self.prototype}
        result = self.call(arguments, this_value=instance)
        if is_js_object(result):
            return result
        return instance


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
                evaluate_statement(self.body, call_env)
                return None
            except ReturnSignal as signal:
                return signal.value
        return evaluate_expr(self.body, call_env)

    def construct(self, arguments: tuple[object, ...]) -> object:
        return self.call(arguments)


class JavaScriptAsyncFunction(JavaScriptFunction):
    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        call_env = Environment(parent=self.closure)
        call_env.declare("this", this_value, kind="const")
        call_env.declare("arguments", list(arguments), kind="var")
        if self.super_class is not None:
            call_env.declare("__super_class__", self.super_class, kind="const")
        if self.super_prototype is not None:
            call_env.declare("__super_prototype__", self.super_prototype, kind="const")
        if self.owner_class is not None:
            call_env.declare("__current_class__", self.owner_class, kind="const")
        if self.name is not None:
            call_env.declare(self.name, self, kind="const")
        for index, param in enumerate(self.params):
            value = arguments[index] if index < len(arguments) else None
            call_env.declare(param, value, kind="var")
        promise = JavaScriptPromise()
        _evaluate_async_statement(
            self.body,
            call_env,
            on_complete=lambda result: _resolve_async_completion(promise, result),
            on_error=lambda reason: promise.reject(reason),
        )
        return promise


class JavaScriptAsyncArrowFunction(JavaScriptArrowFunction):
    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        call_env = Environment(parent=self.closure)
        call_env.declare("this", self.lexical_this, kind="const")
        for index, param in enumerate(self.params):
            value = arguments[index] if index < len(arguments) else None
            call_env.declare(param, value, kind="var")
        promise = JavaScriptPromise()
        if isinstance(self.body, BlockStatement):
            _evaluate_async_statement(
                self.body,
                call_env,
                on_complete=lambda result: _resolve_async_completion(promise, result),
                on_error=lambda reason: promise.reject(reason),
            )
        else:
            _evaluate_async_expr(
                self.body,
                call_env,
                on_value=promise.fulfill,
                on_error=promise.reject,
            )
        return promise


class JavaScriptClass:
    def __init__(
        self,
        *,
        name: str,
        superclass: "JavaScriptClass | None",
        methods: tuple[ClassMethod, ...],
        closure: Environment,
    ) -> None:
        self.name = name
        self.superclass = superclass
        self.closure = closure
        self.prototype: dict[str, object] = (
            {"__proto__": superclass.prototype} if superclass is not None else {}
        )
        self.static_properties: dict[str, object] = {}
        self.fields: tuple[ClassField, ...] = ()
        self.static_fields: tuple[ClassField, ...] = ()
        self.private_fields: tuple[ClassField, ...] = ()
        self.private_static_fields: tuple[ClassField, ...] = ()
        self.private_methods: dict[str, object] = {}
        self.private_static_methods: dict[str, object] = {}
        self.private_static_slots: dict[int, dict[str, object]] = {}
        self.constructor: JavaScriptFunction | None = None
        self.install_members(methods=methods, fields=(), closure=closure)

    def install_members(
        self,
        *,
        methods: tuple[ClassMethod, ...],
        fields: tuple[ClassField, ...],
        closure: Environment,
    ) -> None:
        self.fields = tuple(field for field in fields if not field.is_static and not field.is_private)
        self.static_fields = tuple(field for field in fields if field.is_static and not field.is_private)
        self.private_fields = tuple(field for field in fields if not field.is_static and field.is_private)
        self.private_static_fields = tuple(field for field in fields if field.is_static and field.is_private)
        for method in methods:
            property_name = _class_member_name(method, closure)
            function_cls = JavaScriptAsyncFunction if method.is_async else JavaScriptFunction
            function = function_cls(
                name=property_name,
                params=method.params,
                body=method.body,
                closure=closure,
                super_class=self.superclass,
                super_prototype=self.superclass.prototype if self.superclass is not None else None,
                owner_class=self,
            )
            if method.is_private:
                target = self.private_static_methods if method.is_static else self.private_methods
                if method.accessor_kind is not None:
                    descriptor = target.get(property_name)
                    if not isinstance(descriptor, dict) or ("get" not in descriptor and "set" not in descriptor):
                        descriptor = {"get": None, "set": None}
                    descriptor[method.accessor_kind] = function
                    target[property_name] = descriptor
                else:
                    target[property_name] = function
                continue
            if method.accessor_kind is not None:
                target = self.static_properties if method.is_static else self.prototype
                descriptor = target.get(property_name)
                if not isinstance(descriptor, dict) or ("get" not in descriptor and "set" not in descriptor):
                    descriptor = {"get": None, "set": None}
                descriptor[method.accessor_kind] = function
                target[property_name] = descriptor
                continue
            if property_name == "constructor" and not method.is_static:
                self.constructor = function
            elif method.is_static:
                self.static_properties[property_name] = function
            else:
                self.prototype[property_name] = function

    def _ensure_instance_private_slot(self, instance: object) -> dict[str, object]:
        if not isinstance(instance, dict):
            raise TypeError("Private fields require an object receiver")
        slot = instance.get("__class_private_instance__")
        if not isinstance(slot, dict):
            slot = {}
            instance["__class_private_instance__"] = slot
        class_slot = slot.get(id(self))
        if not isinstance(class_slot, dict):
            class_slot = {}
            slot[id(self)] = class_slot
        return class_slot

    def _get_instance_private_slot(self, instance: object) -> dict[str, object]:
        if not isinstance(instance, dict):
            raise TypeError("Private fields require an object receiver")
        slot = instance.get("__class_private_instance__")
        if not isinstance(slot, dict):
            raise TypeError("Private member access on non-instance")
        class_slot = slot.get(id(self))
        if not isinstance(class_slot, dict):
            raise TypeError(f"Object is not branded for private member #{self.name}")
        return class_slot

    def _ensure_static_private_slot(self) -> dict[str, object]:
        slot = self.private_static_slots.get(id(self))
        if slot is None:
            slot = {}
            self.private_static_slots[id(self)] = slot
        return slot

    def _get_static_private_slot(self, target: object) -> dict[str, object]:
        if not isinstance(target, JavaScriptClass):
            raise TypeError("Private static fields require a class receiver")
        slot = target.private_static_slots.get(id(self))
        if slot is None:
            raise TypeError(f"Class is not branded for private static member #{self.name}")
        return slot

    def read_private(self, target: object, property_name: str, *, receiver: object | None = None) -> object:
        if property_name in self.private_static_methods:
            self._get_static_private_slot(target)
            return _resolve_private_descriptor(
                self.private_static_methods[property_name],
                target if receiver is None else receiver,
            )
        if property_name in _private_name_set(self.private_static_fields):
            return self._get_static_private_slot(target).get(property_name)
        if property_name in self.private_methods:
            self._get_instance_private_slot(target)
            return _resolve_private_descriptor(
                self.private_methods[property_name],
                target if receiver is None else receiver,
            )
        if property_name in _private_name_set(self.private_fields):
            return self._get_instance_private_slot(target).get(property_name)
        raise TypeError(f"Private member #{property_name} is not declared in class {self.name}")

    def write_private(self, target: object, property_name: str, value: object, *, receiver: object | None = None) -> object:
        if property_name in self.private_static_methods:
            self._get_static_private_slot(target)
            descriptor = self.private_static_methods[property_name]
            if isinstance(descriptor, dict) and ("get" in descriptor or "set" in descriptor):
                setter = descriptor.get("set")
                if setter is None:
                    raise TypeError(f"Cannot set private property #{property_name}")
                setter.call((value,), this_value=target if receiver is None else receiver)
                return value
            raise TypeError(f"Cannot set private method #{property_name}")
        if property_name in _private_name_set(self.private_static_fields):
            self._get_static_private_slot(target)[property_name] = value
            return value
        if property_name in self.private_methods:
            self._get_instance_private_slot(target)
            descriptor = self.private_methods[property_name]
            if isinstance(descriptor, dict) and ("get" in descriptor or "set" in descriptor):
                setter = descriptor.get("set")
                if setter is None:
                    raise TypeError(f"Cannot set private property #{property_name}")
                setter.call((value,), this_value=target if receiver is None else receiver)
                return value
            raise TypeError(f"Cannot set private method #{property_name}")
        if property_name in _private_name_set(self.private_fields):
            self._get_instance_private_slot(target)[property_name] = value
            return value
        raise TypeError(f"Private member #{property_name} is not declared in class {self.name}")

    def initialize_static_fields(self) -> None:
        field_env = Environment(parent=self.closure)
        field_env.declare("this", self, kind="const")
        if self.superclass is not None:
            field_env.declare("__super_class__", self.superclass, kind="const")
            field_env.declare("__super_prototype__", self.superclass.prototype, kind="const")
        if self.name:
            field_env.declare(self.name, self, kind="const")
        if self.private_static_fields or self.private_static_methods:
            self._ensure_static_private_slot()
        for field in self.static_fields:
            property_name = _class_member_name(field, field_env)
            value = None if field.initializer is None else evaluate_expr(field.initializer, field_env)
            self.static_properties[property_name] = value
        if self.private_static_fields:
            private_slot = self._ensure_static_private_slot()
            for field in self.private_static_fields:
                property_name = _class_member_name(field, field_env)
                value = None if field.initializer is None else evaluate_expr(field.initializer, field_env)
                private_slot[property_name] = value

    def initialize_instance_fields(self, instance: dict[str, object]) -> None:
        marker = f"__fields_initialized_{id(self)}"
        if instance.get(marker):
            return
        field_env = Environment(parent=self.closure)
        field_env.declare("this", instance, kind="const")
        if self.superclass is not None:
            field_env.declare("__super_class__", self.superclass, kind="const")
            field_env.declare("__super_prototype__", self.superclass.prototype, kind="const")
        if self.name:
            field_env.declare(self.name, self, kind="const")
        if self.private_fields or self.private_methods:
            self._ensure_instance_private_slot(instance)
        for field in self.fields:
            property_name = _class_member_name(field, field_env)
            value = None if field.initializer is None else evaluate_expr(field.initializer, field_env)
            instance[property_name] = value
        if self.private_fields:
            private_slot = self._ensure_instance_private_slot(instance)
            for field in self.private_fields:
                property_name = _class_member_name(field, field_env)
                value = None if field.initializer is None else evaluate_expr(field.initializer, field_env)
                private_slot[property_name] = value
        instance[marker] = True

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        if isinstance(this_value, dict):
            instance = this_value
            instance.setdefault("__proto__", self.prototype)
        else:
            instance = {"__proto__": self.prototype}
        if self.constructor is None:
            if self.superclass is not None:
                self.superclass.call(arguments, this_value=instance)
            self.initialize_instance_fields(instance)
            return instance
        if self.superclass is None:
            self.initialize_instance_fields(instance)
        result = self.constructor.call(arguments, this_value=instance)
        self.initialize_instance_fields(instance)
        if isinstance(result, (dict, list)):
            return result
        return instance


def create_global_environment() -> Environment:
    env = Environment()
    env.declare("this", None, kind="const")
    install_builtins(env)
    return env


def _class_member_name(member: ClassMethod | ClassField, environment: Environment) -> str:
    if member.key_expr is None:
        assert member.name is not None
        return member.name
    value = evaluate_expr(member.key_expr, environment)
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return str(value)


def _resolve_private_descriptor(value: object, receiver: object) -> object:
    if isinstance(value, dict) and ("get" in value or "set" in value):
        getter = value.get("get")
        if getter is None:
            return None
        return getter.call((), this_value=receiver)
    return value


def _private_name_set(fields: tuple[ClassField, ...]) -> set[str]:
    return {field.name for field in fields if field.name is not None}


def _current_this(environment: Environment) -> object:
    try:
        return environment.get("this")
    except Exception:
        return None


def _resolve_async_completion(promise: JavaScriptPromise, result: tuple[str, object]) -> None:
    kind, value = result
    if kind == "return":
        if isinstance(value, JavaScriptPromise):
            await_value(value, promise.fulfill, promise.reject)
            return
        promise.fulfill(value)
        return
    promise.fulfill(value)


def _evaluate_async_statement(statement: Stmt, environment: Environment, *, on_complete, on_error) -> None:
    if isinstance(statement, ExpressionStatement):
        _evaluate_async_expr(statement.expression, environment, on_value=lambda value: on_complete(("normal", value)), on_error=on_error)
        return
    if isinstance(statement, VariableDeclaration):
        if statement.initializer is None:
            environment.declare(statement.name, None, kind=statement.kind)
            on_complete(("normal", None))
            return
        _evaluate_async_expr(
            statement.initializer,
            environment,
            on_value=lambda value: on_complete(("normal", environment.declare(statement.name, value, kind=statement.kind))),
            on_error=on_error,
        )
        return
    if isinstance(statement, FunctionDeclaration):
        function_cls = JavaScriptAsyncFunction if statement.is_async else JavaScriptFunction
        function = function_cls(
            name=statement.name,
            params=statement.params,
            body=statement.body,
            closure=environment,
        )
        environment.declare(statement.name, function, kind="var")
        on_complete(("normal", function))
        return
    if isinstance(statement, ClassDeclaration):
        js_class = evaluate_class_expr(
            ClassExpr(
                name=statement.name,
                superclass=statement.superclass,
                methods=statement.methods,
                fields=statement.fields,
            ),
            environment,
        )
        environment.declare(statement.name, js_class, kind="let")
        on_complete(("normal", js_class))
        return
    if isinstance(statement, BlockStatement):
        block_env = environment.child_block()
        _evaluate_async_statement_list(list(statement.statements), block_env, on_complete=on_complete, on_error=on_error)
        return
    if isinstance(statement, IfStatement):
        _evaluate_async_expr(
            statement.test,
            environment,
            on_value=lambda test: _evaluate_async_statement(
                statement.consequent if js_truthy(test) else (statement.alternate or ExpressionStatement(NullLiteral())),
                environment,
                on_complete=on_complete,
                on_error=on_error,
            ),
            on_error=on_error,
        )
        return
    if isinstance(statement, ReturnStatement):
        if statement.value is None:
            on_complete(("return", None))
            return
        _evaluate_async_expr(statement.value, environment, on_value=lambda value: on_complete(("return", value)), on_error=on_error)
        return
    if isinstance(statement, ThrowStatement):
        _evaluate_async_expr(statement.value, environment, on_value=on_error, on_error=on_error)
        return
    if isinstance(statement, TryStatement):
        def run_finally(next_step) -> None:
            if statement.finally_body is None:
                next_step()
                return
            _evaluate_async_statement(
                statement.finally_body,
                environment,
                on_complete=lambda result: next_step() if result[0] == "normal" else on_complete(result),
                on_error=on_error,
            )

        def handle_body_complete(result: tuple[str, object]) -> None:
            run_finally(lambda: on_complete(result))

        def handle_body_error(reason: object) -> None:
            if statement.catch_body is None:
                run_finally(lambda: on_error(reason))
                return
            catch_env = environment.child_block()
            assert statement.catch_name is not None
            catch_env.declare(statement.catch_name, reason, kind="let")
            _evaluate_async_statement(
                statement.catch_body,
                catch_env,
                on_complete=lambda result: run_finally(lambda: on_complete(result)),
                on_error=lambda catch_reason: run_finally(lambda: on_error(catch_reason)),
            )

        _evaluate_async_statement(statement.body, environment, on_complete=handle_body_complete, on_error=handle_body_error)
        return
    raise RuntimeError(f"Unsupported async statement node: {type(statement).__name__}")


def _evaluate_async_statement_list(statements: list[Stmt], environment: Environment, *, on_complete, on_error, last_value: object = None) -> None:
    if not statements:
        on_complete(("normal", last_value))
        return
    statement = statements[0]
    _evaluate_async_statement(
        statement,
        environment,
        on_complete=lambda result: on_complete(result)
        if result[0] != "normal"
        else _evaluate_async_statement_list(statements[1:], environment, on_complete=on_complete, on_error=on_error, last_value=result[1]),
        on_error=on_error,
    )


def _evaluate_async_expr(expr: Expr, environment: Environment, *, on_value, on_error) -> None:
    if isinstance(expr, AwaitExpr):
        _evaluate_async_expr(expr.value, environment, on_value=lambda value: await_value(value, on_value, on_error), on_error=on_error)
        return
    if isinstance(expr, (NumberLiteral, StringLiteral, BooleanLiteral, NullLiteral, Identifier, ThisExpr, SuperExpr, FunctionExpr, ArrowFunctionExpr, ClassExpr)):
        try:
            on_value(evaluate_expr(expr, environment))
        except ThrowSignal as signal:
            on_error(signal.value)
        except Exception as exc:
            on_error(exc)
        return
    if isinstance(expr, TemplateLiteral):
        _evaluate_template_literal_async(expr, environment, on_value=on_value, on_error=on_error)
        return
    if isinstance(expr, ArrayLiteral):
        _evaluate_async_value_list(list(expr.elements), environment, on_value=lambda values: on_value(list(values)), on_error=on_error)
        return
    if isinstance(expr, ObjectLiteral):
        _evaluate_async_object_literal(expr, environment, on_value=on_value, on_error=on_error)
        return
    if isinstance(expr, UnaryExpr):
        _evaluate_async_expr(
            expr.operand,
            environment,
            on_value=lambda operand: on_value(
                not js_truthy(operand)
                if expr.operator == "!"
                else js_to_number(operand)
                if expr.operator == "+"
                else -js_to_number(operand)
            ),
            on_error=on_error,
        )
        return
    if isinstance(expr, BinaryExpr):
        _evaluate_async_binary(expr, environment, on_value=on_value, on_error=on_error)
        return
    if isinstance(expr, CallExpr):
        _evaluate_async_call(expr, environment, on_value=on_value, on_error=on_error)
        return
    if isinstance(expr, NewExpr):
        _evaluate_async_expr(
            expr.callee,
            environment,
            on_value=lambda callee: _evaluate_async_value_list(
                list(expr.arguments),
                environment,
                on_value=lambda arguments: on_value(
                    callee.call(tuple(arguments))
                    if isinstance(callee, JavaScriptClass)
                    else callee.construct(tuple(arguments))
                    if hasattr(callee, "construct")
                    else _raise_type_error("Value is not a constructor")
                ),
                on_error=on_error,
            ),
            on_error=on_error,
        )
        return
    if isinstance(expr, AssignmentExpr):
        _evaluate_async_assignment(expr, environment, on_value=on_value, on_error=on_error)
        return
    if isinstance(expr, MemberExpr):
        _evaluate_async_expr(
            expr.object,
            environment,
            on_value=lambda target: on_value(
                _read_member_value(expr, environment, target)
            ),
            on_error=on_error,
        )
        return
    if isinstance(expr, IndexExpr):
        _evaluate_async_expr(
            expr.object,
            environment,
            on_value=lambda target: _evaluate_async_expr(
                expr.index,
                environment,
                on_value=lambda index: on_value(read_index(target, index)),
                on_error=on_error,
            ),
            on_error=on_error,
        )
        return
    raise RuntimeError(f"Unsupported async expression node: {type(expr).__name__}")


def _evaluate_template_literal_async(expr: TemplateLiteral, environment: Environment, *, on_value, on_error) -> None:
    parts = list(expr.parts)
    rendered: list[str] = []

    def step(index: int) -> None:
        if index >= len(parts):
            on_value("".join(rendered))
            return
        part = parts[index]
        if isinstance(part, str):
            rendered.append(part)
            step(index + 1)
            return
        _evaluate_async_expr(part, environment, on_value=lambda value: (rendered.append(js_to_string(value)), step(index + 1)), on_error=on_error)

    step(0)


def _evaluate_async_value_list(expressions: list[Expr], environment: Environment, *, on_value, on_error, collected: list[object] | None = None) -> None:
    items = [] if collected is None else collected
    if not expressions:
        on_value(tuple(items))
        return
    head, *tail = expressions
    _evaluate_async_expr(
        head,
        environment,
        on_value=lambda value: (_evaluate_async_value_list(tail, environment, on_value=on_value, on_error=on_error, collected=items + [value])),
        on_error=on_error,
    )


def _evaluate_async_object_literal(expr: ObjectLiteral, environment: Environment, *, on_value, on_error, index: int = 0, collected: dict[str, object] | None = None) -> None:
    result = {} if collected is None else dict(collected)
    if index >= len(expr.properties):
        on_value(result)
        return
    prop = expr.properties[index]
    _evaluate_async_expr(
        prop.value,
        environment,
        on_value=lambda value: _evaluate_async_object_literal(
            expr,
            environment,
            on_value=on_value,
            on_error=on_error,
            index=index + 1,
            collected={**result, prop.key: value},
        ),
        on_error=on_error,
    )


def _evaluate_async_binary(expr: BinaryExpr, environment: Environment, *, on_value, on_error) -> None:
    if expr.operator == "&&":
        _evaluate_async_expr(
            expr.left,
            environment,
            on_value=lambda left: on_value(left)
            if not js_truthy(left)
            else _evaluate_async_expr(expr.right, environment, on_value=on_value, on_error=on_error),
            on_error=on_error,
        )
        return
    if expr.operator == "||":
        _evaluate_async_expr(
            expr.left,
            environment,
            on_value=lambda left: on_value(left)
            if js_truthy(left)
            else _evaluate_async_expr(expr.right, environment, on_value=on_value, on_error=on_error),
            on_error=on_error,
        )
        return
    _evaluate_async_expr(
        expr.left,
        environment,
        on_value=lambda left: _evaluate_async_expr(
            expr.right,
            environment,
            on_value=lambda right: on_value(_apply_binary_operator(expr.operator, left, right)),
            on_error=on_error,
        ),
        on_error=on_error,
    )


def _evaluate_async_call(expr: CallExpr, environment: Environment, *, on_value, on_error) -> None:
    def invoke(callee: object, this_value: object | None) -> None:
        if not is_callable(callee):
            on_error(TypeError("Value is not callable"))
            return
        _evaluate_async_value_list(
            list(expr.arguments),
            environment,
            on_value=lambda arguments: on_value(callee.call(tuple(arguments), this_value=this_value)),
            on_error=on_error,
        )

    if isinstance(expr.callee, SuperExpr):
        super_class = environment.get("__super_class__")
        if not isinstance(super_class, JavaScriptClass):
            on_error(TypeError("super() is not available here"))
            return
        this_value = environment.get("this")
        _evaluate_async_value_list(
            list(expr.arguments),
            environment,
            on_value=lambda arguments: on_value(super_class.call(tuple(arguments), this_value=this_value)),
            on_error=on_error,
        )
        return
    if isinstance(expr.callee, MemberExpr):
        _evaluate_async_expr(
            expr.callee.object,
            environment,
            on_value=lambda this_value: invoke(_read_member_value(expr.callee, environment, this_value), this_value),
            on_error=on_error,
        )
        return
    if isinstance(expr.callee, IndexExpr):
        _evaluate_async_expr(
            expr.callee.object,
            environment,
            on_value=lambda this_value: _evaluate_async_expr(
                expr.callee.index,
                environment,
                on_value=lambda index: invoke(read_index(this_value, index), this_value),
                on_error=on_error,
            ),
            on_error=on_error,
        )
        return
    _evaluate_async_expr(expr.callee, environment, on_value=lambda callee: invoke(callee, None), on_error=on_error)


def _evaluate_async_assignment(expr: AssignmentExpr, environment: Environment, *, on_value, on_error) -> None:
    _evaluate_async_expr(
        expr.value,
        environment,
        on_value=lambda value: on_value(_assign_target(expr.target, value, environment)),
        on_error=on_error,
    )


def _apply_binary_operator(operator: str, left: object, right: object) -> object:
    if operator == "+":
        return js_add(left, right)
    if operator == "-":
        return js_to_number(left) - js_to_number(right)
    if operator == "*":
        return js_to_number(left) * js_to_number(right)
    if operator == "/":
        return js_to_number(left) / js_to_number(right)
    if operator == "%":
        return js_to_number(left) % js_to_number(right)
    if operator == "<":
        return js_to_number(left) < js_to_number(right)
    if operator == ">":
        return js_to_number(left) > js_to_number(right)
    if operator == "<=":
        return js_to_number(left) <= js_to_number(right)
    if operator == ">=":
        return js_to_number(left) >= js_to_number(right)
    if operator == "===":
        return js_strict_equal(left, right)
    if operator == "!==":
        return not js_strict_equal(left, right)
    if operator == "==":
        return js_loose_equal(left, right)
    if operator == "!=":
        return not js_loose_equal(left, right)
    raise RuntimeError(f"Unsupported binary operator: {operator}")


def _read_member_value(expr: MemberExpr, environment: Environment, target: object) -> object:
    if expr.is_private:
        owner_class = environment.get("__current_class__")
        if not isinstance(owner_class, JavaScriptClass):
            raise TypeError(f"Private member #{expr.property_name} is not available here")
        return owner_class.read_private(target, expr.property_name, receiver=target)
    if isinstance(expr.object, SuperExpr):
        receiver = environment.get("this")
        target = environment.get("__super_prototype__")
        return read_property(target, expr.property_name, receiver=receiver)
    return read_property(target, expr.property_name, receiver=target)


def _assign_target(target: Expr, value: object, environment: Environment) -> object:
    if isinstance(target, Identifier):
        return environment.assign(target.name, value)
    if isinstance(target, MemberExpr):
        if target.is_private:
            owner_class = environment.get("__current_class__")
            if not isinstance(owner_class, JavaScriptClass):
                raise TypeError(f"Private member #{target.property_name} is not available here")
            target_object = evaluate_expr(target.object, environment)
            owner_class.write_private(target_object, target.property_name, value, receiver=target_object)
            return value
        if isinstance(target.object, SuperExpr):
            target_object = environment.get("__super_prototype__")
            receiver = environment.get("this")
            write_property(target_object, target.property_name, value, receiver=receiver)
            return value
        target_object = evaluate_expr(target.object, environment)
        write_property(target_object, target.property_name, value, receiver=target_object)
        return value
    if isinstance(target, IndexExpr):
        target_object = evaluate_expr(target.object, environment)
        index = evaluate_expr(target.index, environment)
        write_index(target_object, index, value)
        return value
    raise RuntimeError(f"Unsupported assignment target: {type(target).__name__}")


def _raise_type_error(message: str) -> object:
    raise TypeError(message)


def evaluate_class_expr(expr: ClassExpr, environment: Environment) -> JavaScriptClass:
    superclass = None
    if expr.superclass is not None:
        superclass_value = evaluate_expr(expr.superclass, environment)
        if not isinstance(superclass_value, JavaScriptClass):
            raise TypeError("Superclass must be a class")
        superclass = superclass_value

    class_scope = environment.child_block()
    class_object = JavaScriptClass(
        name=expr.name or "<anonymous>",
        superclass=superclass,
        methods=(),
        closure=class_scope,
    )
    if expr.name is not None:
        class_scope.declare(expr.name, class_object, kind="const")
    class_object.install_members(methods=expr.methods, fields=expr.fields, closure=class_scope)
    class_object.initialize_static_fields()
    return class_object


def evaluate_expression(source: str, environment: Environment | None = None) -> object:
    return evaluate_expression_with_config(source, environment=environment, runtime_config=None)


def evaluate_program(source: str, environment: Environment | None = None) -> object:
    return evaluate_program_with_config(source, environment=environment, runtime_config=None)


def evaluate_expression_with_config(
    source: str,
    environment: Environment | None = None,
    runtime_config: ScriptRuntimeConfig | None = None,
    scheduler=None,
) -> object:
    env = environment or create_global_environment()
    try:
        with execution_budget(runtime_config):
            existing_state = current_runtime_state()
            if existing_state is not None:
                value = evaluate_expr(parse_expression_ast(source), env)
                return value
            with runtime_session(runtime_config, scheduler=scheduler) as state:
                value = evaluate_expr(parse_expression_ast(source), env)
                state.drain_microtasks()
                return value
    except ThrowSignal as signal:
        raise JavaScriptThrownValue(signal.value) from None


def evaluate_program_with_config(
    source: str,
    environment: Environment | None = None,
    runtime_config: ScriptRuntimeConfig | None = None,
    scheduler=None,
) -> object:
    env = environment or create_global_environment()
    program = parse_program_ast(source)
    try:
        with execution_budget(runtime_config):
            existing_state = current_runtime_state()
            if existing_state is not None:
                value = evaluate_ast_program(program, env)
                return value
            with runtime_session(runtime_config, scheduler=scheduler) as state:
                value = evaluate_ast_program(program, env)
                state.drain_microtasks()
                return value
    except ThrowSignal as signal:
        raise JavaScriptThrownValue(signal.value) from None


def evaluate_ast_program(program: Program, environment: Environment | None = None) -> object:
    env = environment or Environment()
    value: object = None
    for statement in program.statements:
        value = evaluate_statement(statement, env)
    return value


def evaluate_statement(statement: Stmt, environment: Environment) -> object:
    budget_tick()
    if isinstance(statement, ExpressionStatement):
        return evaluate_expr(statement.expression, environment)
    if isinstance(statement, VariableDeclaration):
        value = None if statement.initializer is None else evaluate_expr(statement.initializer, environment)
        environment.declare(statement.name, value, kind=statement.kind)
        return value
    if isinstance(statement, FunctionDeclaration):
        function_cls = JavaScriptAsyncFunction if statement.is_async else JavaScriptFunction
        function = function_cls(
            name=statement.name,
            params=statement.params,
            body=statement.body,
            closure=environment,
        )
        environment.declare(statement.name, function, kind="var")
        return function
    if isinstance(statement, ClassDeclaration):
        js_class = evaluate_class_expr(
            ClassExpr(
                name=statement.name,
                superclass=statement.superclass,
                methods=statement.methods,
                fields=statement.fields,
            ),
            environment,
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
    budget_tick()
    if isinstance(expr, NumberLiteral):
        return expr.value
    if isinstance(expr, StringLiteral):
        return expr.value
    if isinstance(expr, TemplateLiteral):
        rendered: list[str] = []
        for part in expr.parts:
            if isinstance(part, str):
                rendered.append(part)
            else:
                rendered.append(js_to_string(evaluate_expr(part, environment)))
        return "".join(rendered)
    if isinstance(expr, BooleanLiteral):
        return expr.value
    if isinstance(expr, NullLiteral):
        return None
    if isinstance(expr, Identifier):
        return environment.get(expr.name)
    if isinstance(expr, ThisExpr):
        return environment.get("this")
    if isinstance(expr, SuperExpr):
        return environment.get("__super_prototype__")
    if isinstance(expr, AwaitExpr):
        raise TypeError("await is only valid inside async functions")
    if isinstance(expr, ArrowFunctionExpr):
        function_cls = JavaScriptAsyncArrowFunction if expr.is_async else JavaScriptArrowFunction
        return function_cls(
            params=expr.params,
            body=expr.body,
            closure=environment,
            lexical_this=_current_this(environment),
        )
    if isinstance(expr, FunctionExpr):
        function_cls = JavaScriptAsyncFunction if expr.is_async else JavaScriptFunction
        function = function_cls(
            name=expr.name,
            params=expr.params,
            body=expr.body,
            closure=environment,
        )
        return function
    if isinstance(expr, ClassExpr):
        return evaluate_class_expr(expr, environment)
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
    if isinstance(expr, UpdateExpr):
        current = None
        if isinstance(expr.target, Identifier):
            current = environment.get(expr.target.name)
            next_value = js_to_number(current) + 1.0
            environment.assign(expr.target.name, next_value)
        elif isinstance(expr.target, MemberExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            current = read_property(target_object, expr.target.property_name, receiver=target_object)
            next_value = js_to_number(current) + 1.0
            write_property(target_object, expr.target.property_name, next_value, receiver=target_object)
        elif isinstance(expr.target, IndexExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            index = evaluate_expr(expr.target.index, environment)
            current = read_index(target_object, index)
            next_value = js_to_number(current) + 1.0
            write_index(target_object, index, next_value)
        else:
            raise TypeError("Invalid update target")
        return next_value if expr.prefix else current
    if isinstance(expr, CallExpr):
        this_value = None
        if isinstance(expr.callee, SuperExpr):
            super_class = environment.get("__super_class__")
            if not isinstance(super_class, JavaScriptClass):
                raise TypeError("super() is not available here")
            this_value = environment.get("this")
            arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
            result = super_class.call(arguments, this_value=this_value)
            current_class = environment.get("__current_class__")
            if isinstance(current_class, JavaScriptClass):
                current_class.initialize_instance_fields(this_value)
            return this_value if result is None or result is this_value else result
        if isinstance(expr.callee, MemberExpr) and expr.callee.is_private:
            owner_class = environment.get("__current_class__")
            if not isinstance(owner_class, JavaScriptClass):
                raise TypeError(f"Private member #{expr.callee.property_name} is not available here")
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = owner_class.read_private(this_value, expr.callee.property_name, receiver=this_value)
        elif isinstance(expr.callee, MemberExpr) and isinstance(expr.callee.object, SuperExpr):
            this_value = environment.get("this")
            super_prototype = environment.get("__super_prototype__")
            callee = read_property(super_prototype, expr.callee.property_name, receiver=this_value)
        elif isinstance(expr.callee, MemberExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = read_property(this_value, expr.callee.property_name, receiver=this_value)
        elif isinstance(expr.callee, IndexExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = read_index(this_value, evaluate_expr(expr.callee.index, environment))
        else:
            callee = evaluate_expr(expr.callee, environment)
        if not is_callable(callee):
            raise TypeError("Value is not callable")
        arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
        return callee.call(arguments, this_value=this_value)
    if isinstance(expr, TaggedTemplateExpr):
        this_value = None
        if isinstance(expr.callee, MemberExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = read_property(this_value, expr.callee.property_name, receiver=this_value)
        elif isinstance(expr.callee, IndexExpr):
            this_value = evaluate_expr(expr.callee.object, environment)
            callee = read_index(this_value, evaluate_expr(expr.callee.index, environment))
        else:
            callee = evaluate_expr(expr.callee, environment)
        if not is_callable(callee):
            raise TypeError("Value is not callable")
        template_argument = _materialize_tagged_template(expr.template, environment)
        return callee.call((template_argument,), this_value=this_value)
    if isinstance(expr, NewExpr):
        callee = evaluate_expr(expr.callee, environment)
        arguments = tuple(evaluate_expr(argument, environment) for argument in expr.arguments)
        if isinstance(callee, JavaScriptClass):
            return callee.call(arguments)
        if hasattr(callee, "construct"):
            return callee.construct(arguments)
        raise TypeError("Value is not a constructor")
    if isinstance(expr, AssignmentExpr):
        value = evaluate_expr(expr.value, environment)
        if isinstance(expr.target, Identifier):
            return environment.assign(expr.target.name, value)
        if isinstance(expr.target, MemberExpr):
            if expr.target.is_private:
                owner_class = environment.get("__current_class__")
                if not isinstance(owner_class, JavaScriptClass):
                    raise TypeError(f"Private member #{expr.target.property_name} is not available here")
                target_object = evaluate_expr(expr.target.object, environment)
                owner_class.write_private(
                    target_object,
                    expr.target.property_name,
                    value,
                    receiver=target_object,
                )
                return value
            if isinstance(expr.target.object, SuperExpr):
                target_object = environment.get("__super_prototype__")
                receiver = environment.get("this")
                write_property(target_object, expr.target.property_name, value, receiver=receiver)
                return value
            target_object = evaluate_expr(expr.target.object, environment)
            write_property(target_object, expr.target.property_name, value, receiver=target_object)
            return value
        if isinstance(expr.target, IndexExpr):
            target_object = evaluate_expr(expr.target.object, environment)
            index = evaluate_expr(expr.target.index, environment)
            write_index(target_object, index, value)
            return value
        raise RuntimeError(f"Unsupported assignment target: {type(expr.target).__name__}")
    if isinstance(expr, MemberExpr):
        if expr.is_private:
            owner_class = environment.get("__current_class__")
            if not isinstance(owner_class, JavaScriptClass):
                raise TypeError(f"Private member #{expr.property_name} is not available here")
            target = evaluate_expr(expr.object, environment)
            return owner_class.read_private(target, expr.property_name, receiver=target)
        if isinstance(expr.object, SuperExpr):
            receiver = environment.get("this")
            target = environment.get("__super_prototype__")
            return read_property(target, expr.property_name, receiver=receiver)
        target = evaluate_expr(expr.object, environment)
        return read_property(target, expr.property_name, receiver=target)
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
        if expr.operator == "instanceof":
            return _js_instanceof(left, right)
    raise RuntimeError(f"Unsupported expression node: {type(expr).__name__}")


def _materialize_tagged_template(template: TemplateLiteral, environment: Environment) -> dict[str, object]:
    cooked_segments = [part for part in template.parts if isinstance(part, str)]
    cooked = {str(index): value for index, value in enumerate(cooked_segments)}
    cooked["length"] = float(len(cooked_segments))
    raw = {str(index): value for index, value in enumerate(template.raw_parts)}
    raw["length"] = float(len(template.raw_parts))
    cooked["raw"] = raw
    return cooked


def _js_instanceof(left: object, right: object) -> bool:
    prototype = read_property(right, "prototype")
    if not isinstance(prototype, dict):
        raise TypeError("Right-hand side of instanceof is not an object")
    current = left if isinstance(left, dict) else None
    while isinstance(current, dict):
        current = current.get("__proto__")
        if current is prototype:
            return True
    return False
