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
class ImageReady:
    """An image referenced by the current page has finished decoding.

    Published from a worker thread by PageLoader.load_async, so shells
    that subscribe must marshal back to their UI thread before touching
    widgets. ``node_id`` matches the key in PageLoadResult.images.
    """

    node_id: Any
    url: str


@dataclass(frozen=True, slots=True)
class DomMutated:
    """A script wrote through to a DOM element's content.

    Published synchronously from the JS host bridge when a property
    like ``textContent`` is assigned on a host object that mirrors a
    real page Element. Shells should debounce-repaint in response.
    """

    node_id: Any
    property: str


@dataclass(frozen=True, slots=True)
class PermissionRequested:
    request_id: str
    capability: Any
    origin: Any
    context_url: str


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
