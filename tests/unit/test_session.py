from pathlib import Path

from neuzelaar.core.policy.capability import PermissionScope
from neuzelaar.core.policy.profile import PolicyProfile
from neuzelaar.core.session import BrowserSession, SessionError
from neuzelaar.engines.js.interface import ScriptExecutionRequest
from neuzelaar.engines.js.own_ticked_engine import OwnTickedJavaScriptEngine
from neuzelaar.engines.js_own.host_scenarios import BrowserScenarioFixture


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


def test_session_defaults_to_balanced_profile_and_can_switch() -> None:
    session = BrowserSession()

    assert session.policy_profile is PolicyProfile.BALANCED

    session.set_policy_profile(PolicyProfile.STRICT)

    assert session.policy_profile is PolicyProfile.STRICT
    assert session.loader.policy_engine.profile is PolicyProfile.STRICT


def test_session_grant_script_permission_updates_shared_permission_state() -> None:
    session = BrowserSession()
    session.open_url(fixture_url("inline_script.html"))

    session.grant_script_permission(1, PermissionScope.ORIGIN)

    assert session.permission_service.store.permissions
    assert session.permission_service.store.permissions[0].capability.name == "EXEC_INLINE_JS"


def test_session_resets_ticked_js_engine_between_page_loads() -> None:
    engine = OwnTickedJavaScriptEngine(scenario_fixture=BrowserScenarioFixture())
    session = BrowserSession(js_engine=engine)

    # First load installs the engine and seeds it with a long-pending
    # timer. The page itself has no scripts, but we use execute()
    # directly to reach into the same runtime the loader would use.
    session.open_url(fixture_url("example.html"))
    engine.execute(
        ScriptExecutionRequest(source="setTimeout(function () {}, 60000);")
    )
    assert engine.has_pending_work() is True

    # Navigating to another page must reset the engine, dropping the
    # previous page's timers.
    session.open_url(fixture_url("example.html"))

    assert engine.has_pending_work() is False
    # session.js_engine must point at the user-provided engine, not None.
    assert session.js_engine is engine


def test_session_with_ticked_engine_runs_inline_script_against_real_dom() -> None:
    from neuzelaar.core.bus import Bus
    from neuzelaar.shell_api.events import ConsoleLog

    bus = Bus()
    logs: list[ConsoleLog] = []
    bus.subscribe(ConsoleLog, logs.append)
    engine = OwnTickedJavaScriptEngine(bus=bus)
    session = BrowserSession(bus=bus, js_engine=engine)

    session.open_url(fixture_url("console_probe.html"))

    texts = [log.text for log in logs]
    # Title comes from the parsed <title>; getElementById finds the
    # real <h1 id="hero"> text; href reflects the file:// URL the
    # loader actually used.
    assert "title:Console Probe" in texts
    assert "hero:Hello, World" in texts
    assert any(t.startswith("href:file://") and t.endswith("console_probe.html") for t in texts)


def test_script_textcontent_write_propagates_to_real_dom_and_publishes_dommutated() -> None:
    from neuzelaar.core.bus import Bus
    from neuzelaar.document.dom import Element, Text, walk
    from neuzelaar.shell_api.events import DomMutated

    bus = Bus()
    mutations: list[DomMutated] = []
    bus.subscribe(DomMutated, mutations.append)
    engine = OwnTickedJavaScriptEngine(bus=bus)
    session = BrowserSession(bus=bus, js_engine=engine)

    result = session.open_url(fixture_url("dom_mutate.html"))

    # Find the h1 in the parsed document and assert its text was
    # rewritten by the inline script.
    document = result.handler_result.value
    hero = next(
        node for node in walk(document)
        if isinstance(node, Element) and node.attr("id") == "hero"
    )
    text_children = [child for child in hero.children if isinstance(child, Text)]
    assert len(text_children) == 1
    assert text_children[0].data == "after"

    # And the bridge fired a DomMutated event so a UI shell could
    # debounce-repaint.
    assert len(mutations) == 1
    assert mutations[0].property == "textContent"


def test_settimeout_mutation_only_lands_after_a_tick() -> None:
    from neuzelaar.core.bus import Bus
    from neuzelaar.document.dom import Element, Text, walk
    from neuzelaar.engines.js.interface import ScriptExecutionRequest
    from neuzelaar.shell_api.events import DomMutated

    bus = Bus()
    mutations: list[DomMutated] = []
    bus.subscribe(DomMutated, mutations.append)
    engine = OwnTickedJavaScriptEngine(bus=bus)
    session = BrowserSession(bus=bus, js_engine=engine)

    # Open a page that just has the h1 — schedule the mutation as a
    # timer via direct execute() so we control when it fires.
    result = session.open_url(fixture_url("dom_mutate.html"))

    document = result.handler_result.value
    hero = next(
        node for node in walk(document)
        if isinstance(node, Element) and node.attr("id") == "hero"
    )

    # Reset baseline: open_url ran the page's inline script which
    # already wrote "after". Drop those mutation events so we observe
    # only the timer-driven one below.
    mutations.clear()

    engine.execute(
        ScriptExecutionRequest(
            source=(
                'setTimeout(function () {'
                '  document.getElementById("hero").textContent = "from-timer";'
                '}, 0);'
            )
        )
    )

    # Before the tick: nothing has changed.
    assert mutations == []
    text_now = next(c for c in hero.children if isinstance(c, Text)).data
    assert text_now == "after"

    engine.tick(timeout_ms=20.0)

    # After the tick: the timer fired, the bridge wrote through.
    assert len(mutations) == 1
    assert mutations[0].property == "textContent"
    text_after = next(c for c in hero.children if isinstance(c, Text)).data
    assert text_after == "from-timer"
