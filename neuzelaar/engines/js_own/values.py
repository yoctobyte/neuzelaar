"""Runtime value helpers for the standalone JS interpreter."""

from __future__ import annotations

import math

from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.runtime import JS_UNDEFINED, js_to_number, js_to_string


def _lookup_dict_property(target: dict[str, object], property_name: str) -> object:
    if property_name in target:
        return target[property_name]
    prototype = target.get("__proto__")
    if isinstance(prototype, dict):
        return _lookup_dict_property(prototype, property_name)
    return JS_UNDEFINED


def _resolve_descriptor(value: object, receiver: object) -> object:
    if isinstance(value, dict) and ("get" in value or "set" in value):
        getter = value.get("get")
        if getter is None:
            return None
        return getter.call((), this_value=receiver)
    return value


def read_property(target: object, property_name: str, *, receiver: object | None = None) -> object:
    if isinstance(target, HostCallable):
        return target.properties.get(property_name, JS_UNDEFINED)
    if hasattr(target, "call") and not hasattr(target, "static_properties"):
        prototype = getattr(target, "prototype", None)
        if property_name == "prototype" and prototype is not None:
            return prototype
        if property_name == "call":
            return HostCallable(
                "Function.call",
                lambda args, _this: target.call(tuple(args[1:]), this_value=args[0] if args else None),
            )
        if property_name == "apply":
            return HostCallable(
                "Function.apply",
                lambda args, _this: target.call(
                    tuple(args[1]) if len(args) > 1 and isinstance(args[1], list) else (),
                    this_value=args[0] if args else None,
                ),
            )
        if property_name == "bind":
            def _bind(args: tuple[object, ...], _this: object | None) -> object:
                bound_this = args[0] if args else None
                bound_args = tuple(args[1:])
                return HostCallable(
                    "Function.bound",
                    lambda call_args, __this: target.call(bound_args + tuple(call_args), this_value=bound_this),
                )

            return HostCallable("Function.bind", _bind)
    if isinstance(target, HostObject):
        return target.get(property_name)
    if hasattr(target, "static_properties") and hasattr(target, "prototype"):
        if property_name == "prototype":
            return target.prototype
        return _resolve_descriptor(
            target.static_properties.get(property_name, JS_UNDEFINED),
            target if receiver is None else receiver,
        )
    if isinstance(target, dict):
        return _resolve_descriptor(
            _lookup_dict_property(target, property_name),
            target if receiver is None else receiver,
        )
    if isinstance(target, list):
        if property_name == "length":
            return float(len(target))
        builder = _ARRAY_PROPERTY_BUILDERS.get(property_name)
        if builder is not None:
            return builder(target)
        return JS_UNDEFINED
    if isinstance(target, str):
        return _read_string_property(target, property_name)
    raise TypeError(f"Cannot read property {property_name!r}")


def read_index(target: object, index: object) -> object:
    if isinstance(target, list):
        resolved = to_index(index)
        if 0 <= resolved < len(target):
            return target[resolved]
        return JS_UNDEFINED
    if isinstance(target, str):
        # JS string indexing: s[i] returns the character or undefined.
        if isinstance(index, (int, float)) and not (isinstance(index, float) and math.isnan(index)):
            i = int(index)
            if 0 <= i < len(target):
                return target[i]
            return JS_UNDEFINED
        # Property-style access (s["length"], s["slice"]) flows through read_property.
        return _read_string_property(target, js_to_string(index))
    if isinstance(target, HostObject):
        return target.get(js_to_string(index))
    if isinstance(target, dict):
        key = js_to_string(index)
        return _resolve_descriptor(_lookup_dict_property(target, key), target)
    raise TypeError("Cannot index value")


def _find_descriptor_holder(target: dict[str, object], property_name: str) -> dict[str, object] | None:
    if property_name in target:
        return target
    prototype = target.get("__proto__")
    if isinstance(prototype, dict):
        return _find_descriptor_holder(prototype, property_name)
    return None


