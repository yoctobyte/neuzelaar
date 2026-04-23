"""urllib-backed fetch client for early milestones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request as UrlLibRequest
from urllib.request import urlopen

from neuzelaar.core.fetch.resource import Request, Resource


class FetchError(RuntimeError):
    """Raised when a resource cannot be fetched within configured limits."""

    def __init__(self, kind: str, message: str, *, url: str | None = None) -> None:
        super().__init__(message)
        self.kind = kind
        self.url = url


@dataclass(frozen=True, slots=True)
class FetchLimits:
    timeout: float = 10.0
    max_bytes: int = 2_000_000
    max_redirects: int = 5


class FetchClient:
    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_bytes: int = 2_000_000,
        max_redirects: int = 5,
    ) -> None:
        self.limits = FetchLimits(
            timeout=timeout,
            max_bytes=max_bytes,
            max_redirects=max_redirects,
        )

    @property
    def timeout(self) -> float:
        return self.limits.timeout

    @property
    def max_bytes(self) -> int:
        return self.limits.max_bytes

    def fetch(self, request: Request) -> Resource:
        parts = urlsplit(request.url)
        if parts.scheme == "file":
            return self._fetch_file(request)
        if request.method.upper() != "GET":
            raise FetchError(
                "unsupported_method",
                f"Unsupported method in M1 fetch client: {request.method}",
                url=request.url,
            )
        urllib_request = UrlLibRequest(
            request.url,
            headers=request.headers,
            method=request.method.upper(),
        )
        try:
            with urlopen(urllib_request, timeout=self.timeout) as response:
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise FetchError(
                        "byte_cap",
                        f"Response exceeded byte cap: {self.max_bytes}",
                        url=request.url,
                    )
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
        except FetchError:
            raise
        except HTTPError as exc:
            raise FetchError("http_error", str(exc), url=request.url) from exc
        except URLError as exc:
            raise FetchError("url_error", str(exc), url=request.url) from exc
        except OSError as exc:
            raise FetchError("network_error", str(exc), url=request.url) from exc

    def redirect_cap(self) -> int:
        """Return the configured redirect cap until custom redirect handling lands."""

        return self.limits.max_redirects

    def _fetch_file(self, request: Request) -> Resource:
        parts = urlsplit(request.url)
        path = Path(unquote(parts.path))
        try:
            body = path.read_bytes()
        except FileNotFoundError as exc:
            raise FetchError("not_found", f"File not found: {path}", url=request.url) from exc
        except OSError as exc:
            raise FetchError("file_error", str(exc), url=request.url) from exc
        if len(body) > self.max_bytes:
            raise FetchError(
                "byte_cap",
                f"File exceeded byte cap: {self.max_bytes}",
                url=request.url,
            )
        return Resource.from_body(
            request=request,
            final_url=request.url,
            status=200,
            headers={},
            body=body,
            encoding="utf-8",
            claimed_mime=None,
        )
