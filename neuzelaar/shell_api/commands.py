"""Commands sent from shells into core.

These dataclasses represent user actions or shell-initiated requests 
that the core must process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OpenUrl:
    url: str


@dataclass(frozen=True, slots=True)
class Reload:
    pass


@dataclass(frozen=True, slots=True)
class StopLoad:
    pass


@dataclass(frozen=True, slots=True)
class Back:
    pass


@dataclass(frozen=True, slots=True)
class Forward:
    pass


@dataclass(frozen=True, slots=True)
class ClickAt:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class HoverAt:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ScrollBy:
    dx: int
    dy: int


@dataclass(frozen=True, slots=True)
class KeyPress:
    key: str
    mods: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class TextInput:
    text: str


@dataclass(frozen=True, slots=True)
class SubmitForm:
    form_id: str


@dataclass(frozen=True, slots=True)
class AllowCapabilityOnce:
    capability: Any
    origin: Any


@dataclass(frozen=True, slots=True)
class GrantPermission:
    capability: Any
    origin: Any
    scope: Any
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class DenyPermission:
    capability: Any
    origin: Any
    remember: bool = False
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class SetSitePolicy:
    origin: Any
    profile: Any


@dataclass(frozen=True, slots=True)
class CloseTab:
    id: str


@dataclass(frozen=True, slots=True)
class DuplicateTab:
    id: str


@dataclass(frozen=True, slots=True)
class OpenInNewTab:
    url: str
