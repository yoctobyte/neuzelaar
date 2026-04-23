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
