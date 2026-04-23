import pytest
from datetime import UTC, datetime

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.client import FetchError
from neuzelaar.core.page import PageLoader
from neuzelaar.core.policy.capability import Capability
from neuzelaar.core.policy.capability import Permission, PermissionScope
from neuzelaar.core.policy.permissions import PermissionStore
from neuzelaar.shell_api.events import (
    PageFailed,
    PageLoadFinished,
    PageLoadStarted,
    PermissionRequested,
    ResourceBlocked,
    ScriptBlocked,
)


def test_page_loader_emits_load_and_blocked_resource_events() -> None:
    bus = Bus()
    events: list[object] = []
    for event_type in (PageLoadStarted, PageLoadFinished, ResourceBlocked, ScriptBlocked, PermissionRequested):
        bus.subscribe(event_type, events.append)

    PageLoader(bus=bus).load("tests/fixtures/sites/third_party_script.html")

    assert isinstance(events[0], PageLoadStarted)
    assert any(isinstance(event, PageLoadFinished) for event in events)
    blocked = [event for event in events if isinstance(event, ResourceBlocked)]
    assert len(blocked) == 1
    assert blocked[0].url == "https://cdn.third-party.test/app.js"
    script_blocked = [event for event in events if isinstance(event, ScriptBlocked)]
    assert len(script_blocked) == 1
    assert script_blocked[0].origin == "https://cdn.third-party.test/app.js"
    permission_requests = [event for event in events if isinstance(event, PermissionRequested)]
    assert len(permission_requests) == 1
    assert permission_requests[0].capability == Capability.EXEC_THIRDPARTY_JS
    assert permission_requests[0].origin.host == "cdn.third-party.test"


def test_page_loader_emits_failure_event() -> None:
    bus = Bus()
    failures: list[PageFailed] = []
    bus.subscribe(PageFailed, failures.append)

    with pytest.raises(FetchError):
        PageLoader(bus=bus).load("tests/fixtures/sites/missing.html")

    assert len(failures) == 1
    assert "File not found" in failures[0].reason


def test_page_loader_emits_inline_script_permission_request() -> None:
    bus = Bus()
    permissions: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, permissions.append)

    PageLoader(bus=bus).load("tests/fixtures/sites/inline_script.html")

    assert len(permissions) == 1
    assert permissions[0].capability == Capability.EXEC_INLINE_JS
    assert permissions[0].origin.scheme == "file"


def test_page_loader_emits_same_origin_script_permission_request() -> None:
    bus = Bus()
    permissions: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, permissions.append)

    PageLoader(bus=bus).load("tests/fixtures/sites/same_origin_script.html")

    assert len(permissions) == 1
    assert permissions[0].capability == Capability.EXEC_SAMEORIGIN_JS
    assert permissions[0].origin.scheme == "file"


def test_page_loader_skips_permission_event_when_grant_exists() -> None:
    bus = Bus()
    permissions: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, permissions.append)
    store = PermissionStore()
    store.grant(
        Permission(
            capability=Capability.EXEC_INLINE_JS,
            scope=PermissionScope.SESSION,
            origin=None,
            granted_at=datetime.now(UTC),
        )
    )

    PageLoader(bus=bus, permission_store=store).load("tests/fixtures/sites/inline_script.html")

    assert permissions == []
