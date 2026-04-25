"""Builtin host objects for the standalone JS interpreter."""

from __future__ import annotations

from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.promises import create_promise_builtins
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
        HostCallable(
            "Number",
            lambda args, _this: js_to_number(args[0] if args else 0.0),
            properties={
                "POSITIVE_INFINITY": float("inf"),
                "NEGATIVE_INFINITY": float("-inf"),
            },
        ),
        kind="const",
    )
    environment.declare(
        "String",
        HostCallable("String", lambda args, _this: js_to_string(args[0] if args else "")),
        kind="const",
    )
    object_create = HostCallable(
        "Object.create",
        lambda args, _this: {"__proto__": args[0]} if args and isinstance(args[0], dict) else {},
    )
    environment.declare(
        "Object",
        HostObject(
            properties={
                "create": object_create,
            }
        ),
        kind="const",
    )
    environment.declare(
        "Error",
        HostCallable(
            "Error",
            lambda args, _this: js_error_object(args[0] if args else ""),
            properties={"prototype": {}},
        ),
        kind="const",
    )
    def _eval(args: tuple[object, ...], _this: object | None) -> object:
        from neuzelaar.engines.js_own.interpreter import evaluate_program_with_config

        source = js_to_string(args[0] if args else "")
        return evaluate_program_with_config(source, environment=environment)

    environment.declare("eval", HostCallable("eval", _eval), kind="const")
    environment.declare("undefined", None, kind="const")
    environment.declare("Infinity", float("inf"), kind="const")
    promise_constructor, queue_microtask = create_promise_builtins()
    environment.declare("Promise", promise_constructor, kind="const")
    environment.declare("queueMicrotask", queue_microtask, kind="const")
