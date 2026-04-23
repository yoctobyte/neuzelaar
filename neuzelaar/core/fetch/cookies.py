"""Session-only cookie jar for early browser workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path

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

    def snapshot(self) -> list[dict[str, str | int | None]]:
        return [
            {
                "name": cookie.name,
                "value": cookie.value,
                "scheme": cookie.origin.scheme,
                "host": cookie.origin.host,
                "port": cookie.origin.port,
                "opaque": cookie.origin.opaque,
                "path": cookie.path,
            }
            for cookie in sorted(
                self._cookies.values(),
                key=lambda cookie: (cookie.origin.scheme, cookie.origin.host or "", cookie.path, cookie.name),
            )
        ]

    def restore(self, snapshot: list[dict[str, str | int | None]]) -> None:
        self.clear()
        for item in snapshot:
            origin = Origin(
                scheme=str(item["scheme"]),
                host=item["host"] if isinstance(item["host"], str) else None,
                port=item["port"] if isinstance(item["port"], int) else None,
                opaque=bool(item["opaque"]),
            )
            cookie = StoredCookie(
                name=str(item["name"]),
                value=str(item["value"]),
                origin=origin,
                path=str(item["path"]),
            )
            self._cookies[(origin, cookie.path, cookie.name)] = cookie


@dataclass(slots=True)
class PersistentCookieJar(SessionCookieJar):
    path: Path | None = None

    def __post_init__(self) -> None:
        if self.path is not None:
            self.load()

    def store_from_resource(self, resource: Resource) -> None:
        super(PersistentCookieJar, self).store_from_resource(resource)
        if self.path is not None:
            self.save()

    def clear(self) -> None:
        super(PersistentCookieJar, self).clear()
        if self.path is not None:
            self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.snapshot(), indent=2), encoding="utf-8")

    def load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise CookieJarError("Cookie jar file must contain a list")
        self.restore(data)


class CookieJarError(RuntimeError):
    """Raised when persistent cookie jar state is invalid."""


def _header_value(headers, name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None
