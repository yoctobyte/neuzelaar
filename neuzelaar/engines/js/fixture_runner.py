"""Fixture-only practical JS scenario runner for backend comparison."""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.errors import JavaScriptThrownValue
from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.host_scenarios import (
    BrowserScenarioFixture,
    BrowserHostStubs,
    build_browser_scenario,
)
from neuzelaar.engines.js_own.values import read_property

try:
    import quickjs as _quickjs
except ImportError:  # pragma: no cover
    _quickjs = None

from neuzelaar.engines.js_own.interpreter import evaluate_program


@dataclass(frozen=True, slots=True)
class PracticalJsFixture:
    name: str
    scenario: BrowserScenarioFixture
    source: str


@dataclass(frozen=True, slots=True)
class PracticalJsOutcome:
    engine: str
    status: str
    reason: str
    console_entries: tuple[tuple[str, tuple[object, ...]], ...]
    title: str
    location_href: str
    history_entries: tuple[str, ...]
    history_index: int
    node_text_by_id: dict[str, str]


@dataclass(frozen=True, slots=True)
class PracticalJsComparison:
    fixture: PracticalJsFixture
    own: PracticalJsOutcome
    quickjs: PracticalJsOutcome

    @property
    def matches(self) -> bool:
        return (
            self.own.status == self.quickjs.status
            and self.own.reason == self.quickjs.reason
            and self.own.console_entries == self.quickjs.console_entries
            and self.own.title == self.quickjs.title
            and self.own.location_href == self.quickjs.location_href
            and self.own.history_entries == self.quickjs.history_entries
            and self.own.history_index == self.quickjs.history_index
            and self.own.node_text_by_id == self.quickjs.node_text_by_id
        )


def run_practical_fixture(fixture: PracticalJsFixture, *, engine: str) -> PracticalJsOutcome:
    environment, stubs = build_browser_scenario(fixture.scenario)
    if engine == "own":
        return _run_own(fixture.source, environment, stubs)
    if engine == "quickjs":
        return _run_quickjs(fixture.source, environment, stubs)
    raise ValueError(f"Unknown engine: {engine}")


def compare_practical_fixture(fixture: PracticalJsFixture) -> PracticalJsComparison:
    return PracticalJsComparison(
        fixture=fixture,
        own=run_practical_fixture(fixture, engine="own"),
        quickjs=run_practical_fixture(fixture, engine="quickjs"),
    )


def _run_own(source: str, environment: Environment, stubs: BrowserHostStubs) -> PracticalJsOutcome:
    try:
        evaluate_program(source, environment)
        status = "ran"
        reason = "ok"
    except JavaScriptThrownValue as exc:
        status = "error"
        reason = f"Thrown: {exc.value!r}"
    except Exception as exc:
        status = "error"
        reason = f"{type(exc).__name__}: {exc}"
    return _snapshot("own", status, reason, stubs)


def _run_quickjs(source: str, environment: Environment, stubs: BrowserHostStubs) -> PracticalJsOutcome:
    if _quickjs is None:  # pragma: no cover
        raise RuntimeError("quickjs package is not installed")
    context = _quickjs.Context()
    _install_quickjs_bridge(context, environment, stubs)
    try:
        context.eval(source)
        status = "ran"
        reason = "ok"
    except Exception as exc:
        status = "error"
        reason = f"{type(exc).__name__}: {exc}"
    return _snapshot("quickjs", status, reason, stubs)


def _install_quickjs_bridge(context, environment: Environment, stubs: BrowserHostStubs) -> None:
    console = environment.get("console")
    document = environment.get("document")
    location = environment.get("location")
    history = environment.get("history")
    context.add_callable("_py_console_log", lambda *args: read_property(console, "log").call(tuple(args)))
    context.add_callable("_py_console_warn", lambda *args: read_property(console, "warn").call(tuple(args)))
    context.add_callable("_py_console_error", lambda *args: read_property(console, "error").call(tuple(args)))
    context.add_callable("_py_console_count", lambda *args: read_property(console, "count").call(tuple(args)))
    context.add_callable(
        "_py_set_timeout",
        lambda *args: environment.get("setTimeout").call(tuple(args)),
    )
    context.add_callable(
        "_py_clear_timeout",
        lambda *args: environment.get("clearTimeout").call(tuple(args)),
    )
    context.add_callable(
        "_py_document_get_element_by_id",
        lambda identifier: str(identifier) if str(identifier) in stubs.document.nodes_by_id else None,
    )
    context.add_callable(
        "_py_node_get_text",
        lambda identifier: read_property(stubs.document.nodes_by_id[str(identifier)], "textContent"),
    )
    context.add_callable(
        "_py_node_set_text",
        lambda identifier, value: stubs.document.nodes_by_id[str(identifier)].set("textContent", value),
    )
    context.add_callable(
        "_py_document_set_title",
        lambda value: read_property(document, "setTitle").call((value,), this_value=document),
    )
    context.add_callable(
        "_py_document_get_title",
        lambda: read_property(document, "title"),
    )
    context.add_callable(
        "_py_location_assign",
        lambda value: read_property(location, "assign").call((value,), this_value=location),
    )
    context.add_callable(
        "_py_location_get_href",
        lambda: read_property(location, "href"),
    )
    context.add_callable(
        "_py_history_push_state",
        lambda state, title, url: read_property(history, "pushState").call((state, title, url), this_value=history),
    )
    context.add_callable(
        "_py_history_back",
        lambda: read_property(history, "back").call((), this_value=history),
    )
    context.add_callable(
        "_py_history_get_length",
        lambda: read_property(history, "length"),
    )
    context.eval(
        """
var console = {
  log: function() { return _py_console_log.apply(null, arguments); },
  warn: function() { return _py_console_warn.apply(null, arguments); },
  error: function() { return _py_console_error.apply(null, arguments); },
  count: function(label) { return _py_console_count(label); }
};
var setTimeout = function() { return _py_set_timeout.apply(null, arguments); };
var clearTimeout = function(id) { return _py_clear_timeout(id); };
var document = {
  get title() { return _py_document_get_title(); },
  set title(value) { _py_document_set_title(value); },
  setTitle: function(value) { return _py_document_set_title(value); },
  getElementById: function(id) {
    var nodeId = _py_document_get_element_by_id(id);
    if (nodeId === null || nodeId === undefined) {
      return null;
    }
    return {
      get textContent() { return _py_node_get_text(nodeId); },
      set textContent(value) { _py_node_set_text(nodeId, value); }
    };
  }
};
var location = {
  get href() { return _py_location_get_href(); },
  assign: function(value) { return _py_location_assign(value); }
};
var history = {
  get length() { return _py_history_get_length(); },
  pushState: function(state, title, url) { return _py_history_push_state(state, title, url); },
  back: function() { return _py_history_back(); }
};
"""
    )


def _snapshot(engine: str, status: str, reason: str, stubs: BrowserHostStubs) -> PracticalJsOutcome:
    return PracticalJsOutcome(
        engine=engine,
        status=status,
        reason=reason,
        console_entries=tuple(stubs.console.entries),
        title=stubs.document.title,
        location_href=stubs.location.href,
        history_entries=tuple(stubs.history.entries),
        history_index=stubs.history.index,
        node_text_by_id={
            node_id: str(read_property(node, "textContent"))
            for node_id, node in stubs.document.nodes_by_id.items()
        },
    )
