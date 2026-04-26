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
        if property_name == "push":
            return HostCallable(
                "Array.push",
                lambda args, this_value: _array_push(target if this_value is None else this_value, args),
            )
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
