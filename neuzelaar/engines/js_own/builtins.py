"""Builtin host objects for the standalone JS interpreter."""

from __future__ import annotations

import json
import math
import random as _random

from neuzelaar.engines.js_own.host import ConstructibleHostObject, HostCallable, HostObject
from neuzelaar.engines.js_own.promises import create_promise_builtins
from neuzelaar.engines.js_own.runtime import JS_UNDEFINED, js_error_object, js_to_number, js_to_string


class _CallableConstructor(ConstructibleHostObject):
    def __init__(self, name: str, build_value) -> None:
        super().__init__(properties={}, construct_impl=lambda args: build_value(args))
        self.name = name
        self._build_value = build_value

    def call(self, arguments: tuple[object, ...], *, this_value: object = None) -> object:
        return self._build_value(arguments)


def _is_internal_key(name: str) -> bool:
    return name.startswith("__") or name == "constructor"


def install_builtins(environment) -> None:
    environment.declare("Math", _build_math(), kind="const")
    environment.declare("Number", _build_number(), kind="const")
    environment.declare(
        "String",
        HostCallable("String", lambda args, _this: js_to_string(args[0] if args else "")),
        kind="const",
    )
    environment.declare("Boolean", _build_boolean(), kind="const")
    environment.declare("Array", _build_array(), kind="const")
    environment.declare("Object", _build_object(), kind="const")
    environment.declare("JSON", _build_json(), kind="const")

    error_prototype: dict[str, object] = {}
    error_constructor = _CallableConstructor(
        "Error",
        lambda args: js_error_object(args[0] if args else ""),
    )
    error_constructor.set("prototype", error_prototype)
    error_constructor.set("name", "Error")
    environment.declare("Error", error_constructor, kind="const")
    for error_name in ("TypeError", "RangeError", "ReferenceError", "SyntaxError"):
        ctor = _CallableConstructor(
            error_name,
            (lambda name: lambda args: {"name": name, "message": js_to_string(args[0] if args else "")})(error_name),
        )
        ctor.set("prototype", error_prototype)
        ctor.set("name", error_name)
        environment.declare(error_name, ctor, kind="const")

    def _eval(args: tuple[object, ...], _this: object | None) -> object:
        from neuzelaar.engines.js_own.interpreter import evaluate_program_with_config

        source = js_to_string(args[0] if args else "")
        return evaluate_program_with_config(source, environment=environment)

    environment.declare("eval", HostCallable("eval", _eval), kind="const")
    environment.declare("undefined", JS_UNDEFINED, kind="const")
    environment.declare("Infinity", float("inf"), kind="const")
    environment.declare("NaN", float("nan"), kind="const")

    environment.declare("parseInt", HostCallable("parseInt", _parse_int), kind="const")
    environment.declare("parseFloat", HostCallable("parseFloat", _parse_float), kind="const")
    environment.declare("isNaN", HostCallable("isNaN", _global_is_nan), kind="const")
    environment.declare("isFinite", HostCallable("isFinite", _global_is_finite), kind="const")

    promise_constructor, queue_microtask = create_promise_builtins()
    environment.declare("Promise", promise_constructor, kind="const")
    environment.declare("queueMicrotask", queue_microtask, kind="const")


