import pytest

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.client import FetchError
from neuzelaar.core.page import PageLoader
from neuzelaar.shell_api.events import PageFailed, PageLoadFinished, PageLoadStarted, ResourceBlocked


def test_page_loader_emits_load_and_blocked_resource_events() -> None:
    bus = Bus()
    events: list[object] = []
    for event_type in (PageLoadStarted, PageLoadFinished, ResourceBlocked):
        bus.subscribe(event_type, events.append)

    PageLoader(bus=bus).load("tests/fixtures/sites/third_party_script.html")

    assert isinstance(events[0], PageLoadStarted)
    assert any(isinstance(event, PageLoadFinished) for event in events)
    blocked = [event for event in events if isinstance(event, ResourceBlocked)]
    assert len(blocked) == 1
    assert blocked[0].url == "https://cdn.third-party.test/app.js"


def test_page_loader_emits_failure_event() -> None:
    bus = Bus()
    failures: list[PageFailed] = []
    bus.subscribe(PageFailed, failures.append)

    with pytest.raises(FetchError):
        PageLoader(bus=bus).load("tests/fixtures/sites/missing.html")

    assert len(failures) == 1
    assert "File not found" in failures[0].reason
