from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.handlers.download_handler import DownloadInfo
from neuzelaar.core.handlers.image_handler import ImagePlaceholder
from neuzelaar.core.handlers.registry import default_registry
from neuzelaar.core.mime.classifier import MimeDecision
from neuzelaar.core.origin import parse_url


def make_resource(body: bytes = b"data", *, url: str = "https://example.com/file.bin") -> Resource:
    record = parse_url(url)
    request = Request(
        url=record.normalized,
        method="GET",
        headers={},
        body=None,
        reason=FetchReason.TOP_LEVEL,
        initiator=None,
        origin=record.origin,
        context_origin=record.origin,
    )
    return Resource.from_body(
        request=request,
        final_url=record.normalized,
        status=200,
        headers={},
        body=body,
        encoding="utf-8",
        claimed_mime=None,
    )


def decision(kind: str) -> MimeDecision:
    return MimeDecision(kind=kind, claimed=None, detected=None, confidence=1.0, reason="test")


def test_image_handler_returns_placeholder_metadata() -> None:
    result = default_registry().handle(
        make_resource(b"\x89PNG\r\n\x1a\n", url="https://example.com/logo.png"),
        decision("image"),
    )

    assert result.kind == "image"
    assert isinstance(result.value, ImagePlaceholder)
    assert result.value.url == "https://example.com/logo.png"
    assert result.value.size == 8


def test_download_handler_returns_download_info() -> None:
    result = default_registry().handle(make_resource(b"abc"), decision("download"))

    assert result.kind == "download"
    assert isinstance(result.value, DownloadInfo)
    assert result.value.size == 3


def test_unknown_handler_degrades_safely() -> None:
    result = default_registry().handle(make_resource(), decision("weird"))

    assert result.kind == "unknown"
    assert result.value == "no safe handler available"
