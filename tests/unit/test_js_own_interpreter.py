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


def test_return_without_value_produces_undefined() -> None:
    from neuzelaar.engines.js_own.runtime import JS_UNDEFINED

    result = evaluate_program("function f() { return; } f();")

    assert result is JS_UNDEFINED


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


def test_prefix_increment_updates_identifier() -> None:
    result = evaluate_program("var calls = 0; ++calls;")

    assert result == 1.0


def test_function_arguments_binding_exists() -> None:
    result = evaluate_program("function read() { return arguments[1]; } read(3, 4, 5);")

    assert result == 4.0


def test_function_calls_keep_separate_var_scope_per_invocation() -> None:
    result = evaluate_program(
        "function make(name) { return { done: function() { return name; } }; } "
        "var t1 = make('one'); "
        "var t2 = make('two'); "
        "t1.done();"
    )

    assert result == "one"


def test_typeof_and_object_method_shorthand_work() -> None:
    result = evaluate_program(
        "var obj = { handleEvent() { return typeof queueMicrotask; } }; obj.handleEvent();"
    )

    assert result == "function"


def test_try_catch_can_catch_runtime_type_error() -> None:
    result = evaluate_program(
        "try { queueMicrotask(); } catch (error) { error.name; }"
    )

    assert result == "TypeError"


def test_while_statement_runs_until_condition_is_false() -> None:
    result = evaluate_program("var x = 0; while (x < 3) { x = x + 1; } x;")

    assert result == 3.0


def test_array_push_appends_values() -> None:
    result = evaluate_program("var xs = []; xs.push('a'); xs.push('b'); xs.length;")

    assert result == 2.0


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


def test_division_by_zero_yields_infinity() -> None:
    assert evaluate_expression("1 / 0") == math.inf
    assert evaluate_expression("-1 / 0") == -math.inf


def test_zero_divided_by_zero_yields_nan() -> None:
    result = evaluate_expression("0 / 0")
    assert isinstance(result, float)
    assert math.isnan(result)


def test_modulo_by_zero_yields_nan() -> None:
    result = evaluate_expression("5 % 0")
    assert isinstance(result, float)
    assert math.isnan(result)


def test_modulo_with_negative_divisor_uses_truncated_division() -> None:
    # JS: 5 % -2 === 1 (truncated division), not Python's -1 (floored).
    assert evaluate_expression("5 % -2") == 1.0


def test_nan_global_is_available() -> None:
    result = evaluate_expression("NaN")
    assert isinstance(result, float)
    assert math.isnan(result)


def test_infinity_globals_format_correctly_in_strings() -> None:
    assert evaluate_expression('"" + (1 / 0)') == "Infinity"
    assert evaluate_expression('"" + (-1 / 0)') == "-Infinity"
    assert evaluate_expression('"" + NaN') == "NaN"


def test_calling_class_without_new_raises_type_error() -> None:
    with pytest.raises(JavaScriptThrownValue) as info:
        evaluate_program(
            "class Foo { constructor() { this.x = 1; } } "
            "try { Foo(); } catch (e) { throw e; }"
        )
    error = info.value.value
    assert isinstance(error, dict)
    assert error.get("name") == "TypeError"
    assert "Foo" in str(error.get("message", ""))


def test_class_can_still_be_constructed_with_new() -> None:
    result = evaluate_program(
        "class Foo { constructor(n) { this.n = n; } } new Foo(7).n;"
    )
    assert result == 7.0


def test_object_strict_equality_uses_reference_identity() -> None:
    assert evaluate_expression("({}) === ({})") is False
    assert evaluate_expression("[] === []") is False


def test_object_strict_equality_same_reference_is_true() -> None:
    assert evaluate_program("var o = {x: 1}; o === o;") is True
    assert evaluate_program("var a = [1, 2]; a === a;") is True


def test_distinct_object_literals_with_same_shape_are_not_equal() -> None:
    assert evaluate_program('var a = {x:1}; var b = {x:1}; a === b;') is False
    assert evaluate_program('var a = [1,2]; var b = [1,2]; a === b;') is False


def test_typeof_undeclared_identifier_returns_undefined() -> None:
    assert evaluate_expression("typeof undeclaredFoo") == "undefined"


def test_typeof_distinguishes_undefined_from_null() -> None:
    assert evaluate_expression("typeof undefined") == "undefined"
    assert evaluate_expression("typeof null") == "object"


def test_typeof_missing_property_is_undefined() -> None:
    assert evaluate_program("var o = {}; typeof o.missing;") == "undefined"


