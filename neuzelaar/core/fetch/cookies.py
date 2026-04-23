"""Session-only cookie jar for early browser workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from http.cookies import SimpleCookie

from neuzelaar.core.origin import Origin, parse_url
from neuzelaar.core.fetch.resource import Resource


@dataclass(slots=True)
class StoredCookie:
    name: str
    value: str
    origin: Origin
    path: str = "/"


@dataclass(slots=True)
class SessionCookieJar:
    _cookies: dict[tuple[Origin, str, str], StoredCookie] = field(default_factory=dict)

    def add_cookie_header(self, url: str, headers: dict[str, str]) -> None:
        record = parse_url(url)
        pairs = [
            f"{cookie.name}={cookie.value}"
            for cookie in self._cookies.values()
            if cookie.origin == record.origin
        ]
        if pairs:
            headers["Cookie"] = "; ".join(sorted(pairs))

    def store_from_resource(self, resource: Resource) -> None:
        header = _header_value(resource.headers, "set-cookie")
        if not header:
            return
        record = parse_url(resource.final_url)
        parsed = SimpleCookie()
        parsed.load(header)
        for morsel in parsed.values():
            path = morsel["path"] or "/"
            cookie = StoredCookie(
                name=morsel.key,
                value=morsel.value,
                origin=record.origin,
                path=path,
            )
            self._cookies[(record.origin, path, morsel.key)] = cookie

    def get(self, url: str, name: str) -> str | None:
        record = parse_url(url)
        for (origin, _path, cookie_name), cookie in self._cookies.items():
            if origin == record.origin and cookie_name == name:
                return cookie.value
        return None

    def clear(self) -> None:
        self._cookies.clear()


def _header_value(headers, name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None

