"""Mediates capability requests between core and shells.

PermissionService is the single entry point for code that needs to check
whether an active-content capability is granted for an origin. It wraps
the PermissionStore and the shell-facing bus so that every capability
check flows through one place:

- if the store already has a matching grant, returns True silently
- otherwise, emits a PermissionRequested event so a shell can prompt
  the user, and returns False

Shells respond via GrantPermission / DenyPermission commands. Handling
those commands writes to the store (grants) or records a negative
decision (denials). Future navigations see the updated store state.

Keeping grants on the command bus — rather than on a callback resolver
field inside the event — preserves the pure-data event contract from
PLAN.md section 3.2 and makes permission flow auditable and
shell-agnostic.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from neuzelaar.core.bus import Bus
from neuzelaar.core.origin import Origin
from neuzelaar.core.policy.capability import Capability, Permission, PermissionScope
from neuzelaar.core.policy.permissions import PermissionStore
from neuzelaar.shell_api.commands import DenyPermission, GrantPermission
from neuzelaar.shell_api.events import PermissionRequested


@dataclass(slots=True)
class PermissionService:
    store: PermissionStore = field(default_factory=PermissionStore)
    bus: Bus | None = None
    _pending: dict[str, tuple[Capability, Origin, str]] = field(default_factory=dict, init=False, repr=False)
    _subscribed_bus_ids: set[int] = field(default_factory=set, init=False, repr=False)

    def request(
        self,
        capability: Capability,
        origin: Origin,
        context_url: str,
    ) -> bool:
        if self.store.is_granted(capability, origin):
            return True
        request_id = str(uuid.uuid4())
        self._pending[request_id] = (capability, origin, context_url)
        if self.bus is not None:
            self.bus.publish(
                PermissionRequested(
                    request_id=request_id,
                    capability=capability,
                    origin=origin,
                    context_url=context_url,
                )
            )
        return False

    def subscribe_to_bus(self, bus: Bus) -> None:
        bus_id = id(bus)
        if bus_id in self._subscribed_bus_ids:
            return
        bus.subscribe(GrantPermission, self.grant)
        bus.subscribe(DenyPermission, self.deny)
        self._subscribed_bus_ids.add(bus_id)

    def request_id_for(
        self,
        capability: Capability,
        origin: Origin,
        context_url: str,
    ) -> str | None:
        for request_id, pending in reversed(tuple(self._pending.items())):
            if pending == (capability, origin, context_url):
                return request_id
        return None

    def grant(self, command: GrantPermission) -> None:
        self.store.grant(
            Permission(
                capability=command.capability,
                scope=command.scope,
                origin=command.origin,
                granted_at=datetime.now(UTC),
            )
        )
        self._clear_pending(command.request_id, command.capability, command.origin)

    def deny(self, command: DenyPermission) -> None:
        # Denials are not yet persisted. When we add a deny-list in a
        # later milestone it will live alongside the store. For now the
        # command is accepted silently so shells can send it without
        # breaking; nothing else needs to happen because the store does
        # not contain a grant.
        self._clear_pending(command.request_id, command.capability, command.origin)

    def _clear_pending(
        self,
        request_id: str | None,
        capability: Capability,
        origin: Origin,
    ) -> None:
        if request_id is not None:
            self._pending.pop(request_id, None)
            return
        for pending_id, pending in tuple(self._pending.items()):
            pending_capability, pending_origin, _context_url = pending
            if pending_capability == capability and pending_origin == origin:
                self._pending.pop(pending_id, None)
