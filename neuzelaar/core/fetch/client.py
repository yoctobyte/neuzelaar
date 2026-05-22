"""urllib-backed fetch client for early milestones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request as UrlLibRequest
from urllib.request import build_opener, HTTPRedirectHandler, urlopen

from neuzelaar.core.fetch.cache import CachedEntry, ResponseCache
from neuzelaar.core.fetch.resource import CacheMeta, Request, Resource


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
        cache: ResponseCache | None = None,
    ) -> None:
        self.limits = FetchLimits(
            timeout=timeout,
            max_bytes=max_bytes,
            max_redirects=max_redirects,
        )
        self.cache = cache

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
        method = request.method.upper()
        if method not in {"GET", "POST"}:
            raise FetchError(
                "unsupported_method",
                f"Unsupported method in M1 fetch client: {request.method}",
                url=request.url,
            )
        # Conditional revalidation: if we have a cached entry with a
        # validator, attach If-None-Match / If-Modified-Since so the
        # server can answer 304 instead of resending the body.
        cached: CachedEntry | None = None
        request_headers = dict(request.headers)
        if self.cache is not None and method == "GET":
            cached = self.cache.get(request.url)
            if cached is not None:
                if cached.etag and "If-None-Match" not in request_headers:
                    request_headers["If-None-Match"] = cached.etag
                if cached.last_modified and "If-Modified-Since" not in request_headers:
                    request_headers["If-Modified-Since"] = cached.last_modified
        # Set a standard browser User-Agent if not already provided to avoid
        # typical urllib blocking (HTTP Error 403: Forbidden)
        has_user_agent = any(k.lower() == "user-agent" for k in request_headers)
        if not has_user_agent:
            request_headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        urllib_request = UrlLibRequest(
            request.url,
            data=request.body if method == "POST" else None,
            headers=request_headers,
            method=method,
        )
        try:
            opener = _build_opener(self.limits.max_redirects)
            with opener.open(urllib_request, timeout=self.timeout) as response:
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
                resource = Resource.from_body(
                    request=request,
                    final_url=response.geturl(),
                    status=response.status,
                    headers=headers,
                    body=body,
                    encoding=encoding,
                    claimed_mime=content_type,
                )
                if self.cache is not None and method == "GET":
                    self.cache.put(request.url, resource)
                return resource
        except FetchError:
            raise
        except HTTPError as exc:
            if exc.code == 304 and cached is not None:
                return _replay_from_cache(request, cached)
            raise FetchError("http_error", str(exc), url=request.url) from exc
        except URLError as exc:
            raise FetchError("url_error", str(exc), url=request.url) from exc
        except OSError as exc:
            raise FetchError("network_error", str(exc), url=request.url) from exc


    def redirect_cap(self) -> int:
        """Return the configured redirect cap until custom redirect handling lands."""

        return self.limits.max_redirects

    def _fetch_file(self, request: Request) -> Resource:
        if request.method.upper() != "GET":
            raise FetchError(
                "unsupported_method",
                f"Unsupported method for file URL: {request.method}",
                url=request.url,
            )
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


class _LimitedRedirectHandler(HTTPRedirectHandler):
    """HTTPRedirectHandler that enforces a redirect count limit."""

    def __init__(self, max_redirects: int) -> None:
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise FetchError(
                "redirect_limit",
                f"Too many redirects (limit: {self.max_redirects})",
                url=newurl,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_opener(max_redirects: int):
    return build_opener(_LimitedRedirectHandler(max_redirects))


def _replay_from_cache(request: Request, cached: CachedEntry) -> Resource:
    base = cached.resource
    return Resource(
        id=base.id,
        request=request,
        final_url=base.final_url,
        status=200,
        headers=base.headers,
        body=base.body,
        encoding=base.encoding,
        claimed_mime=base.claimed_mime,
        detected_mime=base.detected_mime,
        mime_confidence=base.mime_confidence,
        trust=base.trust,
        handler=base.handler,
        cache=CacheMeta(from_cache=True),
        content_hash=base.content_hash,
    )
