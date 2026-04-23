from pathlib import Path

from neuzelaar.core.browser import BrowserState, BrowserStateError


def fixture_url(name: str) -> str:
    return Path(f"tests/fixtures/sites/{name}").resolve().as_uri()


def test_browser_state_creates_and_switches_tabs() -> None:
    browser = BrowserState()
    first = browser.new_tab(fixture_url("example.html"))
    second = browser.new_tab(fixture_url("basic_lists.html"))

    assert browser.active_tab_id == second.id
    assert "Basic Lists" in browser.active_tab.current.rendered_text

    browser.switch_tab(first.id)

    assert browser.active_tab_id == first.id
    assert "Example Domain" in browser.active_tab.current.rendered_text


def test_browser_state_keeps_history_isolated_per_tab() -> None:
    browser = BrowserState()
    tab1 = browser.new_tab(fixture_url("basic_links.html"))
    browser.follow_link(2)
    tab2 = browser.new_tab(fixture_url("basic_lists.html"))

    assert tab2.session.current_index == 0
    browser.switch_tab(tab1.id)
    assert tab1.session.current_index == 1
    assert "Example Domain" in browser.active_tab.current.rendered_text


def test_browser_state_close_and_error_paths() -> None:
    browser = BrowserState()
    tab = browser.new_tab()
    browser.close_tab(tab.id)

    assert browser.active_tab_id is None

    try:
        browser.switch_tab(tab.id)
    except BrowserStateError as exc:
        assert "No tab with id" in str(exc)
    else:
        raise AssertionError("expected BrowserStateError")