def test_undefined_strict_inequality_to_null() -> None:
    assert evaluate_expression("null === undefined") is False
    assert evaluate_expression("null == undefined") is True


def test_missing_property_is_strictly_undefined_not_null() -> None:
    assert evaluate_program("var o = {}; o.x === undefined;") is True
    assert evaluate_program("var o = {}; o.x === null;") is False


def test_uninitialized_var_is_undefined() -> None:
    assert evaluate_program("var x; x === undefined;") is True
    assert evaluate_program("let x; x === undefined;") is True


def test_function_with_no_return_yields_undefined() -> None:
    assert evaluate_program("function f() {} f() === undefined;") is True


def test_missing_function_argument_is_undefined() -> None:
    assert evaluate_program("function f(a, b) { return b; } f(1) === undefined;") is True


def test_undefined_arithmetic_yields_nan() -> None:
    result = evaluate_expression("undefined + 1")
    assert isinstance(result, float)
    assert math.isnan(result)


def test_typeof_in_async_function_handles_undeclared() -> None:
    promise = evaluate_program("async function f() { return typeof undeclaredAsyncVar; } f();")
    assert promise.state == "fulfilled"
    assert promise.value == "undefined"


def test_function_declaration_is_hoisted_above_first_call() -> None:
    result = evaluate_program("var r = f(); function f() { return 42; } r;")
    assert result == 42.0


def test_var_is_hoisted_so_typeof_returns_undefined_before_init() -> None:
    result = evaluate_program("function h() { return typeof y; var y = 1; } h();")
    assert result == "undefined"


def test_var_assignment_before_declaration_in_function_body() -> None:
    result = evaluate_program("function g() { y = 5; var y; return y; } g();")
    assert result == 5.0


def test_function_decl_in_if_block_is_hoisted_to_function_scope() -> None:
    result = evaluate_program(
        "function w() { if (true) { function inner() { return 7; } } return inner(); } w();"
    )
    assert result == 7.0


def test_bare_var_after_function_decl_does_not_overwrite() -> None:
    # function f(){} var f;  — JS leaves f as the function (var without init is a no-op)
    result = evaluate_program("function z() { return 9; } var z; typeof z;")
    assert result == "function"


def test_let_redeclaration_raises_syntax_error() -> None:
    with pytest.raises(JavaScriptSyntaxError):
        evaluate_program("let x = 1; let x = 2;")


def test_const_redeclaration_raises_syntax_error() -> None:
    with pytest.raises(JavaScriptSyntaxError):
        evaluate_program("const x = 1; const x = 2;")


def test_let_in_different_blocks_does_not_clash() -> None:
    # Inner let shadows outer; outer remains unchanged after block.
    assert evaluate_program("let x = 1; { let x = 2; } x;") == 1.0


def test_var_can_still_be_redeclared() -> None:
    assert evaluate_program("var x = 1; var x = 2; x;") == 2.0


def test_float_property_key_round_trips() -> None:
    assert evaluate_program('var o = {}; o[1.5] = "x"; o[1.5];') == "x"


def test_integer_and_float_property_keys_collapse_for_whole_numbers() -> None:
    # JS: o[1] and o[1.0] are the same key "1"
    assert evaluate_program('var o = {}; o[1] = "a"; o[1.0];') == "a"


def test_boolean_property_key_coerces_to_string() -> None:
    # JS: o[true] === o["true"]
    assert evaluate_program('var o = {}; o[true] = "b"; o["true"];') == "b"


def test_deep_recursion_surfaces_as_range_error() -> None:
    with pytest.raises(JavaScriptThrownValue) as info:
        evaluate_program(
            "function r(n) { if (n <= 0) return 0; return 1 + r(n - 1); } r(2000);"
        )
    error = info.value.value
    assert isinstance(error, dict)
    assert error.get("name") == "RangeError"


def test_deep_recursion_is_catchable_in_js_try_catch() -> None:
    result = evaluate_program(
        "function r(n) { if (n <= 0) return 0; return 1 + r(n - 1); } "
        'try { r(2000); "no"; } catch (e) { e.name + ":" + e.message; }'
    )
    assert result == "RangeError:Maximum call stack size exceeded"


def test_classic_for_loop_sums() -> None:
    assert evaluate_program("var s = 0; for (var i = 1; i <= 10; i = i + 1) s = s + i; s;") == 55.0


def test_for_loop_with_let_init() -> None:
    assert evaluate_program("var s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; s;") == 10.0


