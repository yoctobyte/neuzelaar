from datetime import UTC, datetime

from neuzelaar.core.bus import Bus
from neuzelaar.core.origin import Origin
from neuzelaar.core.policy.capability import Capability, Permission, PermissionScope
from neuzelaar.core.policy.permission_service import PermissionService
from neuzelaar.core.policy.permissions import PermissionStore
from neuzelaar.shell_api.commands import DenyPermission, GrantPermission
from neuzelaar.shell_api.events import PermissionRequested


def _origin(host: str = "example.com", scheme: str = "https") -> Origin:
    return Origin(scheme=scheme, host=host, port=None, opaque=False)


def test_request_emits_event_and_returns_false_when_not_granted() -> None:
    bus = Bus()
    events: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, events.append)
    service = PermissionService(bus=bus)

    granted = service.request(
        Capability.EXEC_INLINE_JS, _origin(), "https://example.com/page"
    )

    assert granted is False
    assert len(events) == 1
    assert events[0].capability == Capability.EXEC_INLINE_JS
    assert events[0].origin.host == "example.com"
    assert events[0].context_url == "https://example.com/page"
    assert events[0].request_id


def test_request_stays_silent_and_returns_true_when_already_granted() -> None:
    bus = Bus()
    events: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, events.append)
    store = PermissionStore()
    store.grant(
        Permission(
            capability=Capability.EXEC_INLINE_JS,
            scope=PermissionScope.SESSION,
            origin=_origin(),
            granted_at=datetime.now(UTC),
        )
    )
    service = PermissionService(store=store, bus=bus)

    granted = service.request(
        Capability.EXEC_INLINE_JS, _origin(), "https://example.com/page"
    )

    assert granted is True
    assert events == []


def test_grant_records_permission_so_future_request_is_silent() -> None:
    bus = Bus()
    events: list[PermissionRequested] = []
    bus.subscribe(PermissionRequested, events.append)
    service = PermissionService(bus=bus)

    service.grant(
        GrantPermission(
            capability=Capability.EXEC_SAMEORIGIN_JS,
            origin=_origin(),
            scope=PermissionScope.ORIGIN,
        )
    )
    granted = service.request(
        Capability.EXEC_SAMEORIGIN_JS, _origin(), "https://example.com/page"
    )

    assert granted is True
    assert events == []


def test_request_without_bus_still_returns_false_when_not_granted() -> None:
    service = PermissionService(bus=None)

    granted = service.request(
        Capability.EXEC_INLINE_JS, _origin(), "https://example.com/page"
    )

    assert granted is False


def test_deny_is_silently_accepted() -> None:
    # Deny handling is stubbed until a deny-list lands. The command must
    # be safely accepted so shells can already send it.
    service = PermissionService()

    service.deny(
        DenyPermission(
            capability=Capability.EXEC_INLINE_JS,
            origin=_origin(),
            remember=True,
        )
    )
