import math

import pytest

from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.errors import (
    JavaScriptExecutionLimitError,
    JavaScriptReferenceError,
    JavaScriptSyntaxError,
    JavaScriptThrownValue,
)
from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.interpreter import (
    JavaScriptPromise,
    evaluate_expression,
    evaluate_expression_with_config,
    evaluate_program,
    evaluate_program_with_config,
)


def test_evaluate_numeric_precedence() -> None:
    assert evaluate_expression("1 + 2 * 3") == 7.0


def test_evaluate_string_concatenation() -> None:
    assert evaluate_expression('"a" + 2') == "a2"


def test_evaluate_template_literal() -> None:
    assert evaluate_program('var name = "rene"; `hello ${name} ${1 + 2}`;') == "hello rene 3"


def test_evaluate_nested_template_literal_expression() -> None:
    assert evaluate_expression_with_config("`sum: ${`x${1 + 1}`}`") == "sum: x2"


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


def test_array_literal_and_indexing_work() -> None:
    assert evaluate_program("var a = [1, 2, 3]; a[1];") == 2.0


def test_object_literal_and_member_access_work() -> None:
    assert evaluate_program('var o = { x: 1, "y": 2 }; o.x + o["y"];') == 3.0


def test_array_assignment_by_index_works() -> None:
    assert evaluate_program("var a = [1, 2]; a[1] = 9; a[1];") == 9.0


def test_object_assignment_by_property_works() -> None:
    assert evaluate_program("var o = { x: 1 }; o.x = 4; o.x;") == 4.0


def test_array_length_property_works() -> None:
    assert evaluate_program("var a = [1, 2, 3]; a.length;") == 3.0


def test_method_call_binds_this() -> None:
    result = evaluate_program(
        "var o = { value: 7, get: function () { return this.value; } }; o.get();"
    )

    assert result == 7.0


def test_method_call_via_index_binds_this() -> None:
    result = evaluate_program(
        'var o = { value: 8, get: function () { return this["value"]; } }; o["get"]();'
    )

    assert result == 8.0


def test_private_field_read_and_write_work() -> None:
    result = evaluate_program(
        "class Box { "
        "  #x = 1; "
        "  bump() { this.#x = this.#x + 2; return this.#x; } "
        "} "
        "var b = new Box(); "
        "b.bump();"
    )

    assert result == 3.0


def test_private_method_call_works() -> None:
    result = evaluate_program(
        "class Box { "
        "  #secret() { return 7; } "
        "  value() { return this.#secret(); } "
        "} "
        "new Box().value();"
    )

    assert result == 7.0


def test_private_accessor_works() -> None:
    result = evaluate_program(
        "class Box { "
        "  #stored = 0; "
        "  get #value() { return this.#stored + 1; } "
        "  set #value(x) { this.#stored = x; } "
        "  write(x) { this.#value = x; } "
        "  read() { return this.#value; } "
        "} "
        "var b = new Box(); "
        "b.write(4); "
        "b.read();"
    )

    assert result == 5.0


def test_private_brand_check_rejects_foreign_object() -> None:
    with pytest.raises(TypeError):
        evaluate_program(
            "class Box { "
            "  #x = 1; "
            "  read(other) { return other.#x; } "
            "} "
            "new Box().read({});"
        )


def test_subclass_instance_inherits_base_private_brand() -> None:
    result = evaluate_program(
        "class Base { "
        "  #x = 4; "
        "  read() { return this.#x; } "
        "} "
        "class Child extends Base { } "
        "new Child().read();"
    )

    assert result == 4.0


def test_subclass_cannot_access_base_private_name_directly() -> None:
    with pytest.raises(TypeError):
        evaluate_program(
            "class Base { #x = 1; } "
            "class Child extends Base { read() { return this.#x; } } "
            "new Child().read();"
        )


def test_static_private_field_and_method_work() -> None:
    result = evaluate_program(
        "class Box { "
        "  static #x = 4; "
        "  static #secret() { return this.#x + 3; } "
        "  static value() { return this.#secret(); } "
        "} "
        "Box.value();"
    )

    assert result == 7.0


def test_throw_and_catch_work() -> None:
    result = evaluate_program('try { throw "x"; } catch (e) { e; }')

    assert result == "x"


