"""Fixture-driven host scenarios for standalone JS tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuzelaar.engines.js_own.builtins import install_builtins
from neuzelaar.engines.js_own.config import (
    SCRIPT_DEBUG_KEEP_HISTORY_KEY,
    SCRIPT_DEBUG_TRACK_TASKS_KEY,
    ScriptRuntimeConfig,
)
from neuzelaar.engines.js_own.environment import Environment
from neuzelaar.engines.js_own.host import HostObject
from neuzelaar.engines.js_own.host_stubs import BrowserHostStubs, HostDocument, HostHistory, HostLocation
from neuzelaar.engines.js_own.scheduler import ScriptScheduler


@dataclass(frozen=True, slots=True)
class DocumentNodeFixture:
    id: str
    text_content: str = ""
    extra_properties: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrowserScenarioFixture:
    url: str = "https://example.test/"
    title: str = ""
    history_entries: tuple[str, ...] = ()
    history_index: int = -1
    nodes: tuple[DocumentNodeFixture, ...] = ()
    scheduler_debug: bool = False


def build_browser_scenario(fixture: BrowserScenarioFixture) -> tuple[Environment, BrowserHostStubs]:
    environment = Environment()
    install_builtins(environment)
    stubs = BrowserHostStubs(
        document=HostDocument(title=fixture.title),
        location=HostLocation(fixture.url),
        history=HostHistory(entries=list(fixture.history_entries), index=fixture.history_index),
        scheduler=(
            ScriptScheduler(
                config=ScriptRuntimeConfig.from_settings(
                    {
                        SCRIPT_DEBUG_TRACK_TASKS_KEY: fixture.scheduler_debug,
                        SCRIPT_DEBUG_KEEP_HISTORY_KEY: fixture.scheduler_debug,
                    }
                )
            )
            if fixture.scheduler_debug
            else None
        ),
    )
    stubs.timers.scheduler = stubs.scheduler
    stubs.timers.scheduler_origin = fixture.url
    stubs.timers.scheduler_url = fixture.url
    for node_fixture in fixture.nodes:
        properties = {"textContent": node_fixture.text_content}
        properties.update(node_fixture.extra_properties)
        stubs.document.nodes_by_id[node_fixture.id] = HostObject(properties=properties)
    stubs.install(environment)
    return environment, stubs


def article_reader_scenario() -> tuple[Environment, BrowserHostStubs]:
    return build_browser_scenario(
        BrowserScenarioFixture(
            url="https://example.test/articles/intro",
            title="Intro Article",
            history_entries=("/home", "/articles/intro"),
            history_index=1,
            nodes=(
                DocumentNodeFixture(id="headline", text_content="Intro Article"),
                DocumentNodeFixture(id="lead", text_content="A concise fixture article."),
            ),
        )
    )


def settings_page_scenario() -> tuple[Environment, BrowserHostStubs]:
    return build_browser_scenario(
        BrowserScenarioFixture(
            url="https://example.test/settings",
            title="Settings",
            history_entries=("/home", "/settings"),
            history_index=1,
            nodes=(
                DocumentNodeFixture(id="status", text_content="idle"),
                DocumentNodeFixture(id="save", text_content="Save"),
            ),
        )
    )