def write_property(target: object, property_name: str, value: object, *, receiver: object | None = None) -> object:
    if isinstance(target, HostCallable):
        target.properties[property_name] = value
        return value
    if hasattr(target, "call") and not hasattr(target, "static_properties"):
        if property_name == "prototype" and hasattr(target, "prototype"):
            target.prototype = value
            return value
        properties = getattr(target, "properties", None)
        if isinstance(properties, dict):
            properties[property_name] = value
            return value
        setattr(target, property_name, value)
        return value
    if isinstance(target, HostObject):
        return target.set(property_name, value)
    if hasattr(target, "static_properties") and hasattr(target, "prototype"):
        if property_name == "prototype":
            raise TypeError("Cannot assign to class prototype")
        existing = target.static_properties.get(property_name)
        if isinstance(existing, dict) and ("get" in existing or "set" in existing):
            setter = existing.get("set")
            if setter is None:
                raise TypeError(f"Cannot set property {property_name!r}")
            setter.call((value,), this_value=target if receiver is None else receiver)
            return value
        target.static_properties[property_name] = value
        return value
    if isinstance(target, dict):
        holder = _find_descriptor_holder(target, property_name)
        descriptor = holder.get(property_name) if holder is not None else None
        if isinstance(descriptor, dict) and ("get" in descriptor or "set" in descriptor):
            setter = descriptor.get("set")
            if setter is None:
                raise TypeError(f"Cannot set property {property_name!r}")
            setter.call((value,), this_value=target if receiver is None else receiver)
            return value
        target[property_name] = value
        return value
    raise TypeError(f"Cannot write property {property_name!r}")


def write_index(target: object, index: object, value: object) -> object:
    if isinstance(target, list):
        target[to_index(index)] = value
        return value
    if isinstance(target, HostObject):
        return target.set(js_to_string(index), value)
    if isinstance(target, dict):
        target[js_to_string(index)] = value
        return value
    raise TypeError("Cannot index-assign value")


def is_callable(value: object) -> bool:
    return hasattr(value, "call")


def to_index(value: object) -> int:
    if isinstance(value, float):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(float(value))
    raise TypeError("Invalid index")


def _array_push(target: object, values: tuple[object, ...]) -> float:
    if not isinstance(target, list):
        raise TypeError("Array.push receiver must be an array")
    target.extend(values)
    return float(len(target))


def _arr_pop(arr: list[object], _args: tuple[object, ...]) -> object:
    if not arr:
        return JS_UNDEFINED
    return arr.pop()


def _arr_shift(arr: list[object], _args: tuple[object, ...]) -> object:
    if not arr:
        return JS_UNDEFINED
    return arr.pop(0)


def _arr_unshift(arr: list[object], args: tuple[object, ...]) -> float:
    for i, value in enumerate(args):
        arr.insert(i, value)
    return float(len(arr))


def _arr_index_of(arr: list[object], args: tuple[object, ...]) -> float:
    if not args:
        return -1.0
    needle = args[0]
    start = 0
    if len(args) > 1:
        raw = js_to_number(args[1])
        if not math.isnan(raw):
            start = int(raw)
            if start < 0:
                start = max(0, len(arr) + start)
    for i in range(start, len(arr)):
        if _strict_equal_for_array(arr[i], needle):
            return float(i)
    return -1.0


def _arr_last_index_of(arr: list[object], args: tuple[object, ...]) -> float:
    if not args:
        return -1.0
    needle = args[0]
    for i in range(len(arr) - 1, -1, -1):
        if _strict_equal_for_array(arr[i], needle):
            return float(i)
    return -1.0


def _arr_includes(arr: list[object], args: tuple[object, ...]) -> bool:
    if not args:
        return False
    needle = args[0]
    for value in arr:
        if _strict_equal_for_array(value, needle):
            return True
    return False


def _arr_slice(arr: list[object], args: tuple[object, ...]) -> list[object]:
    start = int(js_to_number(args[0])) if args and args[0] is not JS_UNDEFINED else 0
    if len(args) > 1 and args[1] is not JS_UNDEFINED:
        end = int(js_to_number(args[1]))
        return list(arr[start:end])
    return list(arr[start:])


def _arr_concat(arr: list[object], args: tuple[object, ...]) -> list[object]:
    result = list(arr)
    for arg in args:
        if isinstance(arg, list):
            result.extend(arg)
        else:
            result.append(arg)
    return result


def _arr_join(arr: list[object], args: tuple[object, ...]) -> str:
    sep = js_to_string(args[0]) if args and args[0] is not JS_UNDEFINED else ","
    parts = []
    for value in arr:
        if value is None or value is JS_UNDEFINED:
            parts.append("")
        else:
            parts.append(js_to_string(value))
    return sep.join(parts)


def _arr_reverse(arr: list[object], _args: tuple[object, ...]) -> list[object]:
    arr.reverse()
    return arr


def _arr_for_each(arr: list[object], args: tuple[object, ...]) -> object:
    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.forEach callback must be callable")
    for index, value in enumerate(list(arr)):
        callback.call((value, float(index), arr), this_value=None)
    return JS_UNDEFINED


