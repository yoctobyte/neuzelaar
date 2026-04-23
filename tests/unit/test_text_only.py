from pathlib import Path

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.handlers.registry import default_registry
from neuzelaar.core.mime.classifier import classify_resource
from neuzelaar.core.origin import parse_url
from neuzelaar.render.text_only import render_text


def render_fixture(name: str) -> str:
    record = parse_url(Path(f"tests/fixtures/sites/{name}").resolve().as_uri())
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
    return render_text(handled.value)


def test_text_renderer_renders_links_with_href() -> None:
    rendered = render_fixture("basic_links.html")

    assert "External Link <https://example.com>" in rendered
    assert "Relative Link <example.html>" in rendered


def test_text_renderer_renders_lists() -> None:
    rendered = render_fixture("basic_lists.html")

    assert "- Unordered item 1" in rendered
    assert "- Ordered item 2" in rendered


def test_text_renderer_renders_images_as_placeholders() -> None:
    rendered = render_fixture("basic_images.html")

    assert "[image: Local Placeholder]" in rendered
    assert "[image: External Image]" in rendered


def test_text_renderer_ignores_hidden_tags() -> None:
    rendered = render_fixture("script_and_style_ignored.html")

    assert "# Visible Title" in rendered
    assert "Visible paragraph." in rendered
    assert "console.log" not in rendered
    assert "background: red" not in rendered
    assert "document.write" not in rendered


def test_text_renderer_renders_nested_blocks() -> None:
    rendered = render_fixture("nested_blocks.html")

    assert "# Main Article" in rendered
    assert "## Section Title" in rendered
    assert "Paragraph inside a div inside a section inside an article." in rendered
    assert "This is a blockquote." in rendered