def test_try_finally_runs_before_return() -> None:
    result = evaluate_program(
        "function f() { var x = 1; try { return x; } finally { x = 9; } } f();"
    )

    assert result == 1.0


def test_finally_can_override_return() -> None:
    result = evaluate_program(
        "function f() { try { return 1; } finally { return 2; } } f();"
    )

    assert result == 2.0


def test_uncaught_throw_raises_python_wrapper() -> None:
    with pytest.raises(JavaScriptThrownValue) as exc:
        evaluate_program('throw "boom";')

    assert exc.value.value == "boom"


def test_execution_step_budget_can_abort_script() -> None:
    with pytest.raises(JavaScriptExecutionLimitError):
        evaluate_program_with_config(
            "function fact(n) { if (n === 0) { return 1; } return n * fact(n - 1); } fact(5);",
            runtime_config=ScriptRuntimeConfig(max_steps=10),
        )


def test_execution_step_budget_allows_small_program() -> None:
    assert (
        evaluate_program_with_config(
            "var x = 1; x = x + 2; x;",
            runtime_config=ScriptRuntimeConfig(max_steps=50),
        )
        == 3.0
    )


def test_promise_then_updates_environment_after_microtask_drain() -> None:
    env = Environment()
    install_builtins(env)

    result = evaluate_program("var seen = 0; Promise.resolve(2).then(x => { seen = x + 1; }); seen;", env)

    assert result == 0.0
    assert env.get("seen") == 3.0


def test_promise_catch_recovers_rejection() -> None:
    env = Environment()
    install_builtins(env)

    evaluate_program("var seen = 0; Promise.reject(2).catch(x => { seen = x + 1; });", env)

    assert env.get("seen") == 3.0


def test_queue_microtask_runs_after_program() -> None:
    env = Environment()
    install_builtins(env)

    result = evaluate_program("var seen = 0; queueMicrotask(() => { seen = 7; }); seen;", env)

    assert result == 0.0
    assert env.get("seen") == 7.0


def test_new_promise_executor_resolves() -> None:
    promise = evaluate_program("new Promise((resolve, reject) => { resolve(4); });")

    assert isinstance(promise, JavaScriptPromise)
    assert promise.state == "fulfilled"
    assert promise.value == 4.0


def test_async_function_resolves_fulfilled_promise() -> None:
    promise = evaluate_program("async function load() { return await Promise.resolve(5); } load();")

    assert isinstance(promise, JavaScriptPromise)
    assert promise.state == "fulfilled"
    assert promise.value == 5.0


def test_async_function_rejects_on_awaited_rejection() -> None:
    promise = evaluate_program('async function load() { return await Promise.reject("boom"); } load();')

    assert isinstance(promise, JavaScriptPromise)
    assert promise.state == "rejected"
    assert promise.value == "boom"


def test_async_arrow_function_works() -> None:
    promise = evaluate_program("var load = async x => await Promise.resolve(x + 1); load(4);")

    assert isinstance(promise, JavaScriptPromise)
    assert promise.state == "fulfilled"
    assert promise.value == 5.0


def test_async_method_works() -> None:
    promise = evaluate_program(
        "class Box { async load(x) { return await Promise.resolve(x + 2); } } "
        "new Box().load(5);"
    )

    assert isinstance(promise, JavaScriptPromise)
    assert promise.state == "fulfilled"
    assert promise.value == 7.0


def test_math_and_primitive_builtins_work() -> None:
    assert evaluate_program("Math.abs(-3);") == 3.0
    assert evaluate_program("Math.max(1, 5, 2);") == 5.0
    assert evaluate_program('Number("12");') == 12.0
    assert evaluate_program("String(12);") == "12"
    error = evaluate_program('Error("x");')
    assert error["name"] == "Error"
    assert error["message"] == "x"


def test_arrow_function_expression_body_works() -> None:
    assert evaluate_program("var inc = x => x + 1; inc(2);") == 3.0


def test_arrow_function_block_body_works() -> None:
    assert evaluate_program("var add = (x, y) => { return x + y; }; add(2, 3);") == 5.0


