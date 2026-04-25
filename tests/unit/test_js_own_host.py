from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.host_scenarios import (
    BrowserScenarioFixture,
    DocumentNodeFixture,
    article_reader_scenario,
    build_browser_scenario,
    settings_page_scenario,
)
from neuzelaar.engines.js_own.host_stubs import BrowserHostStubs
from neuzelaar.engines.js_own.config import (
    SCRIPT_BUDGET_MAX_MS_KEY,
    SCRIPT_BUDGET_MAX_STEPS_KEY,
    SCRIPT_DEBUG_KEEP_HISTORY_KEY,
    SCRIPT_DEBUG_MAX_HISTORY_KEY,
    SCRIPT_DEBUG_TRACK_TASKS_KEY,
    ScriptRuntimeConfig,
)
from neuzelaar.engines.js_own.scheduler import (
    ScriptScheduler,
    ScriptTaskKind,
    ScriptTaskPriority,
)
from neuzelaar.engines.js_own.interpreter import evaluate_program
from neuzelaar.engines.js_own.values import (
    is_callable,
    read_index,
    read_property,
    write_index,
    write_property,
)


def test_host_object_property_bridge_round_trip() -> None:
    host = HostObject(properties={"x": 1.0})

    assert read_property(host, "x") == 1.0
    assert write_property(host, "x", 4.0) == 4.0
    assert read_property(host, "x") == 4.0


def test_host_object_index_bridge_round_trip() -> None:
    host = HostObject(properties={"0": "a"})

    assert read_index(host, 0.0) == "a"
    assert write_index(host, "1", "b") == "b"
    assert read_index(host, 1.0) == "b"


def test_host_callable_is_callable() -> None:
    fn = HostCallable("id", lambda args, _this: args[0] if args else None)

    assert is_callable(fn) is True
    assert fn.call((3.0,), this_value=None) == 3.0


def test_builtins_install_via_host_bridge() -> None:
    env = Environment()
    install_builtins(env)

    math_value = env.get("Math")
    number_value = env.get("Number")

    assert isinstance(math_value, HostObject)
    assert isinstance(number_value, HostCallable)
    assert read_property(math_value, "abs").call((-2.0,), this_value=None) == 2.0


def test_host_object_can_be_exposed_to_program() -> None:
    env = Environment()
    install_builtins(env)
    env.declare(
        "host",
        HostObject(
            properties={
                "value": 7.0,
                "bump": HostCallable("host.bump", lambda _args, this: read_property(this, "value") + 1.0),
            }
        ),
        kind="const",
    )

    assert evaluate_program("host.value;", env) == 7.0
    assert evaluate_program("host.bump();", env) == 8.0


def test_browser_host_console_stub_collects_entries() -> None:
    env = Environment()
    install_builtins(env)
    stubs = BrowserHostStubs()
    stubs.install(env)

    result = evaluate_program('console.log("a", 1); console.count("x"); console.count("x");', env)

    assert result == 2.0
    assert stubs.console.entries[0] == ("log", ("a", 1.0))
    assert stubs.console.entries[1] == ("count", ("x", 1.0))
    assert stubs.console.entries[2] == ("count", ("x", 2.0))


def test_browser_host_timer_stub_records_scheduled_and_cleared() -> None:
    env = Environment()
    install_builtins(env)
    stubs = BrowserHostStubs()
    stubs.install(env)

    result = evaluate_program(
        "var id = setTimeout(function () { return 1; }, 250, 'a'); clearTimeout(id); id;",
        env,
    )

    assert result == 1.0
    assert stubs.timers.scheduled[0]["id"] == 1
    assert stubs.timers.scheduled[0]["delay"] == 250.0
    assert stubs.timers.scheduled[0]["arguments"] == ("a",)
    assert 1 in stubs.timers.cleared


def test_browser_host_timer_stub_can_emit_scheduler_debug_tasks() -> None:
    env = Environment()
    install_builtins(env)
    stubs = BrowserHostStubs(scheduler=ScriptScheduler())
    stubs.timers.scheduler = stubs.scheduler
    stubs.timers.scheduler_origin = "https://example.test/page"
    stubs.timers.scheduler_url = "https://example.test/page"
    stubs.install(env)

    evaluate_program("setTimeout(function () { return 1; }, 250, 'a');", env)

    assert stubs.scheduler is not None
    snapshots = stubs.scheduler.snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].kind == ScriptTaskKind.TIMER.value
    assert snapshots[0].state == "queued"
    assert snapshots[0].metadata["timer_id"] == 1
    assert snapshots[0].metadata["delay"] == 250.0


def test_browser_host_document_stub_exposes_title_and_nodes() -> None:
    env = Environment()
    install_builtins(env)
    stubs = BrowserHostStubs()
    node = HostObject(properties={"textContent": "hello"})
    stubs.document.nodes_by_id["hero"] = node
    stubs.install(env)

    result = evaluate_program(
        "document.setTitle('Test Title'); document.getElementById('hero').textContent;",
        env,
    )

    assert result == "hello"
    assert stubs.document.title == "Test Title"


