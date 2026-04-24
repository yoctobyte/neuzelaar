from neuzelaar.document.dom import Element, walk
from neuzelaar.engines.html.html5lib_adapter import parse_html


def test_parse_html_handles_live_site_non_string_tags() -> None:
    html = """
    <!doctype html>
    <html>
      <body>
        <svg><g></g></svg>
        <p>Hello</p>
      </body>
    </html>
    """

    document = parse_html(html, url="https://example.com")

    assert document.url == "https://example.com"
    tags = [node.tag for node in walk(document) if isinstance(node, Element)]
    assert "svg" in tags
    assert "g" in tags
    assert "p" in tags
