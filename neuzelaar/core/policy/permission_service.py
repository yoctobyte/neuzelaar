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

    def request(
        self,
        capability: Capability,
        origin: Origin,
        context_url: str,
    ) -> bool:
        if self.store.is_granted(capability, origin):
            return True
        if self.bus is not None:
            self.bus.publish(
                PermissionRequested(
                    request_id=str(uuid.uuid4()),
                    capability=capability,
                    origin=origin,
                    context_url=context_url,
                )
            )
        return False

    def grant(self, command: GrantPermission) -> None:
        self.store.grant(
            Permission(
                capability=command.capability,
                scope=command.scope,
                origin=command.origin,
                granted_at=datetime.now(UTC),
            )
        )

    def deny(self, command: DenyPermission) -> None:
        # Denials are not yet persisted. When we add a deny-list in a
        # later milestone it will live alongside the store. For now the
        # command is accepted silently so shells can send it without
        # breaking; nothing else needs to happen because the store does
        # not contain a grant.
        _ = command
