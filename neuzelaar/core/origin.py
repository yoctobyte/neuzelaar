"""URL normalization and origin classification.

Policy code should use this module instead of comparing URL strings directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit


DEFAULT_PORTS = {
    "http": 80,
    "https": 443,
    "ws": 80,
    "wss": 443,
}

OPAQUE_SCHEMES = {"about", "data", "javascript", "mailto"}


@dataclass(frozen=True, slots=True)
class Origin:
    scheme: str
    host: str | None
    port: int | None
    opaque: bool = False


@dataclass(frozen=True, slots=True)
class UrlRecord:
    raw: str
    normalized: str
    origin: Origin
    fragment: str | None = None


def parse_url(raw: str, base: str | None = None) -> UrlRecord:
    """Resolve and normalize a URL or local path."""

    resolved = urljoin(base, raw) if base else raw
    if "://" not in resolved and not _looks_like_special_scheme(resolved):
        resolved = Path(resolved).expanduser().resolve().as_uri()

    without_fragment, fragment = urldefrag(resolved)
    parts = urlsplit(without_fragment)
    scheme = parts.scheme.lower()
    host = parts.hostname.lower() if parts.hostname else None
    port = parts.port or DEFAULT_PORTS.get(scheme)

    if host is not None:
        netloc = host
        if parts.port is not None and parts.port != DEFAULT_PORTS.get(scheme):
            netloc = f"{netloc}:{parts.port}"
    else:
        netloc = parts.netloc

    normalized = urlunsplit(
        (
            scheme,
            netloc,
            parts.path or ("/" if scheme in {"http", "https"} else ""),
            parts.query,
            "",
        )
    )
    origin = Origin(
        scheme=scheme,
        host=host,
        port=port,
        opaque=scheme in OPAQUE_SCHEMES,
    )
    return UrlRecord(
        raw=raw,
        normalized=normalized,
        origin=origin,
        fragment=fragment or None,
    )


def resolve_url(base: str, url: str) -> UrlRecord:
    return parse_url(url, base=base)


def same_origin(left: Origin, right: Origin) -> bool:
    if left.opaque or right.opaque:
        return False
    return left == right


def is_third_party(resource: Origin, context: Origin) -> bool:
    return not same_origin(resource, context)


def _looks_like_special_scheme(value: str) -> bool:
    scheme = value.split(":", 1)[0].lower()
    return ":" in value and scheme in OPAQUE_SCHEMES