def test_arrow_function_lexically_captures_this() -> None:
    result = evaluate_program(
        "var o = { value: 7, get: function () { var f = () => this.value; return f(); } }; o.get();"
    )

    assert result == 7.0


def test_arrow_function_ignores_call_site_this() -> None:
    result = evaluate_program(
        "var outer = { value: 3, make: function () { return () => this.value; } }; "
        "var fn = outer.make(); "
        "var other = { value: 9, fn: fn }; "
        "other.fn();"
    )

    assert result == 3.0


def test_function_call_apply_and_bind_work() -> None:
    result = evaluate_program(
        "function read(x) { return this.value + x; } "
        "var ctx = { value: 4 }; "
        "var bound = read.bind(ctx, 2); "
        "read.call(ctx, 1) + read.apply(ctx, [2]) + bound();"
    )

    assert result == 17.0


def test_eval_supports_unicode_escape_whitespace_cases() -> None:
    assert evaluate_program('eval("1\\u0009+\\u00091");') == 2.0


def test_tagged_template_passes_cooked_and_raw_arrays() -> None:
    result = evaluate_program(
        "(function (s) { return s[0] + ':' + s.raw[0]; })`foo`;"
    )

    assert result == "foo:foo"


def test_instanceof_checks_constructor_prototype_chain() -> None:
    result = evaluate_program(
        "function Box() {} "
        "var box = new Box(); "
        "box instanceof Box;"
    )

    assert result is True


def test_postfix_increment_updates_identifier() -> None:
    result = evaluate_program("var calls = 0; calls++; calls;")

    assert result == 1.0


def test_class_constructor_and_method_work() -> None:
    result = evaluate_program(
        "class Point { "
        "  constructor(x, y) { this.x = x; this.y = y; } "
        "  sum() { return this.x + this.y; } "
        "} "
        "var p = new Point(2, 3); "
        "p.sum();"
    )

    assert result == 5.0


def test_class_methods_are_found_through_prototype_chain() -> None:
    result = evaluate_program(
        "class Counter { "
        "  constructor() { this.value = 1; } "
        "  inc() { this.value = this.value + 1; return this.value; } "
        "} "
        "var c = new Counter(); "
        "c.inc();"
    )

    assert result == 2.0


def test_new_requires_constructor_value() -> None:
    with pytest.raises(TypeError):
        evaluate_program("var x = {}; new x();")


def test_class_inheritance_uses_super_constructor() -> None:
    result = evaluate_program(
        "class Base { constructor(x) { this.x = x; } } "
        "class Child extends Base { constructor(x, y) { super(x); this.y = y; } sum() { return this.x + this.y; } } "
        "var c = new Child(2, 3); "
        "c.sum();"
    )

    assert result == 5.0


def test_class_inheritance_finds_parent_methods() -> None:
    result = evaluate_program(
        "class Base { greet() { return 7; } } "
        "class Child extends Base { } "
        "var c = new Child(); "
        "c.greet();"
    )

    assert result == 7.0


def test_super_method_call_uses_current_this() -> None:
    result = evaluate_program(
        "class Base { greet() { return this.value + 1; } } "
        "class Child extends Base { constructor() { super(); this.value = 4; } greet() { return super.greet() + 2; } } "
        "new Child().greet();"
    )

    assert result == 7.0


def test_derived_class_without_constructor_uses_parent_constructor() -> None:
    result = evaluate_program(
        "class Base { constructor(x) { this.x = x; } } "
        "class Child extends Base { } "
        "new Child(6).x;"
    )

    assert result == 6.0


def test_class_expression_can_be_instantiated() -> None:
    result = evaluate_program(
        "var Point = class { constructor(x) { this.x = x; } getX() { return this.x; } }; "
        "new Point(4).getX();"
    )

    assert result == 4.0


def test_named_class_expression_can_self_reference_in_static_method() -> None:
    result = evaluate_program(
        "var Point = class NamedPoint { "
        "  constructor(x) { this.x = x; } "
        "  static make(x) { return new NamedPoint(x); } "
        "}; "
        "Point.make(5).x;"
    )

    assert result == 5.0


def test_static_method_call_works() -> None:
    result = evaluate_program(
        "class MathBox { static sum(x, y) { return x + y; } } "
        "MathBox.sum(2, 3);"
    )

    assert result == 5.0


