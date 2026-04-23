from pathlib import Path

from neuzelaar.core.fetch.client import FetchClient
from neuzelaar.core.fetch.resource import FetchReason, Request
from neuzelaar.core.handlers.registry import default_registry
from neuzelaar.core.mime.classifier import classify_resource
from neuzelaar.core.origin import parse_url
from neuzelaar.document.subresources import extract_subresources
from neuzelaar.render.text_only import render_text


def test_fixture_fetch_classify_parse_render_pipeline() -> None:
    record = parse_url(Path("tests/fixtures/sites/example.html").resolve().as_uri())
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
    decision = classify_resource(resource)
    handled = default_registry().handle(resource, decision)

    assert decision.kind == "html"
    assert handled.kind == "document"
    assert render_text(handled.value).startswith("# Example Fixture")
    assert "##" not in render_text(handled.value)
    assert "Example Domain" in render_text(handled.value)
    assert extract_subresources(handled.value) == []
