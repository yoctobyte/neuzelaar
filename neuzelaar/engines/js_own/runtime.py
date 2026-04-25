"""Runtime helpers for the standalone JS interpreter."""

from __future__ import annotations

import math


def is_js_object(value: object) -> bool:
    return value is not None and not isinstance(value, (bool, int, float, str))


def js_truthy(value: object) -> bool:
    if value is None:
        return False
    if value is False:
        return False
    if value == 0 or value == 0.0:
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
    return left == right


def js_loose_equal(left: object, right: object) -> bool:
    if left is None and right is None:
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
    if left is None or right is None:
        return False
    return False


def js_to_number(value: object) -> float:
    return _to_number(value)


def js_add(left: object, right: object) -> object:
    if isinstance(left, str) or isinstance(right, str):
        return js_to_string(left) + js_to_string(right)
    return js_to_number(left) + js_to_number(right)


def js_to_string(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
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
