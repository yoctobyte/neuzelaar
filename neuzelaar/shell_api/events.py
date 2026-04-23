"""Events emitted from core to shells.

These dataclasses represent state changes, diagnostic messages, or 
requests for user interaction (like permissions) sent from the core.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PageLoadStarted:
    url: str


@dataclass(frozen=True, slots=True)
class PageLoadProgress:
    done: int
    total: int | None


@dataclass(frozen=True, slots=True)
class PageLoadFinished:
    url: str
    status: int


@dataclass(frozen=True, slots=True)
class PageFailed:
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class TitleChanged:
    title: str


@dataclass(frozen=True, slots=True)
class UrlChanged:
    url: str


@dataclass(frozen=True, slots=True)
class HistoryChanged:
    pass


@dataclass(frozen=True, slots=True)
class RenderInvalidated:
    rect: Any


@dataclass(frozen=True, slots=True)
class PermissionRequested:
    capability: Any
    origin: Any
    resolver: Any


@dataclass(frozen=True, slots=True)
class ResourceBlocked:
    url: str
    reason: str


@dataclass(frozen=True, slots=True)
class ScriptBlocked:
    origin: Any
    reason: str


@dataclass(frozen=True, slots=True)
class StatusMessage:
    text: str


@dataclass(frozen=True, slots=True)
class ConsoleLog:
    level: str
    text: str


@dataclass(frozen=True, slots=True)
class HandlerWarning:
    text: str