def test_browser_host_location_and_history_stubs_hold_meaningful_state() -> None:
    env = Environment()
    install_builtins(env)
    stubs = BrowserHostStubs()
    stubs.install(env)

    result = evaluate_program(
        "location.assign('https://example.test/a'); "
        "history.pushState(null, '', '/a'); "
        "history.pushState(null, '', '/b'); "
        "history.back();",
        env,
    )

    assert stubs.location.href == "https://example.test/a"
    assert stubs.history.entries == ["/a", "/b"]
    assert stubs.history.index == 0
    assert result == "/a"


def test_browser_scenario_fixture_builds_meaningful_page_state() -> None:
    env, stubs = build_browser_scenario(
        BrowserScenarioFixture(
            url="https://example.test/post/1",
            title="Post 1",
            history_entries=("/home", "/post/1"),
            history_index=1,
            nodes=(
                DocumentNodeFixture(id="headline", text_content="Post 1"),
                DocumentNodeFixture(id="body", text_content="Hello world"),
            ),
        )
    )

    result = evaluate_program(
        "document.title + '|' + location.href + '|' + document.getElementById('headline').textContent;",
        env,
    )

    assert result == "Post 1|https://example.test/post/1|Post 1"
    assert stubs.history.entries == ["/home", "/post/1"]


def test_article_reader_scenario_is_useful_as_ready_fixture() -> None:
    env, stubs = article_reader_scenario()

    result = evaluate_program(
        "console.log(document.title); "
        "document.getElementById('lead').textContent + ' @ ' + location.href;",
        env,
    )

    assert result == "A concise fixture article. @ https://example.test/articles/intro"
    assert stubs.console.entries == [("log", ("Intro Article",))]


def test_settings_page_scenario_can_be_mutated_by_script() -> None:
    env, stubs = settings_page_scenario()

    result = evaluate_program(
        "document.getElementById('status').textContent = 'saved'; "
        "history.pushState(null, '', '/settings?saved=1'); "
        "document.getElementById('status').textContent;",
        env,
    )

    assert result == "saved"
    assert stubs.history.entries == ["/home", "/settings", "/settings?saved=1"]


def test_scheduler_records_history_when_debug_enabled() -> None:
    scheduler = ScriptScheduler(
        config=ScriptRuntimeConfig.from_settings(
            {
                SCRIPT_DEBUG_TRACK_TASKS_KEY: True,
                SCRIPT_DEBUG_KEEP_HISTORY_KEY: True,
            }
        )
    )
    task = scheduler.queue_task(kind=ScriptTaskKind.BACKGROUND_SCRIPT, reason="test")

    started = scheduler.start_next()

    assert started is not None
    scheduler.note_progress(task.task_id, steps_used=12, wall_ms_used=4.5)
    scheduler.complete_task(task.task_id, reason="done")

    history = scheduler.history()
    assert len(history) == 1
    assert history[0].kind == ScriptTaskKind.BACKGROUND_SCRIPT.value
    assert history[0].state == "completed"
    assert history[0].steps_used == 12
    assert history[0].wall_ms_used == 4.5


def test_browser_scenario_can_provide_scheduler_debug_state() -> None:
    env, stubs = build_browser_scenario(
        BrowserScenarioFixture(
            url="https://example.test/debug",
            scheduler_debug=True,
        )
    )

    evaluate_program("setTimeout(function () { return 1; }, 100);", env)

    assert stubs.scheduler is not None
    snapshots = stubs.scheduler.snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].origin == "https://example.test/debug"
    assert snapshots[0].priority == ScriptTaskPriority.BACKGROUND.value


def test_runtime_config_roundtrips_stable_settings_keys() -> None:
    config = ScriptRuntimeConfig.from_settings(
        {
            SCRIPT_BUDGET_MAX_STEPS_KEY: "2500",
            SCRIPT_BUDGET_MAX_MS_KEY: "40.5",
            SCRIPT_DEBUG_TRACK_TASKS_KEY: "true",
            SCRIPT_DEBUG_KEEP_HISTORY_KEY: 1,
            SCRIPT_DEBUG_MAX_HISTORY_KEY: "20",
        }
    )

    assert config.max_steps == 2500
    assert config.max_wall_ms == 40.5
    assert config.debug_track_tasks is True
    assert config.debug_keep_history is True
    assert config.debug_max_history == 20
    assert config.to_settings()[SCRIPT_BUDGET_MAX_STEPS_KEY] == 2500


def test_scheduler_uses_explicit_task_kinds_and_priorities() -> None:
    scheduler = ScriptScheduler()

    task = scheduler.queue_task(
        kind=ScriptTaskKind.CLICK_HANDLER,
        priority=ScriptTaskPriority.USER_BLOCKING,
        reason="click",
    )

    snapshot = task.snapshot()
    assert snapshot.kind == ScriptTaskKind.CLICK_HANDLER.value
    assert snapshot.priority == ScriptTaskPriority.USER_BLOCKING.value
