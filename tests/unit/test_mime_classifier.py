from neuzelaar.core.fetch.resource import FetchReason, Request, Resource
from neuzelaar.core.mime.classifier import classify_resource
from neuzelaar.core.origin import parse_url


def make_resource(
    body: bytes,
    *,
    url: str = "https://example.com/resource",
    claimed_mime: str | None = None,
) -> Resource:
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
        claimed_mime=claimed_mime,
    )


def test_claimed_html_is_handled_as_html() -> None:
    resource = make_resource(b"hello", claimed_mime="text/html; charset=utf-8")

    assert classify_resource(resource).kind == "html"


def test_text_plain_html_stays_text() -> None:
    resource = make_resource(b"<!doctype html><html></html>", claimed_mime="text/plain")
    decision = classify_resource(resource)

    assert decision.kind == "text"
    assert decision.detected == "html"


def test_extension_hint_classifies_html_without_header() -> None:
    resource = make_resource(b"<html></html>", url="https://example.com/page.html")

    assert classify_resource(resource).kind == "html"


def test_binary_unknown_becomes_download() -> None:
    resource = make_resource(b"\x00\xff\x00\xff", url="https://example.com/blob.bin")

    assert classify_resource(resource).kind == "download"
