from neuzelaar.document.dom import Document, Element, NodeId, Text, append_child
from neuzelaar.document.links import extract_links


def test_extracts_links_with_resolved_urls() -> None:
    document = Document(id=NodeId("doc"), url="https://example.com/docs/page.html")
    body = Element(id=NodeId("body"), tag="body")
    link = Element(id=NodeId("link"), tag="a", attrs={"href": "../next.html"})
    append_child(document, body)
    append_child(body, link)
    append_child(link, Text(id=NodeId("text"), data="Next page"))

    links = extract_links(document)

    assert len(links) == 1
    assert links[0].index == 1
    assert links[0].text == "Next page"
    assert links[0].href == "../next.html"
    assert links[0].resolved_url == "https://example.com/next.html"


def test_ignores_anchors_without_href() -> None:
    document = Document(id=NodeId("doc"), url="https://example.com/")
    append_child(document, Element(id=NodeId("anchor"), tag="a"))

    assert extract_links(document) == ()