def _arr_map(arr: list[object], args: tuple[object, ...]) -> list[object]:
    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.map callback must be callable")
    return [callback.call((value, float(index), arr), this_value=None) for index, value in enumerate(list(arr))]


def _arr_filter(arr: list[object], args: tuple[object, ...]) -> list[object]:
    from neuzelaar.engines.js_own.runtime import js_truthy

    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.filter callback must be callable")
    return [
        value
        for index, value in enumerate(list(arr))
        if js_truthy(callback.call((value, float(index), arr), this_value=None))
    ]


def _arr_find(arr: list[object], args: tuple[object, ...]) -> object:
    from neuzelaar.engines.js_own.runtime import js_truthy

    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.find callback must be callable")
    for index, value in enumerate(arr):
        if js_truthy(callback.call((value, float(index), arr), this_value=None)):
            return value
    return JS_UNDEFINED


def _arr_find_index(arr: list[object], args: tuple[object, ...]) -> float:
    from neuzelaar.engines.js_own.runtime import js_truthy

    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.findIndex callback must be callable")
    for index, value in enumerate(arr):
        if js_truthy(callback.call((value, float(index), arr), this_value=None)):
            return float(index)
    return -1.0


def _arr_some(arr: list[object], args: tuple[object, ...]) -> bool:
    from neuzelaar.engines.js_own.runtime import js_truthy

    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.some callback must be callable")
    return any(
        js_truthy(callback.call((value, float(index), arr), this_value=None))
        for index, value in enumerate(arr)
    )


def _arr_every(arr: list[object], args: tuple[object, ...]) -> bool:
    from neuzelaar.engines.js_own.runtime import js_truthy

    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.every callback must be callable")
    return all(
        js_truthy(callback.call((value, float(index), arr), this_value=None))
        for index, value in enumerate(arr)
    )


def _arr_reduce(arr: list[object], args: tuple[object, ...]) -> object:
    callback = args[0] if args else None
    if callback is None or not hasattr(callback, "call"):
        raise TypeError("Array.reduce callback must be callable")
    has_initial = len(args) > 1
    if not arr and not has_initial:
        raise TypeError("Reduce of empty array with no initial value")
    if has_initial:
        accumulator = args[1]
        start_index = 0
    else:
        accumulator = arr[0]
        start_index = 1
    for index in range(start_index, len(arr)):
        accumulator = callback.call(
            (accumulator, arr[index], float(index), arr), this_value=None
        )
    return accumulator


def _arr_sort(arr: list[object], args: tuple[object, ...]) -> list[object]:
    comparator = args[0] if args and args[0] is not JS_UNDEFINED else None
    if comparator is None or not hasattr(comparator, "call"):
        # Default sort: convert to strings, sort lexicographically.
        arr.sort(key=js_to_string)
        return arr
    import functools

    def compare(a: object, b: object) -> int:
        result = comparator.call((a, b), this_value=None)
        n = js_to_number(result)
        if math.isnan(n) or n == 0:
            return 0
        return -1 if n < 0 else 1

    arr.sort(key=functools.cmp_to_key(compare))
    return arr


def _arr_flat(arr: list[object], args: tuple[object, ...]) -> list[object]:
    depth = int(js_to_number(args[0])) if args and args[0] is not JS_UNDEFINED else 1
    return _flatten(arr, depth)


def _flatten(arr: list[object], depth: int) -> list[object]:
    out: list[object] = []
    for value in arr:
        if isinstance(value, list) and depth > 0:
            out.extend(_flatten(value, depth - 1))
        else:
            out.append(value)
    return out


def _strict_equal_for_array(left: object, right: object) -> bool:
    # Lightweight strict-equal that avoids importing the runtime module repeatedly.
    if isinstance(left, float) and math.isnan(left):
        return False
    if isinstance(right, float) and math.isnan(right):
        return False
    if type(left) is not type(right) and not (
        isinstance(left, (int, float)) and isinstance(right, (int, float))
    ):
        # Allow int/float cross-comparison; keep bool distinct.
        if isinstance(left, bool) != isinstance(right, bool):
            return False
        if not (isinstance(left, (int, float)) and isinstance(right, (int, float))):
            return False
    if isinstance(left, (dict, list)) and isinstance(right, (dict, list)):
        return left is right
    return left == right


def _bind_arr_method(arr: list[object], name: str, fn) -> HostCallable:
    return HostCallable(
        f"Array.prototype.{name}",
        lambda args, this_value: fn(arr if this_value is None else this_value, args),
    )