def test_static_method_is_not_on_instance() -> None:
    with pytest.raises(TypeError):
        evaluate_program(
            "class MathBox { static sum(x, y) { return x + y; } } "
            "new MathBox().sum(2, 3);"
        )


def test_instance_fields_initialize_on_construction() -> None:
    result = evaluate_program(
        "class Point { x = 1; y = 2; sum() { return this.x + this.y; } } "
        "new Point().sum();"
    )

    assert result == 3.0


def test_instance_fields_initialize_before_base_constructor_body() -> None:
    result = evaluate_program(
        "class Point { x = 1; constructor() { this.x = this.x + 4; } } "
        "new Point().x;"
    )

    assert result == 5.0


def test_instance_fields_initialize_after_super_in_derived_constructor() -> None:
    result = evaluate_program(
        "class Base { constructor() { this.base = 1; } } "
        "class Child extends Base { y = this.base + 1; constructor() { super(); this.z = this.y + this.base; } } "
        "new Child().z;"
    )

    assert result == 3.0


def test_derived_class_without_constructor_initializes_own_fields_after_super() -> None:
    result = evaluate_program(
        "class Base { constructor() { this.base = 2; } } "
        "class Child extends Base { y = this.base + 1; } "
        "new Child().y;"
    )

    assert result == 3.0


def test_instance_getter_reads_from_prototype_descriptor() -> None:
    result = evaluate_program(
        "class Box { get value() { return 7; } } "
        "new Box().value;"
    )

    assert result == 7.0


def test_instance_setter_writes_through_prototype_descriptor() -> None:
    result = evaluate_program(
        "class Box { set value(x) { this.stored = x + 1; } } "
        "var b = new Box(); "
        "b.value = 4; "
        "b.stored;"
    )

    assert result == 5.0


def test_static_getter_works() -> None:
    result = evaluate_program(
        "class Box { static get answer() { return 42; } } "
        "Box.answer;"
    )

    assert result == 42.0


def test_super_getter_uses_current_this() -> None:
    result = evaluate_program(
        "class Base { get value() { return this.x + 1; } } "
        "class Child extends Base { constructor() { super(); this.x = 4; } get value() { return super.value + 2; } } "
        "new Child().value;"
    )

    assert result == 7.0


def test_super_setter_uses_current_this() -> None:
    result = evaluate_program(
        "class Base { set value(x) { this.stored = x + 1; } } "
        "class Child extends Base { set value(x) { super.value = x + 2; } } "
        "var c = new Child(); "
        "c.value = 4; "
        "c.stored;"
    )

    assert result == 7.0


def test_static_field_initializes_on_class_definition() -> None:
    result = evaluate_program(
        "class Box { static answer = 42; } "
        "Box.answer;"
    )

    assert result == 42.0


def test_static_field_initializer_can_use_class_name() -> None:
    result = evaluate_program(
        "var Box = class NamedBox { static selfName = String(this.prototype !== null); }; "
        "Box.selfName;"
    )

    assert result == "true"


def test_static_field_initializer_can_use_static_method() -> None:
    result = evaluate_program(
        "class Box { static value() { return 7; } static answer = this.value() + 1; } "
        "Box.answer;"
    )

    assert result == 8.0


def test_computed_method_name_works() -> None:
    result = evaluate_program(
        'var name = "speak"; '
        'class Box { [name]() { return 7; } } '
        'new Box().speak();'
    )

    assert result == 7.0


def test_computed_instance_field_name_works() -> None:
    result = evaluate_program(
        'var key = "value"; '
        'class Box { [key] = 4; } '
        'new Box().value;'
    )

    assert result == 4.0


def test_computed_static_field_name_works() -> None:
    result = evaluate_program(
        'var key = "answer"; '
        'class Box { static [key] = 42; } '
        'Box.answer;'
    )

    assert result == 42.0


def test_computed_getter_and_setter_work() -> None:
    result = evaluate_program(
        'var key = "value"; '
        'class Box { '
        '  get [key]() { return this.stored + 1; } '
        '  set [key](x) { this.stored = x; } '
        '} '
        'var b = new Box(); '
        'b.value = 4; '
        'b.value;'
    )

    assert result == 5.0
