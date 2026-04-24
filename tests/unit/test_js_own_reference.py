import pytest

from neuzelaar.engines.js_own.interpreter import evaluate_program

quickjs = pytest.importorskip("quickjs")


CASES = [
    "1 + 2 * 3",
    '"a" + 2',
    '"2" == 2',
    '"2" === 2',
    "null + 2",
    '"" || "fallback"',
    '"left" && "right"',
    "!(1 < 2)",
    "var x = 1; x = x + 2; x;",
    "let x = 1; { let x = 2; x; } x;",
    "{ var x = 4; } x;",
    'if (false) { "a"; } else { "b"; }',
    "function add(a, b) { return a + b; } add(2, 3);",
    "(function (x) { return x + 1; })(2);",
    "function outer(x) { function inner(y) { return x + y; } return inner; } var add2 = outer(2); add2(3);",
    "function fact(n) { if (n === 0) { return 1; } return n * fact(n - 1); } fact(5);",
    "var a = [1, 2, 3]; a[1];",
    'var o = { x: 1, "y": 2 }; o.x + o["y"];',
    "var a = [1, 2]; a[1] = 9; a[1];",
    "var o = { x: 1 }; o.x = 4; o.x;",
    "var a = [1, 2, 3]; a.length;",
    "var o = { value: 7, get: function () { return this.value; } }; o.get();",
    'var o = { value: 8, get: function () { return this["value"]; } }; o["get"]();',
    'try { throw "x"; } catch (e) { e; }',
    "function f() { try { return 1; } finally { return 2; } } f();",
    "Math.abs(-3);",
    "Math.max(1, 5, 2);",
    'Number("12");',
    "String(12);",
    'Error("x").message;',
    "var inc = x => x + 1; inc(2);",
    "var add = (x, y) => { return x + y; }; add(2, 3);",
    "var o = { value: 7, get: function () { var f = () => this.value; return f(); } }; o.get();",
    "var outer = { value: 3, make: function () { return () => this.value; } }; var fn = outer.make(); var other = { value: 9, fn: fn }; other.fn();",
    "class Point { constructor(x, y) { this.x = x; this.y = y; } sum() { return this.x + this.y; } } var p = new Point(2, 3); p.sum();",
    "class Counter { constructor() { this.value = 1; } inc() { this.value = this.value + 1; return this.value; } } var c = new Counter(); c.inc();",
    "class Base { constructor(x) { this.x = x; } } class Child extends Base { constructor(x, y) { super(x); this.y = y; } sum() { return this.x + this.y; } } var c = new Child(2, 3); c.sum();",
    "class Base { greet() { return 7; } } class Child extends Base { } var c = new Child(); c.greet();",
    "class Base { greet() { return this.value + 1; } } class Child extends Base { constructor() { super(); this.value = 4; } greet() { return super.greet() + 2; } } new Child().greet();",
    "class Base { constructor(x) { this.x = x; } } class Child extends Base { } new Child(6).x;",
    "var Point = class { constructor(x) { this.x = x; } getX() { return this.x; } }; new Point(4).getX();",
    "var Point = class NamedPoint { constructor(x) { this.x = x; } static make(x) { return new NamedPoint(x); } }; Point.make(5).x;",
    "class MathBox { static sum(x, y) { return x + y; } } MathBox.sum(2, 3);",
    "class Point { x = 1; y = 2; sum() { return this.x + this.y; } } new Point().sum();",
    "class Point { x = 1; constructor() { this.x = this.x + 4; } } new Point().x;",
    "class Base { constructor() { this.base = 1; } } class Child extends Base { y = this.base + 1; constructor() { super(); this.z = this.y + this.base; } } new Child().z;",
    "class Base { constructor() { this.base = 2; } } class Child extends Base { y = this.base + 1; } new Child().y;",
    "class Box { get value() { return 7; } } new Box().value;",
    "class Box { set value(x) { this.stored = x + 1; } } var b = new Box(); b.value = 4; b.stored;",
    "class Box { static get answer() { return 42; } } Box.answer;",
    "class Base { get value() { return this.x + 1; } } class Child extends Base { constructor() { super(); this.x = 4; } get value() { return super.value + 2; } } new Child().value;",
    "class Base { set value(x) { this.stored = x + 1; } } class Child extends Base { set value(x) { super.value = x + 2; } } var c = new Child(); c.value = 4; c.stored;",
]


@pytest.mark.parametrize("source", CASES)
def test_own_interpreter_matches_quickjs_for_supported_cases(source: str) -> None:
    context = quickjs.Context()
    actual = evaluate_program(source)
    expected = context.eval(source)

    assert actual == expected