def _build_math() -> HostObject:
    def _wrap(name: str, fn):
        return HostCallable(f"Math.{name}", lambda args, _this: fn(args))

    def _one_arg(fn):
        def runner(args):
            value = js_to_number(args[0] if args else float("nan"))
            return fn(value)
        return runner

    def _safe_sqrt(x: float) -> float:
        if math.isnan(x) or x < 0:
            return float("nan")
        return math.sqrt(x)

    def _safe_log(x: float) -> float:
        if math.isnan(x) or x < 0:
            return float("nan")
        if x == 0:
            return float("-inf")
        return math.log(x)

    def _truncate(x: float) -> float:
        if math.isnan(x) or math.isinf(x):
            return x
        return float(math.trunc(x))

    def _round_half_away(x: float) -> float:
        # JS Math.round: rounds half toward +Infinity (NOT banker's rounding).
        if math.isnan(x) or math.isinf(x):
            return x
        return math.floor(x + 0.5)

    def _sign(x: float) -> float:
        if math.isnan(x):
            return float("nan")
        if x > 0:
            return 1.0
        if x < 0:
            return -1.0
        return 0.0

    def _max(args: tuple[object, ...]) -> float:
        if not args:
            return float("-inf")
        values = [js_to_number(arg) for arg in args]
        for v in values:
            if math.isnan(v):
                return float("nan")
        return max(values)

    def _min(args: tuple[object, ...]) -> float:
        if not args:
            return float("inf")
        values = [js_to_number(arg) for arg in args]
        for v in values:
            if math.isnan(v):
                return float("nan")
        return min(values)

    def _pow(args: tuple[object, ...]) -> float:
        base = js_to_number(args[0]) if args else float("nan")
        exp = js_to_number(args[1]) if len(args) > 1 else float("nan")
        try:
            return base ** exp
        except (ValueError, OverflowError):
            return float("nan")

    def _atan2(args: tuple[object, ...]) -> float:
        y = js_to_number(args[0]) if args else float("nan")
        x = js_to_number(args[1]) if len(args) > 1 else float("nan")
        return math.atan2(y, x)

    return HostObject(
        properties={
            "abs": _wrap("abs", _one_arg(lambda x: float("nan") if math.isnan(x) else abs(x))),
            "ceil": _wrap("ceil", _one_arg(lambda x: x if math.isnan(x) or math.isinf(x) else float(math.ceil(x)))),
            "floor": _wrap("floor", _one_arg(lambda x: x if math.isnan(x) or math.isinf(x) else float(math.floor(x)))),
            "round": _wrap("round", _one_arg(_round_half_away)),
            "trunc": _wrap("trunc", _one_arg(_truncate)),
            "sign": _wrap("sign", _one_arg(_sign)),
            "sqrt": _wrap("sqrt", _one_arg(_safe_sqrt)),
            "log": _wrap("log", _one_arg(_safe_log)),
            "log2": _wrap("log2", _one_arg(lambda x: float("nan") if math.isnan(x) or x < 0 else (float("-inf") if x == 0 else math.log2(x)))),
            "log10": _wrap("log10", _one_arg(lambda x: float("nan") if math.isnan(x) or x < 0 else (float("-inf") if x == 0 else math.log10(x)))),
            "exp": _wrap("exp", _one_arg(math.exp)),
            "sin": _wrap("sin", _one_arg(math.sin)),
            "cos": _wrap("cos", _one_arg(math.cos)),
            "tan": _wrap("tan", _one_arg(math.tan)),
            "asin": _wrap("asin", _one_arg(lambda x: float("nan") if math.isnan(x) or x < -1 or x > 1 else math.asin(x))),
            "acos": _wrap("acos", _one_arg(lambda x: float("nan") if math.isnan(x) or x < -1 or x > 1 else math.acos(x))),
            "atan": _wrap("atan", _one_arg(math.atan)),
            "atan2": _wrap("atan2", _atan2),
            "pow": _wrap("pow", _pow),
            "max": _wrap("max", _max),
            "min": _wrap("min", _min),
            "random": HostCallable("Math.random", lambda args, _this: _random.random()),
            "PI": math.pi,
            "E": math.e,
            "LN2": math.log(2),
            "LN10": math.log(10),
            "LOG2E": 1.0 / math.log(2),
            "LOG10E": 1.0 / math.log(10),
            "SQRT2": math.sqrt(2),
            "SQRT1_2": 1.0 / math.sqrt(2),
        }
    )


def _build_number() -> HostCallable:
    def _is_finite(args: tuple[object, ...], _this: object | None) -> bool:
        if not args or not isinstance(args[0], (int, float)) or isinstance(args[0], bool):
            return False
        value = float(args[0])
        return not (math.isnan(value) or math.isinf(value))

    def _is_nan(args: tuple[object, ...], _this: object | None) -> bool:
        return bool(args) and isinstance(args[0], float) and math.isnan(args[0])

    def _is_integer(args: tuple[object, ...], _this: object | None) -> bool:
        if not args or not isinstance(args[0], (int, float)) or isinstance(args[0], bool):
            return False
        value = float(args[0])
        return not math.isnan(value) and not math.isinf(value) and value.is_integer()

    return HostCallable(
        "Number",
        lambda args, _this: js_to_number(args[0] if args else 0.0),
        properties={
            "POSITIVE_INFINITY": float("inf"),
            "NEGATIVE_INFINITY": float("-inf"),
            "NaN": float("nan"),
            "MAX_SAFE_INTEGER": float(2 ** 53 - 1),
            "MIN_SAFE_INTEGER": -float(2 ** 53 - 1),
            "MAX_VALUE": 1.7976931348623157e308,
            "MIN_VALUE": 5e-324,
            "EPSILON": 2.220446049250313e-16,
            "isFinite": HostCallable("Number.isFinite", _is_finite),
            "isNaN": HostCallable("Number.isNaN", _is_nan),
            "isInteger": HostCallable("Number.isInteger", _is_integer),
        },
    )


