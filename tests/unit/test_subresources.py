from neuzelaar.core.fetch.resource import FetchReason
from neuzelaar.document.dom import Document, Element, NodeId, append_child
from neuzelaar.document.subresources import PolicyHint, extract_subresources


def test_extracts_policy_visible_subresources() -> None:
    document = Document(id=NodeId("doc"), url="https://example.com/articles/page.html")
    body = Element(id=NodeId("body"), tag="body")
    script = Element(id=NodeId("script"), tag="script", attrs={"src": "https://cdn.test/app.js"})
    image = Element(id=NodeId("image"), tag="img", attrs={"src": "../img/photo.png"})
    style = Element(
        id=NodeId("style"),
        tag="link",
        attrs={"rel": "preload stylesheet", "href": "/site.css"},
    )
    iframe = Element(id=NodeId("frame"), tag="iframe", attrs={"src": "embed.html"})

    append_child(document, body)
    append_child(body, script)
    append_child(body, image)
    append_child(body, style)
    append_child(body, iframe)

    requests = extract_subresources(document)

    assert [(request.reason, request.url, request.policy_hint) for request in requests] == [
        (FetchReason.SCRIPT, "https://cdn.test/app.js", PolicyHint.ACTIVE),
        (FetchReason.IMAGE, "https://example.com/img/photo.png", PolicyHint.PASSIVE),
        (FetchReason.STYLESHEET, "https://example.com/site.css", PolicyHint.PASSIVE),
        (FetchReason.IFRAME, "https://example.com/articles/embed.html", PolicyHint.ACTIVE),
    ]


def test_ignores_non_stylesheet_links_and_missing_urls() -> None:
    document = Document(id=NodeId("doc"), url="https://example.com/")
    append_child(document, Element(id=NodeId("link"), tag="link", attrs={"rel": "canonical", "href": "/"}))
    append_child(document, Element(id=NodeId("img"), tag="img"))

    assert extract_subresources(document) == []


def test_extract_subresources_from_fixture() -> None:
    from pathlib import Path

    from neuzelaar.core.fetch.client import FetchClient
    from neuzelaar.core.fetch.resource import FetchReason, Request
    from neuzelaar.core.handlers.registry import default_registry
    from neuzelaar.core.mime.classifier import classify_resource
    from neuzelaar.core.origin import parse_url

    record = parse_url(Path("tests/fixtures/sites/stylesheet_link.html").resolve().as_uri())
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
    resource = FetchClient().fetch(request)
    handled = default_registry().handle(resource, classify_resource(resource))

    requests = extract_subresources(handled.value)

    assert len(requests) == 2
    assert requests[0].reason == FetchReason.STYLESHEET
    assert requests[0].url == "https://cdn.example.test/style.css"
    assert requests[1].reason == FetchReason.STYLESHEET
    assert requests[1].url.endswith("local.css")