_ARRAY_PROPERTY_BUILDERS: dict[str, "callable[[list], object]"] = {
    "push": lambda a: _bind_arr_method(a, "push", lambda arr, args: _array_push(arr, args)),
    "pop": lambda a: _bind_arr_method(a, "pop", _arr_pop),
    "shift": lambda a: _bind_arr_method(a, "shift", _arr_shift),
    "unshift": lambda a: _bind_arr_method(a, "unshift", _arr_unshift),
    "indexOf": lambda a: _bind_arr_method(a, "indexOf", _arr_index_of),
    "lastIndexOf": lambda a: _bind_arr_method(a, "lastIndexOf", _arr_last_index_of),
    "includes": lambda a: _bind_arr_method(a, "includes", _arr_includes),
    "slice": lambda a: _bind_arr_method(a, "slice", _arr_slice),
    "concat": lambda a: _bind_arr_method(a, "concat", _arr_concat),
    "join": lambda a: _bind_arr_method(a, "join", _arr_join),
    "reverse": lambda a: _bind_arr_method(a, "reverse", _arr_reverse),
    "forEach": lambda a: _bind_arr_method(a, "forEach", _arr_for_each),
    "map": lambda a: _bind_arr_method(a, "map", _arr_map),
    "filter": lambda a: _bind_arr_method(a, "filter", _arr_filter),
    "find": lambda a: _bind_arr_method(a, "find", _arr_find),
    "findIndex": lambda a: _bind_arr_method(a, "findIndex", _arr_find_index),
    "some": lambda a: _bind_arr_method(a, "some", _arr_some),
    "every": lambda a: _bind_arr_method(a, "every", _arr_every),
    "reduce": lambda a: _bind_arr_method(a, "reduce", _arr_reduce),
    "sort": lambda a: _bind_arr_method(a, "sort", _arr_sort),
    "flat": lambda a: _bind_arr_method(a, "flat", _arr_flat),
}


def _read_string_property(s: str, name: str) -> object:
    if name == "length":
        return float(len(s))
    builder = _STRING_PROPERTY_BUILDERS.get(name)
    if builder is None:
        return JS_UNDEFINED
    return builder(s)


def _str_int_arg(args: tuple[object, ...], position: int, default: object = 0) -> int:
    raw = args[position] if position < len(args) else default
    value = js_to_number(raw)
    if math.isnan(value):
        return 0
    return int(value)


def _str_char_at(s: str, args: tuple[object, ...]) -> str:
    i = _str_int_arg(args, 0)
    return s[i] if 0 <= i < len(s) else ""


def _str_char_code_at(s: str, args: tuple[object, ...]) -> float:
    i = _str_int_arg(args, 0)
    if 0 <= i < len(s):
        return float(ord(s[i]))
    return float("nan")


def _str_index_of(s: str, args: tuple[object, ...]) -> float:
    needle = js_to_string(args[0]) if args else "undefined"
    start = _str_int_arg(args, 1)
    return float(s.find(needle, start if start >= 0 else 0))


def _str_last_index_of(s: str, args: tuple[object, ...]) -> float:
    needle = js_to_string(args[0]) if args else "undefined"
    return float(s.rfind(needle))


def _str_includes(s: str, args: tuple[object, ...]) -> bool:
    needle = js_to_string(args[0]) if args else "undefined"
    start = _str_int_arg(args, 1)
    return needle in s[start:] if start > 0 else needle in s


def _str_starts_with(s: str, args: tuple[object, ...]) -> bool:
    needle = js_to_string(args[0]) if args else "undefined"
    start = _str_int_arg(args, 1)
    return s.startswith(needle, max(0, start))


def _str_ends_with(s: str, args: tuple[object, ...]) -> bool:
    needle = js_to_string(args[0]) if args else "undefined"
    if len(args) > 1:
        end = _str_int_arg(args, 1)
        return s.endswith(needle, 0, end)
    return s.endswith(needle)


def _str_slice(s: str, args: tuple[object, ...]) -> str:
    start = _str_int_arg(args, 0) if args else 0
    if len(args) > 1 and args[1] is not JS_UNDEFINED:
        end = _str_int_arg(args, 1)
        return s[start:end]
    return s[start:]


def _str_substring(s: str, args: tuple[object, ...]) -> str:
    start = max(0, _str_int_arg(args, 0)) if args else 0
    if len(args) > 1 and args[1] is not JS_UNDEFINED:
        end = max(0, _str_int_arg(args, 1))
    else:
        end = len(s)
    if start > end:
        start, end = end, start
    return s[start:end]


def _str_to_upper(s: str, _args: tuple[object, ...]) -> str:
    return s.upper()


def _str_to_lower(s: str, _args: tuple[object, ...]) -> str:
    return s.lower()


