"""Runtime value helpers for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.host import HostCallable, HostObject


def read_property(target: object, property_name: str) -> object:
    if isinstance(target, HostObject):
        return target.get(property_name)
    if isinstance(target, dict):
        return target.get(property_name)
    if isinstance(target, list) and property_name == "length":
        return float(len(target))
    raise TypeError(f"Cannot read property {property_name!r}")


def read_index(target: object, index: object) -> object:
    if isinstance(target, list):
        resolved = to_index(index)
        return target[resolved]
    if isinstance(target, HostObject):
        return target.get(str(to_index(index)) if isinstance(index, (int, float)) else str(index))
    if isinstance(target, dict):
        return target.get(str(index))
    raise TypeError("Cannot index value")


def write_property(target: object, property_name: str, value: object) -> object:
    if isinstance(target, HostObject):
        return target.set(property_name, value)
    if isinstance(target, dict):
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
