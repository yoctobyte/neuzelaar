"""urllib-backed fetch client for early milestones."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request as UrlLibRequest
from urllib.request import urlopen

from neuzelaar.core.fetch.resource import Request, Resource


class FetchError(RuntimeError):
    """Raised when a resource cannot be fetched within configured limits."""


class FetchClient:
    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_bytes: int = 2_000_000,
    ) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, request: Request) -> Resource:
        parts = urlsplit(request.url)
        if parts.scheme == "file":
            return self._fetch_file(request)
        if request.method.upper() != "GET":
            raise FetchError(f"Unsupported method in M1 fetch client: {request.method}")
        urllib_request = UrlLibRequest(
            request.url,
            headers=request.headers,
            method=request.method.upper(),
        )
        with urlopen(urllib_request, timeout=self.timeout) as response:
            body = response.read(self.max_bytes + 1)
            if len(body) > self.max_bytes:
                raise FetchError(f"Response exceeded byte cap: {self.max_bytes}")
            headers = dict(response.headers.items())
            content_type = response.headers.get_content_type()
            encoding = response.headers.get_content_charset()
            return Resource.from_body(
                request=request,
                final_url=response.geturl(),
                status=response.status,
                headers=headers,
                body=body,
                encoding=encoding,
                claimed_mime=content_type,
            )

    def _fetch_file(self, request: Request) -> Resource:
        parts = urlsplit(request.url)
        path = Path(unquote(parts.path))
        body = path.read_bytes()
        if len(body) > self.max_bytes:
            raise FetchError(f"File exceeded byte cap: {self.max_bytes}")
        return Resource.from_body(
            request=request,
            final_url=request.url,
            status=200,
            headers={},
            body=body,
            encoding="utf-8",
            claimed_mime=None,
        )
