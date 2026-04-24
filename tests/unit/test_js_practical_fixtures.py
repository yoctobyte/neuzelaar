import pytest

from neuzelaar.engines.js.fixture_runner import (
    PracticalJsFixture,
    compare_practical_fixture,
    run_practical_fixture,
)
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture, DocumentNodeFixture

quickjs = pytest.importorskip("quickjs")


def test_practical_fixture_console_and_document_effects_match() -> None:
    fixture = PracticalJsFixture(
        name="article-console",
        scenario=BrowserScenarioFixture(
            url="https://example.test/articles/intro",
            title="Intro Article",
            history_entries=("/home", "/articles/intro"),
            history_index=1,
            nodes=(
                DocumentNodeFixture(id="headline", text_content="Intro Article"),
                DocumentNodeFixture(id="lead", text_content="Draft"),
            ),
        ),
        source=(
            "console.log(document.title); "
            "document.getElementById('lead').textContent = 'Published'; "
            "document.setTitle('Updated Article');"
        ),
    )

    comparison = compare_practical_fixture(fixture)

    assert comparison.matches
    assert comparison.own.console_entries == (("log", ("Intro Article",)),)
    assert comparison.own.title == "Updated Article"
    assert comparison.own.node_text_by_id["lead"] == "Published"


def test_practical_fixture_location_history_and_timers_match() -> None:
    fixture = PracticalJsFixture(
        name="nav-timers",
        scenario=BrowserScenarioFixture(
            url="https://example.test/settings",
            title="Settings",
            history_entries=("/home", "/settings"),
            history_index=1,
        ),
        source=(
            "var id = setTimeout(function () { return 1; }, 250, 'x'); "
            "clearTimeout(id); "
            "location.assign('https://example.test/settings?saved=1'); "
            "history.pushState(null, '', '/settings?saved=1');"
        ),
    )

    comparison = compare_practical_fixture(fixture)

    assert comparison.matches
    assert comparison.own.location_href == "https://example.test/settings?saved=1"
    assert comparison.own.history_entries == ("/home", "/settings", "/settings?saved=1")


def test_practical_fixture_runner_can_run_own_only_when_debugging() -> None:
    fixture = PracticalJsFixture(
        name="own-only",
        scenario=BrowserScenarioFixture(
            nodes=(DocumentNodeFixture(id="status", text_content="idle"),),
        ),
        source="document.getElementById('status').textContent = 'done';",
    )

    outcome = run_practical_fixture(fixture, engine="own")

    assert outcome.status == "ran"
    assert outcome.node_text_by_id["status"] == "done"