def _build_boolean() -> HostCallable:
    from neuzelaar.engines.js_own.runtime import js_truthy

    return HostCallable("Boolean", lambda args, _this: js_truthy(args[0]) if args else False)


def _build_array() -> HostCallable:
    def _is_array(args: tuple[object, ...], _this: object | None) -> bool:
        return bool(args) and isinstance(args[0], list)

    def _array_from(args: tuple[object, ...], _this: object | None) -> list[object]:
        if not args:
            return []
        source = args[0]
        callback = args[1] if len(args) > 1 else None
        if isinstance(source, list):
            items = list(source)
        elif isinstance(source, str):
            items = list(source)
        else:
            items = []
        if callback is not None and hasattr(callback, "call"):
            return [
                callback.call((value, float(index)), this_value=None)
                for index, value in enumerate(items)
            ]
        return items

    def _array_of(args: tuple[object, ...], _this: object | None) -> list[object]:
        return list(args)

    def _array_constructor(args: tuple[object, ...]) -> list[object]:
        if len(args) == 1 and isinstance(args[0], (int, float)) and not isinstance(args[0], bool):
            length = int(args[0])
            return [JS_UNDEFINED] * length
        return list(args)

    constructor = HostCallable(
        "Array",
        lambda args, _this: _array_constructor(args),
        properties={
            "isArray": HostCallable("Array.isArray", _is_array),
            "from": HostCallable("Array.from", _array_from),
            "of": HostCallable("Array.of", _array_of),
        },
    )
    return constructor


def _build_object() -> HostObject:
    def _enumerable_keys(target: object) -> list[str]:
        if not isinstance(target, dict):
            return []
        return [k for k in target.keys() if not _is_internal_key(k)]

    def _object_create(args: tuple[object, ...], _this: object | None) -> object:
        if args and isinstance(args[0], dict):
            return {"__proto__": args[0]}
        return {}

    def _object_keys(args: tuple[object, ...], _this: object | None) -> list[object]:
        if not args:
            return []
        return list(_enumerable_keys(args[0]))

    def _object_values(args: tuple[object, ...], _this: object | None) -> list[object]:
        if not args or not isinstance(args[0], dict):
            return []
        return [args[0][k] for k in _enumerable_keys(args[0])]

    def _object_entries(args: tuple[object, ...], _this: object | None) -> list[object]:
        if not args or not isinstance(args[0], dict):
            return []
        return [[k, args[0][k]] for k in _enumerable_keys(args[0])]

    def _object_assign(args: tuple[object, ...], _this: object | None) -> object:
        if not args:
            return {}
        target = args[0]
        if not isinstance(target, dict):
            raise TypeError("Object.assign target must be an object")
        for source in args[1:]:
            if not isinstance(source, dict):
                continue
            for key in _enumerable_keys(source):
                target[key] = source[key]
        return target

    def _object_freeze(args: tuple[object, ...], _this: object | None) -> object:
        # No-op: we don't enforce frozen state, but accept the call.
        return args[0] if args else JS_UNDEFINED

    def _object_from_entries(args: tuple[object, ...], _this: object | None) -> dict[str, object]:
        if not args:
            return {}
        source = args[0]
        result: dict[str, object] = {}
        if isinstance(source, list):
            for entry in source:
                if isinstance(entry, list) and len(entry) >= 2:
                    result[js_to_string(entry[0])] = entry[1]
        return result

    return HostObject(
        properties={
            "create": HostCallable("Object.create", _object_create),
            "keys": HostCallable("Object.keys", _object_keys),
            "values": HostCallable("Object.values", _object_values),
            "entries": HostCallable("Object.entries", _object_entries),
            "assign": HostCallable("Object.assign", _object_assign),
            "freeze": HostCallable("Object.freeze", _object_freeze),
            "fromEntries": HostCallable("Object.fromEntries", _object_from_entries),
        }
    )


