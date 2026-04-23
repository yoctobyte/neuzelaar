from pathlib import Path

from neuzelaar.core.policy.capability import PermissionScope
from neuzelaar.core.session import BrowserSession, SessionError


def fixture_url(name: str) -> str:
    return Path(f"tests/fixtures/sites/{name}").resolve().as_uri()


def test_session_opens_page_and_tracks_history() -> None:
    session = BrowserSession()

    result = session.open_url(fixture_url("example.html"))

    assert result.rendered_text.startswith("# Example Fixture")
    assert session.current is result
    assert session.current_index == 0
    assert len(session.history) == 1


def test_session_back_and_forward() -> None:
    session = BrowserSession()
    first = session.open_url(fixture_url("example.html"))
    second = session.open_url(fixture_url("basic_lists.html"))

    assert session.back() is first
    assert session.forward() is second


def test_session_open_url_discards_forward_history() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("example.html"))
    session.open_url(fixture_url("basic_lists.html"))
    session.back()

    session.open_url(fixture_url("basic_images.html"))

    assert len(session.history) == 2
    assert "Images Test" in session.current.rendered_text


def test_session_follow_link_by_index() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("basic_links.html"))

    result = session.follow_link(2)

    assert result.resource.final_url.endswith("/tests/fixtures/sites/example.html")
    assert "Example Domain" in result.rendered_text


def test_session_raises_for_invalid_link() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("example.html"))

    try:
        session.follow_link(1)
    except SessionError as exc:
        assert "No link at index" in str(exc)
    else:
        raise AssertionError("expected SessionError")


def test_session_submits_get_form_with_overrides() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("basic_form.html"))

    result = session.submit_form(1, {"q": "changed"})

    assert result.resource.final_url.endswith("form_result.html?q=changed&note=hello&kind=b")
    assert "Form Result" in result.rendered_text


def test_session_grant_script_permission_updates_shared_permission_state() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("inline_script.html"))

    session.grant_script_permission(1, PermissionScope.ORIGIN)

    assert session.permission_service.store.permissions
    assert session.permission_service.store.permissions[0].capability.name == "EXEC_INLINE_JS"
