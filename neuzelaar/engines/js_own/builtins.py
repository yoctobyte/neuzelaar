"""Builtin host objects for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.runtime import js_error_object, js_to_number, js_to_string


def install_builtins(environment) -> None:
    environment.declare(
        "Math",
        HostObject(
            properties={
                "abs": HostCallable("Math.abs", lambda args, _this: abs(js_to_number(args[0] if args else 0.0))),
                "max": HostCallable(
                    "Math.max",
                    lambda args, _this: max((js_to_number(arg) for arg in args), default=float("-inf")),
                ),
            }
        ),
        kind="const",
    )
    environment.declare(
        "Number",
        HostCallable("Number", lambda args, _this: js_to_number(args[0] if args else 0.0)),
        kind="const",
    )
    environment.declare(
        "String",
        HostCallable("String", lambda args, _this: js_to_string(args[0] if args else "")),
        kind="const",
    )
    environment.declare(
        "Error",
        HostCallable("Error", lambda args, _this: js_error_object(args[0] if args else "")),
        kind="const",
    )
