"""In-memory browsing session and single-tab history."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.core.fetch.resource import FetchReason
from neuzelaar.core.fetch.cookies import SessionCookieJar
from neuzelaar.core.page import PageLoader, PageLoadResult


@dataclass(slots=True)
class HistoryEntry:
    url: str
    result: PageLoadResult


@dataclass(slots=True)
class BrowserSession:
    cookie_jar: SessionCookieJar = field(default_factory=SessionCookieJar)
    loader: PageLoader | None = None
    history: list[HistoryEntry] = field(default_factory=list)
    current_index: int = -1

    def __post_init__(self) -> None:
        if self.loader is None:
            self.loader = PageLoader(cookie_jar=self.cookie_jar)

    @property
    def current(self) -> PageLoadResult | None:
        if self.current_index < 0:
            return None
        return self.history[self.current_index].result

    def open_url(self, url: str) -> PageLoadResult:
        result = self.loader.load(url)
        del self.history[self.current_index + 1 :]
        self.history.append(HistoryEntry(url=result.resource.final_url, result=result))
        self.current_index = len(self.history) - 1
        return result

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


class SessionError(RuntimeError):
    """Raised when a session command cannot be completed."""
