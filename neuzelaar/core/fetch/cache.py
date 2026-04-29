"""In-memory HTTP response cache with conditional revalidation support.

Stores GET responses keyed by their original request URL, alongside the
revalidation headers (`ETag`, `Last-Modified`) needed to ask the origin
"is this still fresh?" on the next fetch. The FetchClient consults the
cache before each GET and replays the cached body on a 304.

This is in-memory only; persistence across runs is a follow-up. The
implementation is thread-safe so the parallel image fetch can share a
single cache across workers.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Mapping

from neuzelaar.core.fetch.resource import Resource


@dataclass(frozen=True, slots=True)
class CachedEntry:
    resource: Resource
    etag: str | None
    last_modified: str | None


class ResponseCache:
    def __init__(self, *, max_bytes: int = 50_000_000) -> None:
        self.max_bytes = max_bytes
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, CachedEntry] = OrderedDict()
        self._used_bytes = 0

    def get(self, url: str) -> CachedEntry | None:
        with self._lock:
            entry = self._entries.get(url)
            if entry is not None:
                self._entries.move_to_end(url)
            return entry

    def put(self, url: str, resource: Resource) -> None:
        if resource.status != 200:
            return
        size = len(resource.body)
        if size > self.max_bytes:
            return
        cache_control = (_header(resource.headers, "cache-control") or "").lower()
        if "no-store" in cache_control:
            return
        etag = _header(resource.headers, "etag")
        last_modified = _header(resource.headers, "last-modified")
        # Without a revalidation token there is no safe way to ask
        # "still fresh?" on the next fetch, so the cache would either
        # serve stale forever or never be hit. Skip those entries.
        if etag is None and last_modified is None:
            return
        entry = CachedEntry(resource=resource, etag=etag, last_modified=last_modified)
        with self._lock:
            existing = self._entries.pop(url, None)
            if existing is not None:
                self._used_bytes -= len(existing.resource.body)
            self._entries[url] = entry
            self._used_bytes += size
            while self._used_bytes > self.max_bytes and len(self._entries) > 1:
                _, evicted = self._entries.popitem(last=False)
                self._used_bytes -= len(evicted.resource.body)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._used_bytes = 0


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None
