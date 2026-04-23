from pathlib import Path

from neuzelaar.core.page import PageLoader
from neuzelaar.core.policy.rules import PolicyAction


def test_page_loader_returns_structured_document_result() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/example.html").resolve().as_uri())

    assert result.resource.status == 200
    assert result.mime_decision.kind == "html"
    assert result.handler_result.kind == "document"
    assert "# Example Fixture" in result.rendered_text
    assert result.planned_subresources == ()
    assert result.forms == ()


def test_page_loader_returns_forms() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_form.html").resolve().as_uri())

    assert len(result.forms) == 1
    assert result.forms[0].controls[0].name == "q"


def test_page_loader_evaluates_planned_subresources() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/third_party_script.html").resolve().as_uri())

    assert len(result.planned_subresources) == 1
    planned = result.planned_subresources[0]
    assert planned.normalized_url == "https://cdn.third-party.test/app.js"
    assert planned.decision.action == PolicyAction.BLOCK