def test_break_exits_while_loop() -> None:
    assert evaluate_program("var i = 0; while (true) { if (i >= 3) break; i = i + 1; } i;") == 3.0


def test_continue_skips_iteration() -> None:
    assert evaluate_program(
        "var s = 0; for (var i = 0; i < 5; i = i + 1) { if (i === 2) continue; s = s + i; } s;"
    ) == 8.0


def test_break_only_exits_inner_of_nested_loops() -> None:
    assert evaluate_program(
        "var s = 0; "
        "for (var i = 0; i < 3; i = i + 1) { "
        "  for (var j = 0; j < 3; j = j + 1) { if (j === 1) break; s = s + 10; } "
        "} "
        "s;"
    ) == 30.0


def test_for_with_empty_clauses_runs_until_break() -> None:
    assert evaluate_program("var i = 0; for (;;) { i = i + 1; if (i >= 3) break; } i;") == 3.0


def test_break_outside_loop_is_syntax_error() -> None:
    with pytest.raises(JavaScriptSyntaxError):
        evaluate_program("break;")


def test_continue_outside_loop_is_syntax_error() -> None:
    with pytest.raises(JavaScriptSyntaxError):
        evaluate_program("continue;")


def test_for_loop_inside_async_function_works() -> None:
    promise = evaluate_program(
        "async function f() { var s = 0; for (var i = 0; i < 5; i = i + 1) s = s + i; return s; } f();"
    )
    assert promise.state == "fulfilled"
    assert promise.value == 10.0


def test_postfix_decrement_returns_old_value() -> None:
    assert evaluate_program("var x = 5; var y = x--; x + y * 10;") == 54.0


def test_prefix_decrement_returns_new_value() -> None:
    assert evaluate_program("var x = 5; var y = --x; x + y * 10;") == 44.0


def test_decrement_works_in_for_loop_update() -> None:
    assert evaluate_program("var s = 0; for (var i = 5; i > 0; i--) s = s + i; s;") == 15.0


def test_decrement_works_on_index_target() -> None:
    assert evaluate_program("var a = [3, 3]; a[0]--; a[0];") == 2.0


def test_ternary_conditional_basic() -> None:
    assert evaluate_expression('1 < 2 ? "yes" : "no"') == "yes"
    assert evaluate_expression('1 > 2 ? "yes" : "no"') == "no"


def test_ternary_is_right_associative() -> None:
    assert (
        evaluate_program('var x = 2; x === 1 ? "one" : x === 2 ? "two" : "other";')
        == "two"
    )


def test_ternary_lower_precedence_than_addition() -> None:
    # 1 + 2 binds first; the truthy 3 selects "yes".
    assert evaluate_expression('1 + 2 ? "yes" : "no"') == "yes"


def test_ternary_works_inside_async_function() -> None:
    promise = evaluate_program(
        'async function f() { return 1 < 2 ? "yes" : "no"; } f();'
    )
    assert promise.state == "fulfilled"
    assert promise.value == "yes"


def test_ternary_branches_can_contain_assignments() -> None:
    result = evaluate_program(
        "var a = 0; var b = 0; true ? (a = 1) : (b = 1); a + b * 10;"
    )
    assert result == 1.0


def test_parenthesised_assignment_no_longer_misparsed_as_arrow() -> None:
    # Used to fail: (a = 5) entered the arrow-detection path and raised
    # before the speculative parse could roll back.
    assert evaluate_program("var a; (a = 5); a;") == 5.0


def test_compound_assignment_plus_eq() -> None:
    assert evaluate_program("var x = 5; x += 3; x;") == 8.0


def test_compound_assignment_minus_eq() -> None:
    assert evaluate_program("var x = 10; x -= 4; x;") == 6.0


def test_compound_assignment_times_eq() -> None:
    assert evaluate_program("var x = 2; x *= 5; x;") == 10.0


def test_compound_assignment_div_eq() -> None:
    assert evaluate_program("var x = 10; x /= 2; x;") == 5.0


def test_compound_assignment_mod_eq() -> None:
    assert evaluate_program("var x = 10; x %= 3; x;") == 1.0


def test_compound_assignment_works_on_member_target() -> None:
    assert evaluate_program("var o = { count: 0 }; o.count += 5; o.count;") == 5.0


def test_compound_assignment_works_on_index_target() -> None:
    assert evaluate_program("var a = [10]; a[0] += 5; a[0];") == 15.0


def test_compound_assignment_string_concatenation() -> None:
    assert evaluate_program('var s = "hi "; s += "world"; s;') == "hi world"


