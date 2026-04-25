"""Runtime value helpers for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.host import HostCallable, HostObject


def _lookup_dict_property(target: dict[str, object], property_name: str) -> object:
    if property_name in target:
        return target[property_name]
    prototype = target.get("__proto__")
    if isinstance(prototype, dict):
        return _lookup_dict_property(prototype, property_name)
    return None


def _resolve_descriptor(value: object, receiver: object) -> object:
    if isinstance(value, dict) and ("get" in value or "set" in value):
        getter = value.get("get")
        if getter is None:
            return None
        return getter.call((), this_value=receiver)
    return value


def read_property(target: object, property_name: str, *, receiver: object | None = None) -> object:
    if isinstance(target, HostCallable):
        return target.properties.get(property_name)
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
            target.static_properties.get(property_name),
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
    raise TypeError(f"Cannot read property {property_name!r}")


def read_index(target: object, index: object) -> object:
    if isinstance(target, list):
        resolved = to_index(index)
        return target[resolved]
    if isinstance(target, HostObject):
        return target.get(str(to_index(index)) if isinstance(index, (int, float)) else str(index))
    if isinstance(target, dict):
        key = str(to_index(index)) if isinstance(index, (int, float)) else str(index)
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
        return target.set(str(index), value)
    if isinstance(target, dict):
        target[str(index)] = value
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
