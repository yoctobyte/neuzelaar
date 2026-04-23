"""Capability and permission contracts for active content."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

from neuzelaar.core.origin import Origin


class Capability(Enum):
    EXEC_INLINE_JS = auto()
    EXEC_SAMEORIGIN_JS = auto()
    EXEC_THIRDPARTY_JS = auto()
    NET_FETCH_FROM_SCRIPT = auto()
    TIMERS = auto()
    DOM_MUTATE = auto()
    FORM_SUBMIT = auto()
    SET_COOKIE = auto()
    PERSISTENT_STORAGE = auto()
    USE_CANVAS = auto()
    LOAD_WASM = auto()


class PermissionScope(Enum):
    ONCE = auto()
    TAB = auto()
    SESSION = auto()
    ORIGIN = auto()
    PERSISTENT = auto()


@dataclass(frozen=True, slots=True)
class Permission:
    capability: Capability
    scope: PermissionScope
    origin: Origin | None
    granted_at: datetime
    expires_at: datetime | None = None