def test_compound_assignment_chains_right_associatively() -> None:
    # a = (b += 5)
    result = evaluate_program("var a = 0; var b = 0; a = b += 5; a + b * 10;")
    assert result == 55.0


def test_compound_assignment_with_await_on_rhs() -> None:
    promise = evaluate_program(
        "async function f() { var x = 10; x += await Promise.resolve(7); return x; } f();"
    )
    assert promise.state == "fulfilled"
    assert promise.value == 17.0


def test_exponentiation_basic() -> None:
    assert evaluate_expression("2 ** 8") == 256.0


def test_exponentiation_is_right_associative() -> None:
    # 2 ** 3 ** 2  ==  2 ** (3 ** 2)  ==  2 ** 9  ==  512
    assert evaluate_expression("2 ** 3 ** 2") == 512.0


def test_exponentiation_works_in_async() -> None:
    promise = evaluate_program("async function f() { return 2 ** 8; } f();")
    assert promise.state == "fulfilled"
    assert promise.value == 256.0


def test_nullish_coalesce_returns_left_for_non_nullish() -> None:
    assert evaluate_program('"value" ?? "default";') == "value"


def test_nullish_coalesce_does_not_short_circuit_on_zero() -> None:
    assert evaluate_program("0 ?? 99;") == 0.0


def test_nullish_coalesce_does_not_short_circuit_on_empty_string() -> None:
    assert evaluate_program('"" ?? "default";') == ""


def test_nullish_coalesce_uses_right_for_null() -> None:
    assert evaluate_program('null ?? "default";') == "default"


def test_nullish_coalesce_uses_right_for_undefined() -> None:
    assert evaluate_program('undefined ?? "default";') == "default"


def test_nullish_coalesce_works_in_async() -> None:
    promise = evaluate_program(
        'async function f() { return null ?? await Promise.resolve("via-await"); } f();'
    )
    assert promise.state == "fulfilled"
    assert promise.value == "via-await"


def test_string_length() -> None:
    assert evaluate_expression('"hello".length') == 5.0


def test_string_indexing() -> None:
    assert evaluate_expression('"hello"[1]') == "e"


def test_string_index_out_of_range_is_undefined() -> None:
    from neuzelaar.engines.js_own.runtime import JS_UNDEFINED

    assert evaluate_expression('"abc"[100]') is JS_UNDEFINED


def test_string_methods_basic() -> None:
    assert evaluate_expression('"hello".toUpperCase()') == "HELLO"
    assert evaluate_expression('"HELLO".toLowerCase()') == "hello"
    assert evaluate_expression('"  spaces  ".trim()') == "spaces"


def test_string_slice_and_substring() -> None:
    assert evaluate_expression('"hello world".slice(6)') == "world"
    assert evaluate_expression('"hello world".slice(0, 5)') == "hello"
    assert evaluate_expression('"hello world".substring(0, 5)') == "hello"


def test_string_index_of_and_includes() -> None:
    assert evaluate_expression('"hello world".indexOf("world")') == 6.0
    assert evaluate_expression('"hello world".indexOf("xyz")') == -1.0
    assert evaluate_expression('"hello world".includes("world")') is True
    assert evaluate_expression('"hello world".includes("xyz")') is False


def test_string_starts_and_ends_with() -> None:
    assert evaluate_expression('"hello".startsWith("he")') is True
    assert evaluate_expression('"hello".endsWith("lo")') is True
    assert evaluate_expression('"hello".startsWith("ll", 2)') is True


def test_string_split_returns_array() -> None:
    result = evaluate_program('"a,b,c".split(",");')
    assert result == ["a", "b", "c"]


def test_string_replace_only_first_occurrence() -> None:
    # JS replace(string, string) replaces only the first match.
    assert evaluate_expression('"foo bar foo".replace("foo", "baz")') == "baz bar foo"


def test_string_replace_all() -> None:
    assert evaluate_expression('"foo bar foo".replaceAll("foo", "baz")') == "baz bar baz"


def test_string_repeat() -> None:
    assert evaluate_expression('"ab".repeat(3)') == "ababab"


def test_string_concat() -> None:
    assert evaluate_expression('"hi".concat(" ", "world")') == "hi world"


def test_string_pad_start() -> None:
    assert evaluate_expression('"5".padStart(3, "0")') == "005"


def test_string_methods_chain() -> None:
    assert evaluate_program('"  Hello  ".trim().toLowerCase();') == "hello"


def test_string_char_code_at() -> None:
    assert evaluate_expression('"A".charCodeAt(0)') == 65.0
