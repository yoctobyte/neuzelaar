from dataclasses import dataclass

from neuzelaar.core.bus import Bus


@dataclass(frozen=True)
class BaseEvent:
    value: str


@dataclass(frozen=True)
class ChildEvent(BaseEvent):
    pass


def test_bus_delivers_to_exact_message_type() -> None:
    bus = Bus()
    received: list[str] = []

    bus.subscribe(BaseEvent, lambda event: received.append(event.value))
    bus.publish(BaseEvent("ready"))

    assert received == ["ready"]


def test_bus_delivers_to_base_class_subscribers() -> None:
    bus = Bus()
    received: list[str] = []

    bus.subscribe(BaseEvent, lambda event: received.append(event.value))
    bus.publish(ChildEvent("child"))

    assert received == ["child"]
