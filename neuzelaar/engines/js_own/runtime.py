"""Runtime helpers for the standalone JS interpreter."""

from __future__ import annotations

import math


class _UndefinedType:
    __slots__ = ()
    _instance: "_UndefinedType | None" = None

    def __new__(cls) -> "_UndefinedType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _UndefinedType)

    def __ne__(self, other: object) -> bool:
        return not isinstance(other, _UndefinedType)

    def __hash__(self) -> int:
        return 0xC0DE_DEF


JS_UNDEFINED: _UndefinedType = _UndefinedType()


def is_js_object(value: object) -> bool:
    if value is None or isinstance(value, _UndefinedType):
        return False
    return not isinstance(value, (bool, int, float, str))


def js_typeof(value: object) -> str:
    if isinstance(value, _UndefinedType):
        return "undefined"
    if value is None:
        return "object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if hasattr(value, "call"):
        return "function"
    return "object"


def js_truthy(value: object) -> bool:
    if value is None or isinstance(value, _UndefinedType):
        return False
    if value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if value == "":
        return False
    return True


def js_typeof_equal(left: object, right: object) -> bool:
    return _js_type_name(left) == _js_type_name(right)


def js_strict_equal(left: object, right: object) -> bool:
    if isinstance(left, float) and math.isnan(left):
        return False
    if isinstance(right, float) and math.isnan(right):
        return False
    if not js_typeof_equal(left, right):
        return False
    if is_js_object(left) and is_js_object(right):
        return left is right
    return left == right


def js_loose_equal(left: object, right: object) -> bool:
    left_nullish = left is None or isinstance(left, _UndefinedType)
    right_nullish = right is None or isinstance(right, _UndefinedType)
    if left_nullish and right_nullish:
        return True
    if js_typeof_equal(left, right):
        return js_strict_equal(left, right)
    if isinstance(left, bool):
        return js_loose_equal(float(left), right)
    if isinstance(right, bool):
        return js_loose_equal(left, float(right))
    if isinstance(left, str) and isinstance(right, (int, float)):
        return js_loose_equal(_to_number(left), right)
    if isinstance(right, str) and isinstance(left, (int, float)):
        return js_loose_equal(left, _to_number(right))
    if left_nullish or right_nullish:
        return False
    return False


def js_to_number(value: object) -> float:
    return _to_number(value)


def js_add(left: object, right: object) -> object:
    if isinstance(left, str) or isinstance(right, str):
        return js_to_string(left) + js_to_string(right)
    return js_to_number(left) + js_to_number(right)


def js_divide(left: object, right: object) -> float:
    numerator = js_to_number(left)
    divisor = js_to_number(right)
    if math.isnan(numerator) or math.isnan(divisor):
        return math.nan
    if divisor == 0.0:
        if numerator == 0.0:
            return math.nan
        sign = math.copysign(1.0, numerator) * math.copysign(1.0, divisor)
        return math.copysign(math.inf, sign)
    return numerator / divisor


def js_modulo(left: object, right: object) -> float:
    numerator = js_to_number(left)
    divisor = js_to_number(right)
    if math.isnan(numerator) or math.isnan(divisor):
        return math.nan
    if divisor == 0.0 or math.isinf(numerator):
        return math.nan
    if math.isinf(divisor):
        return numerator
    return math.fmod(numerator, divisor)


def js_to_string(value: object) -> str:
    if isinstance(value, _UndefinedType):
        return "undefined"
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def js_error_object(message: object) -> dict[str, object]:
    return {
        "name": "Error",
        "message": js_to_string(message),
    }


def _js_type_name(value: object) -> str:
    if isinstance(value, _UndefinedType):
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _to_number(value: object) -> float:
    if isinstance(value, _UndefinedType):
        return math.nan
    if value is None:
        return 0.0
    if value is True:
        return 1.0
    if value is False:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return 0.0
        try:
            return float(stripped)
        except ValueError:
            return math.nan
    return math.nan
