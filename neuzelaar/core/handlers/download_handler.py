"""Download fallback handler."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.fetch.resource import Resource


@dataclass(frozen=True, slots=True)
class DownloadInfo:
    url: str
    size: int
    reason: str


def handle_download(resource: Resource) -> DownloadInfo:
    return DownloadInfo(
        url=resource.final_url,
        size=len(resource.body),
        reason="resource treated as download",
    )
