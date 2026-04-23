from pathlib import Path

from neuzelaar.core.page import PageLoader, PassiveResourceBudget
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


def test_page_loader_computes_styles_from_style_blocks_and_inline_styles() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/styled_page.html").resolve().as_uri())

    assert result.root_style.color == "red"
    assert result.root_style.background_color == "#eeeeee"


def test_page_loader_fetches_same_origin_stylesheets() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/linked_styles.html").resolve().as_uri())

    assert len(result.stylesheet_urls) == 1
    assert result.stylesheet_urls[0].endswith("/tests/fixtures/sites/linked_styles.css")
    assert result.root_style.color == "blue"
    assert result.root_style.background_color == "#dddddd"


def test_page_loader_fetches_same_origin_images() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())

    assert len(result.images) == 1
    image = next(iter(result.images.values()))
    assert image.url.endswith("/tests/fixtures/sites/placeholder.png")
    assert image.bitmap.width == 1
    assert image.bitmap.height == 1


def test_page_loader_evaluates_planned_subresources() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/third_party_script.html").resolve().as_uri())

    assert len(result.planned_subresources) == 1
    planned = result.planned_subresources[0]
    assert planned.normalized_url == "https://cdn.third-party.test/app.js"
    assert planned.decision.action == PolicyAction.BLOCK
    assert len(result.scripts) == 1


def test_page_loader_plans_inline_scripts_through_js_engine() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/inline_script.html").resolve().as_uri())

    assert len(result.scripts) == 1
    execution = next(iter(result.scripts.values()))
    assert execution.status.value == "blocked"
    assert execution.reason == "JavaScript execution is disabled"


def test_page_loader_blocks_third_party_images_in_strict_mode() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())

    external = [
        planned
        for planned in result.planned_subresources
        if planned.normalized_url == "https://example.com/external.png"
    ][0]

    assert external.decision.action == PolicyAction.BLOCK


def test_page_loader_applies_passive_stylesheet_budget() -> None:
    loader = PageLoader(passive_budget=PassiveResourceBudget(max_stylesheets=0))

    result = loader.load(Path("tests/fixtures/sites/linked_styles.html").resolve().as_uri())

    assert result.stylesheet_urls == ()
    assert result.root_style.color == "#141414"


def test_page_loader_applies_passive_image_budget() -> None:
    loader = PageLoader(passive_budget=PassiveResourceBudget(max_images=0))

    result = loader.load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())

    assert result.images == {}
