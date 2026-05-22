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


def test_parse_html_comments() -> None:
    from neuzelaar.document.dom import Comment, Text
    from neuzelaar.render.text_only import render_text

    html = """
    <!doctype html>
    <html>
      <body>
        <!-- normal comment -->
        <!--[if lt IE 9]><script src="//a.fsdn.com/sd/html5.js"></script><![endif]-->
        <p>Visible content</p>
      </body>
    </html>
    """

    document = parse_html(html, url="https://example.com")
    nodes = list(walk(document))

    comments = [node for node in nodes if isinstance(node, Comment)]
    assert len(comments) == 2
    assert comments[0].data.strip() == "normal comment"
    assert "if lt IE 9" in comments[1].data

    # Ensure none of the comments are treated as elements with tag "unknown"
    unknowns = [node for node in nodes if isinstance(node, Element) and node.tag == "unknown"]
    assert len(unknowns) == 0

    # Ensure comments are NOT rendered in semantic text output
    text_output = render_text(document)
    assert "normal comment" not in text_output
    assert "html5.js" not in text_output
    assert "Visible content" in text_output
