from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.interpreter import evaluate_program
from neuzelaar.engines.js_own.values import (
    is_callable,
    read_index,
    read_property,
    write_index,
    write_property,
)


def test_host_object_property_bridge_round_trip() -> None:
    host = HostObject(properties={"x": 1.0})

    assert read_property(host, "x") == 1.0
    assert write_property(host, "x", 4.0) == 4.0
    assert read_property(host, "x") == 4.0


def test_host_object_index_bridge_round_trip() -> None:
    host = HostObject(properties={"0": "a"})

    assert read_index(host, 0.0) == "a"
    assert write_index(host, "1", "b") == "b"
    assert read_index(host, 1.0) == "b"


def test_host_callable_is_callable() -> None:
    fn = HostCallable("id", lambda args, _this: args[0] if args else None)

    assert is_callable(fn) is True
    assert fn.call((3.0,), this_value=None) == 3.0


def test_builtins_install_via_host_bridge() -> None:
    env = Environment()
    install_builtins(env)

    math_value = env.get("Math")
    number_value = env.get("Number")

    assert isinstance(math_value, HostObject)
    assert isinstance(number_value, HostCallable)
    assert read_property(math_value, "abs").call((-2.0,), this_value=None) == 2.0


def test_host_object_can_be_exposed_to_program() -> None:
    env = Environment()
    install_builtins(env)
    env.declare(
        "host",
        HostObject(
            properties={
                "value": 7.0,
                "bump": HostCallable("host.bump", lambda _args, this: read_property(this, "value") + 1.0),
            }
        ),
        kind="const",
    )

    assert evaluate_program("host.value;", env) == 7.0
    assert evaluate_program("host.bump();", env) == 8.0
