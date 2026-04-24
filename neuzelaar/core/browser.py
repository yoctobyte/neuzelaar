"""Multi-tab browser state built on top of per-tab sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from neuzelaar.core.bus import Bus
from neuzelaar.core.fetch.cookies import PersistentCookieJar, SessionCookieJar
from neuzelaar.core.page import PageLoadResult
from neuzelaar.core.policy.capability import PermissionScope
from neuzelaar.core.policy.permission_service import PermissionService
from neuzelaar.core.session import BrowserSession, SessionError
from neuzelaar.engines.js.interface import JavaScriptEngine


@dataclass(slots=True)
class BrowserTab:
    id: int
    session: BrowserSession

    @property
    def current(self) -> PageLoadResult | None:
        return self.session.current


@dataclass(slots=True)
class BrowserState:
    cookie_jar: SessionCookieJar = field(default_factory=SessionCookieJar)
    bus: Bus = field(default_factory=Bus)
    permission_service: PermissionService | None = None
    js_engine_factory: Callable[[], JavaScriptEngine] | None = None
    tabs: dict[int, BrowserTab] = field(default_factory=dict)
    active_tab_id: int | None = None
    _next_tab_id: int = 1

    def __post_init__(self) -> None:
        if self.permission_service is None:
            self.permission_service = PermissionService(bus=self.bus)
        self.permission_service.subscribe_to_bus(self.bus)

    @classmethod
    def with_persistent_cookies(cls, path: str | Path) -> "BrowserState":
        return cls(cookie_jar=PersistentCookieJar(path=Path(path)))

    @property
    def active_tab(self) -> BrowserTab:
        if self.active_tab_id is None or self.active_tab_id not in self.tabs:
            raise BrowserStateError("No active tab")
        return self.tabs[self.active_tab_id]

    def new_tab(self, url: str | None = None, *, activate: bool = True) -> BrowserTab:
        tab = BrowserTab(
            id=self._next_tab_id,
            session=BrowserSession(
                cookie_jar=self.cookie_jar,
                bus=self.bus,
                permission_service=self.permission_service,
                js_engine=self.js_engine_factory() if self.js_engine_factory is not None else None,
            ),
        )
        self.tabs[tab.id] = tab
        self._next_tab_id += 1
        if activate or self.active_tab_id is None:
            self.active_tab_id = tab.id
        if url is not None:
            tab.session.open_url(url)
        return tab

    def switch_tab(self, tab_id: int) -> BrowserTab:
        if tab_id not in self.tabs:
            raise BrowserStateError(f"No tab with id {tab_id}")
        self.active_tab_id = tab_id
        return self.tabs[tab_id]

    def close_tab(self, tab_id: int) -> None:
        if tab_id not in self.tabs:
            raise BrowserStateError(f"No tab with id {tab_id}")
        del self.tabs[tab_id]
        if not self.tabs:
            self.active_tab_id = None
            return
        if self.active_tab_id == tab_id:
            self.active_tab_id = sorted(self.tabs)[0]

    def list_tabs(self) -> tuple[BrowserTab, ...]:
        return tuple(self.tabs[tab_id] for tab_id in sorted(self.tabs))

    def open_url(self, url: str) -> PageLoadResult:
        return self.active_tab.session.open_url(url)

    def follow_link(self, index: int) -> PageLoadResult:
        return self.active_tab.session.follow_link(index)

    def submit_form(self, index: int, values: dict[str, str] | None = None) -> PageLoadResult:
        return self.active_tab.session.submit_form(index, values)

    def back(self) -> PageLoadResult:
        return self.active_tab.session.back()

    def forward(self) -> PageLoadResult:
        return self.active_tab.session.forward()

    def reload(self) -> PageLoadResult:
        return self.active_tab.session.reload()

    def grant_script_permission(self, index: int, scope: PermissionScope) -> None:
        self.active_tab.session.grant_script_permission(index, scope)

    def deny_script_permission(self, index: int) -> None:
        self.active_tab.session.deny_script_permission(index)


class BrowserStateError(RuntimeError):
    """Raised when browser-level tab state is invalid."""
