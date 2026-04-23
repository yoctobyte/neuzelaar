"""Conservative MIME classification for early milestones."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from neuzelaar.core.fetch.resource import Resource


@dataclass(frozen=True, slots=True)
class MimeDecision:
    kind: str
    claimed: str | None
    detected: str | None
    confidence: float
    reason: str


def classify_resource(resource: Resource) -> MimeDecision:
    claimed = _normalize_mime(resource.claimed_mime)
    detected, confidence, reason = _sniff(resource.body)
    extension_kind = _kind_from_extension(resource.final_url)

    if claimed in {"text/html", "application/xhtml+xml"}:
        return MimeDecision("html", claimed, detected, 1.0, "claimed html")
    if claimed and claimed.startswith("text/"):
        return MimeDecision("text", claimed, detected, 0.9, "claimed text")
    if claimed and claimed.startswith("image/"):
        return MimeDecision("image", claimed, detected, 0.9, "claimed image")

    if extension_kind:
        return MimeDecision(extension_kind, claimed, detected, 0.8, "extension hint")
    if detected:
        return MimeDecision(detected, claimed, detected, confidence, reason)
    return MimeDecision("download", claimed, detected, 0.0, "unknown or binary")


def _normalize_mime(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower()


def _kind_from_extension(url: str) -> str | None:
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix in {".txt", ".md", ".css", ".js", ".json", ".xml"}:
        return "text"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return "image"
    return None


def _sniff(body: bytes) -> tuple[str | None, float, str]:
    sample = body[:512].lstrip()
    lower = sample.lower()
    if lower.startswith(b"<!doctype html") or lower.startswith(b"<html") or b"<html" in lower[:128]:
        return "html", 0.8, "sniffed html"
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", 0.95, "sniffed png"
    if sample.startswith(b"\xff\xd8\xff"):
        return "image", 0.95, "sniffed jpeg"
    if sample.startswith((b"GIF87a", b"GIF89a")):
        return "image", 0.95, "sniffed gif"
    try:
        body[:4096].decode("utf-8")
    except UnicodeDecodeError:
        return None, 0.0, "binary-looking content"
    return "text", 0.5, "utf-8 decodable"