def _str_trim(s: str, _args: tuple[object, ...]) -> str:
    return s.strip()


def _str_trim_start(s: str, _args: tuple[object, ...]) -> str:
    return s.lstrip()


def _str_trim_end(s: str, _args: tuple[object, ...]) -> str:
    return s.rstrip()


def _str_split(s: str, args: tuple[object, ...]) -> list[object]:
    if not args or args[0] is JS_UNDEFINED:
        return [s]
    sep = js_to_string(args[0])
    if sep == "":
        return list(s)
    if len(args) > 1 and args[1] is not JS_UNDEFINED:
        limit = _str_int_arg(args, 1)
        parts = s.split(sep)
        return parts[:limit] if limit >= 0 else parts
    return s.split(sep)


def _str_replace(s: str, args: tuple[object, ...]) -> str:
    if len(args) < 2:
        return s
    return s.replace(js_to_string(args[0]), js_to_string(args[1]), 1)


def _str_replace_all(s: str, args: tuple[object, ...]) -> str:
    if len(args) < 2:
        return s
    return s.replace(js_to_string(args[0]), js_to_string(args[1]))


def _str_repeat(s: str, args: tuple[object, ...]) -> str:
    n = _str_int_arg(args, 0)
    if n < 0:
        raise ValueError("Invalid count value")
    return s * n


def _str_concat(s: str, args: tuple[object, ...]) -> str:
    return s + "".join(js_to_string(arg) for arg in args)


def _str_pad_start(s: str, args: tuple[object, ...]) -> str:
    width = _str_int_arg(args, 0)
    fill = js_to_string(args[1]) if len(args) > 1 and args[1] is not JS_UNDEFINED else " "
    if width <= len(s) or not fill:
        return s
    pad_len = width - len(s)
    return (fill * (pad_len // len(fill) + 1))[:pad_len] + s


def _str_pad_end(s: str, args: tuple[object, ...]) -> str:
    width = _str_int_arg(args, 0)
    fill = js_to_string(args[1]) if len(args) > 1 and args[1] is not JS_UNDEFINED else " "
    if width <= len(s) or not fill:
        return s
    pad_len = width - len(s)
    return s + (fill * (pad_len // len(fill) + 1))[:pad_len]


def _bind_str_method(s: str, name: str, fn) -> HostCallable:
    return HostCallable(f"String.prototype.{name}", lambda args, _this: fn(s, args))


_STRING_PROPERTY_BUILDERS: dict[str, "callable[[str], object]"] = {
    "charAt": lambda s: _bind_str_method(s, "charAt", _str_char_at),
    "charCodeAt": lambda s: _bind_str_method(s, "charCodeAt", _str_char_code_at),
    "indexOf": lambda s: _bind_str_method(s, "indexOf", _str_index_of),
    "lastIndexOf": lambda s: _bind_str_method(s, "lastIndexOf", _str_last_index_of),
    "includes": lambda s: _bind_str_method(s, "includes", _str_includes),
    "startsWith": lambda s: _bind_str_method(s, "startsWith", _str_starts_with),
    "endsWith": lambda s: _bind_str_method(s, "endsWith", _str_ends_with),
    "slice": lambda s: _bind_str_method(s, "slice", _str_slice),
    "substring": lambda s: _bind_str_method(s, "substring", _str_substring),
    "toUpperCase": lambda s: _bind_str_method(s, "toUpperCase", _str_to_upper),
    "toLowerCase": lambda s: _bind_str_method(s, "toLowerCase", _str_to_lower),
    "trim": lambda s: _bind_str_method(s, "trim", _str_trim),
    "trimStart": lambda s: _bind_str_method(s, "trimStart", _str_trim_start),
    "trimEnd": lambda s: _bind_str_method(s, "trimEnd", _str_trim_end),
    "split": lambda s: _bind_str_method(s, "split", _str_split),
    "replace": lambda s: _bind_str_method(s, "replace", _str_replace),
    "replaceAll": lambda s: _bind_str_method(s, "replaceAll", _str_replace_all),
    "repeat": lambda s: _bind_str_method(s, "repeat", _str_repeat),
    "concat": lambda s: _bind_str_method(s, "concat", _str_concat),
    "padStart": lambda s: _bind_str_method(s, "padStart", _str_pad_start),
    "padEnd": lambda s: _bind_str_method(s, "padEnd", _str_pad_end),
    "toString": lambda s: HostCallable("String.prototype.toString", lambda args, _this: s),
    "valueOf": lambda s: HostCallable("String.prototype.valueOf", lambda args, _this: s),
}