def _build_json() -> HostObject:
    def _to_jsonable(value: object) -> object:
        if value is None:
            return None
        if value is JS_UNDEFINED:
            return None  # caller handles "skip" semantics by returning sentinel
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                return None
            # JSON.stringify(1.0) should produce "1", not "1.0".
            if isinstance(value, float) and value.is_integer():
                return int(value)
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return [
                _to_jsonable(item) if item is not JS_UNDEFINED else None
                for item in value
            ]
        if isinstance(value, dict):
            obj: dict[str, object] = {}
            for k, v in value.items():
                if _is_internal_key(k):
                    continue
                if v is JS_UNDEFINED or hasattr(v, "call"):
                    continue  # JSON skips undefined and function values in objects
                obj[k] = _to_jsonable(v)
            return obj
        if hasattr(value, "call"):
            return None
        return None

    def _json_stringify(args: tuple[object, ...], _this: object | None) -> object:
        if not args:
            return JS_UNDEFINED
        value = args[0]
        if value is JS_UNDEFINED or hasattr(value, "call"):
            return JS_UNDEFINED
        indent: int | None = None
        if len(args) > 2 and args[2] is not JS_UNDEFINED:
            raw_indent = args[2]
            if isinstance(raw_indent, (int, float)) and not isinstance(raw_indent, bool):
                indent = max(0, min(10, int(raw_indent)))
        prepared = _to_jsonable(value)
        if indent is not None:
            return json.dumps(prepared, indent=indent, ensure_ascii=False)
        return json.dumps(prepared, ensure_ascii=False, separators=(",", ":"))

    def _from_python_json(value: object) -> object:
        if isinstance(value, dict):
            return {k: _from_python_json(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_from_python_json(v) for v in value]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return float(value)
        return value

    def _json_parse(args: tuple[object, ...], _this: object | None) -> object:
        source = js_to_string(args[0] if args else "")
        try:
            parsed = json.loads(source)
        except json.JSONDecodeError as exc:
            raise TypeError(f"JSON.parse: {exc.msg} at position {exc.pos}")
        return _from_python_json(parsed)

    return HostObject(
        properties={
            "stringify": HostCallable("JSON.stringify", _json_stringify),
            "parse": HostCallable("JSON.parse", _json_parse),
        }
    )


def _parse_int(args: tuple[object, ...], _this: object | None) -> float:
    if not args:
        return float("nan")
    source = js_to_string(args[0]).strip()
    radix_arg: int | None = None
    if len(args) > 1 and args[1] is not JS_UNDEFINED:
        radix_raw = js_to_number(args[1])
        if not math.isnan(radix_raw):
            radix_arg = int(radix_raw)
    if not source:
        return float("nan")
    sign = 1.0
    if source[0] in "+-":
        if source[0] == "-":
            sign = -1.0
        source = source[1:]
    radix = radix_arg
    if source[:2].lower() == "0x" and (radix is None or radix == 0 or radix == 16):
        source = source[2:]
        radix = 16
    if radix is None or radix == 0:
        radix = 10
    if radix < 2 or radix > 36:
        return float("nan")
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"[:radix]
    consumed = ""
    for ch in source.lower():
        if ch in digits:
            consumed += ch
        else:
            break
    if not consumed:
        return float("nan")
    return sign * float(int(consumed, radix))


def _parse_float(args: tuple[object, ...], _this: object | None) -> float:
    if not args:
        return float("nan")
    source = js_to_string(args[0]).strip()
    if not source:
        return float("nan")
    # Accept the longest valid float prefix.
    import re

    match = re.match(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?", source)
    if not match:
        if source.startswith("Infinity") or source.startswith("+Infinity"):
            return float("inf")
        if source.startswith("-Infinity"):
            return float("-inf")
        return float("nan")
    try:
        return float(match.group(0))
    except ValueError:
        return float("nan")


def _global_is_nan(args: tuple[object, ...], _this: object | None) -> bool:
    if not args:
        return True
    value = js_to_number(args[0])
    return math.isnan(value)


def _global_is_finite(args: tuple[object, ...], _this: object | None) -> bool:
    if not args:
        return False
    value = js_to_number(args[0])
    return not (math.isnan(value) or math.isinf(value))
