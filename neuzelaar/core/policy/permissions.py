"""Minimal permission store for active-content capability requests."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.core.origin import Origin, same_origin
from neuzelaar.core.policy.capability import Capability, Permission


@dataclass(slots=True)
class PermissionStore:
    permissions: list[Permission] = field(default_factory=list)

    def grant(self, permission: Permission) -> None:
        self.permissions.append(permission)

    def is_granted(self, capability: Capability, origin: Origin) -> bool:
        for permission in reversed(self.permissions):
            if permission.capability != capability:
                continue
            if permission.origin is None:
                return True
            if same_origin(permission.origin, origin):
                return True
        return False
