from datetime import UTC, datetime

from neuzelaar.core.origin import Origin
from neuzelaar.core.policy.capability import Capability, Permission, PermissionScope
from neuzelaar.core.policy.permissions import PermissionStore


def test_permission_store_matches_same_origin_grants() -> None:
    store = PermissionStore()
    store.grant(
        Permission(
            capability=Capability.EXEC_SAMEORIGIN_JS,
            scope=PermissionScope.ORIGIN,
            origin=Origin("https", "example.com", 443),
            granted_at=datetime.now(UTC),
        )
    )

    assert store.is_granted(Capability.EXEC_SAMEORIGIN_JS, Origin("https", "example.com", 443))
    assert not store.is_granted(Capability.EXEC_SAMEORIGIN_JS, Origin("https", "other.example", 443))


def test_permission_store_supports_global_grants() -> None:
    store = PermissionStore()
    store.grant(
        Permission(
            capability=Capability.EXEC_INLINE_JS,
            scope=PermissionScope.SESSION,
            origin=None,
            granted_at=datetime.now(UTC),
        )
    )

    assert store.is_granted(Capability.EXEC_INLINE_JS, Origin("file", None, None))
