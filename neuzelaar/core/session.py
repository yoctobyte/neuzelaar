"""In-memory browsing session and single-tab history."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass, field

from neuzelaar.core.bus import Bus
from neuzelaar.core.diagnostics import LoadDiagnostics
from neuzelaar.core.fetch.cache import ResponseCache
from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason
from neuzelaar.core.fetch.cookies import SessionCookieJar
from neuzelaar.core.page import PageLoader, PageLoadResult
from neuzelaar.core.policy.capability import PermissionScope
from neuzelaar.core.policy.permission_service import PermissionService
from neuzelaar.core.policy.profile import PolicyProfile
from neuzelaar.engines.js.interface import JavaScriptEngine
from neuzelaar.shell_api.commands import DenyPermission, GrantPermission


@dataclass(slots=True)
class HistoryEntry:
    url: str
    result: PageLoadResult


@dataclass(slots=True)
class BrowserSession:
    cookie_jar: SessionCookieJar = field(default_factory=SessionCookieJar)
    bus: Bus = field(default_factory=Bus)
    permission_service: PermissionService | None = None
    js_engine: JavaScriptEngine | None = None
    loader: PageLoader | None = None
    response_cache: ResponseCache | None = None
    diagnostics: LoadDiagnostics = field(default_factory=LoadDiagnostics)
    history: list[HistoryEntry] = field(default_factory=list)
    current_index: int = -1

    def __post_init__(self) -> None:
        if self.permission_service is None:
            self.permission_service = PermissionService(bus=self.bus)
        self.permission_service.subscribe_to_bus(self.bus)
        if self.loader is None:
            if self.response_cache is None:
                self.response_cache = ResponseCache()
            self.loader = PageLoader(
                fetch_client=FetchClient(cache=self.response_cache),
                cookie_jar=self.cookie_jar,
                bus=self.bus,
                permission_service=self.permission_service,
                js_engine=self.js_engine,
                diagnostics=self.diagnostics,
            )
        else:
            self.diagnostics = self.loader.diagnostics
            if self.response_cache is None:
                self.response_cache = self.loader.fetch_client.cache

    @property
    def current(self) -> PageLoadResult | None:
        if self.current_index < 0:
            return None
        return self.history[self.current_index].result

    def open_url(self, url: str) -> PageLoadResult:
        result = self.loader.load(url)
        self._record_history(result)
        return result

    def open_url_async(self, url: str) -> tuple[PageLoadResult, Future[None]]:
        """Streaming variant of open_url for shells that can repaint mid-load.

        Returns once the document and styles are ready; image fetches
        continue in the background and publish ImageReady events on
        completion. Headless callers should keep using ``open_url``.
        """
        result, future = self.loader.load_async(url)
        self._record_history(result)
        return result, future

    def _record_history(self, result: PageLoadResult) -> None:
        del self.history[self.current_index + 1 :]
        self.history.append(HistoryEntry(url=result.resource.final_url, result=result))
        self.current_index = len(self.history) - 1

    def reload(self) -> PageLoadResult:
        current = self.current
        if current is None:
            raise SessionError("No current page")
        return self.open_url(current.resource.final_url)

    def reload_async(self) -> tuple[PageLoadResult, Future[None]]:
        current = self.current
        if current is None:
            raise SessionError("No current page")
        return self.open_url_async(current.resource.final_url)

    def follow_link(self, index: int) -> PageLoadResult:
        current = self.current
        if current is None:
            raise SessionError("No current page")
        try:
            link = current.links[index - 1]
        except IndexError as exc:
            raise SessionError(f"No link at index {index}") from exc
        return self.open_url(link.resolved_url)

    def submit_form(self, index: int, values: dict[str, str] | None = None) -> PageLoadResult:
        current = self.current
        if current is None:
            raise SessionError("No current page")
        try:
            form = current.forms[index - 1]
        except IndexError as exc:
            raise SessionError(f"No form at index {index}") from exc
        data = {control.name: control.value for control in form.controls}
        if values:
            data.update(values)
        return self.loader.load(
            form.resolved_action,
            method=form.method.upper(),
            form_data=data,
            reason=FetchReason.FORM_SUBMIT,
        )

    def back(self) -> PageLoadResult:
        if self.current_index <= 0:
            raise SessionError("No previous history entry")
        self.current_index -= 1
        return self.history[self.current_index].result

    def forward(self) -> PageLoadResult:
        if self.current_index >= len(self.history) - 1:
            raise SessionError("No next history entry")
        self.current_index += 1
        return self.history[self.current_index].result

    @property
    def policy_profile(self) -> PolicyProfile:
        return self.loader.policy_engine.profile

    def set_policy_profile(self, profile: PolicyProfile) -> None:
        self.loader.policy_engine.profile = profile

    def grant_script_permission(self, index: int, scope: PermissionScope) -> None:
        node_id, script = self._script_at(index)
        capability = self._script_capability(node_id)
        request_id = self.permission_service.request_id_for(
            capability,
            script.origin,
            self.current.resource.final_url,
        )
        self.bus.publish(
            GrantPermission(
                capability=capability,
                origin=script.origin,
                scope=scope,
                request_id=request_id,
            )
        )

    def deny_script_permission(self, index: int) -> None:
        node_id, script = self._script_at(index)
        capability = self._script_capability(node_id)
        request_id = self.permission_service.request_id_for(
            capability,
            script.origin,
            self.current.resource.final_url,
        )
        self.bus.publish(
            DenyPermission(
                capability=capability,
                origin=script.origin,
                request_id=request_id,
            )
        )

    def _script_at(self, index: int):
        current = self.current
        if current is None:
            raise SessionError("No current page")
        scripts = tuple(current.scripts.items())
        try:
            return scripts[index - 1]
        except IndexError as exc:
            raise SessionError(f"No script request at index {index}") from exc

    def _script_capability(self, node_id) -> object:
        current = self.current
        if current is None:
            raise SessionError("No current page")
        script = current.scripts[node_id]
        if not script.result.requested_capabilities:
            raise SessionError("Script request has no capability")
        return script.result.requested_capabilities[0]


class SessionError(RuntimeError):
    """Raised when a session command cannot be completed."""
