"""Meaningful standalone host stubs for JS5 testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from neuzelaar.engines.js_own.host import HostCallable, HostObject
from neuzelaar.engines.js_own.runtime import JS_UNDEFINED, js_to_string
from neuzelaar.engines.js_own.runtime_state import current_runtime_state
from neuzelaar.engines.js_own.scheduler import ScriptScheduler


ConsoleSink = Callable[[str, str], None]


@dataclass(slots=True)
class HostConsole:
    entries: list[tuple[str, tuple[object, ...]]] = field(default_factory=list)
    # Optional callback the engine sets to forward console output to a
    # bus / debug pane. Stays None by default so test fixtures can read
    # ``entries`` without paying for a sink call.
    sink: ConsoleSink | None = None

    def as_host_object(self) -> HostObject:
        return HostObject(
            properties={
                "log": HostCallable("console.log", self._log),
                "warn": HostCallable("console.warn", self._warn),
                "error": HostCallable("console.error", self._error),
                "count": HostCallable("console.count", self._count),
            }
        )

    def _log(self, arguments: tuple[object, ...], _this: object | None) -> object:
        self.entries.append(("log", arguments))
        self._emit("log", arguments)
        return None

    def _warn(self, arguments: tuple[object, ...], _this: object | None) -> object:
        self.entries.append(("warn", arguments))
        self._emit("warn", arguments)
        return None

    def _error(self, arguments: tuple[object, ...], _this: object | None) -> object:
        self.entries.append(("error", arguments))
        self._emit("error", arguments)
        return None

    def _count(self, arguments: tuple[object, ...], _this: object | None) -> object:
        label = js_to_string(arguments[0] if arguments else "default")
        seen = sum(1 for level, args in self.entries if level == "count" and js_to_string(args[0] if args else "default") == label)
        self.entries.append(("count", (label, seen + 1.0)))
        self._emit("count", (label, float(seen + 1)))
        return float(seen + 1)

    def _emit(self, level: str, arguments: tuple[object, ...]) -> None:
        if self.sink is None:
            return
        self.sink(level, " ".join(js_to_string(arg) for arg in arguments))


@dataclass(slots=True)
class HostTimers:
    next_id: int = 1
    scheduled: list[dict[str, object]] = field(default_factory=list)
    cleared: set[int] = field(default_factory=set)
    scheduler: ScriptScheduler | None = None
    scheduler_origin: str | None = None
    scheduler_url: str | None = None

    def as_bindings(self) -> dict[str, HostCallable]:
        return {
            "setTimeout": HostCallable("setTimeout", self._set_timeout),
            "clearTimeout": HostCallable("clearTimeout", self._clear_timeout),
            "setInterval": HostCallable("setInterval", self._set_interval),
            "clearInterval": HostCallable("clearInterval", self._clear_timeout),
        }

    def _set_timeout(self, arguments: tuple[object, ...], _this: object | None) -> object:
        return self._schedule(arguments, repeat=False)

    def _set_interval(self, arguments: tuple[object, ...], _this: object | None) -> object:
        return self._schedule(arguments, repeat=True)

    def _schedule(self, arguments: tuple[object, ...], *, repeat: bool) -> object:
        callback = arguments[0] if arguments else None
        delay = arguments[1] if len(arguments) > 1 else 0.0
        if delay is None or delay is JS_UNDEFINED:
            delay = 0.0
        timer_id = self.next_id
        self.next_id += 1
        self.scheduled.append(
            {
                "id": timer_id,
                "callback": callback,
                "delay": delay,
                "arguments": arguments[2:],
                "repeat": repeat,
            }
        )
        runtime = current_runtime_state()
        if runtime is not None and hasattr(callback, "call"):
            runtime.queue_timer(
                lambda: callback.call(tuple(arguments[2:]), this_value=None),
                timer_id=timer_id,
                delay_ms=float(delay),
                repeat=repeat,
                reason="setInterval" if repeat else "setTimeout",
                origin=self.scheduler_origin,
                url=self.scheduler_url,
            )
        return float(timer_id)

    def _clear_timeout(self, arguments: tuple[object, ...], _this: object | None) -> object:
        if arguments:
            timer_id = int(arguments[0])
            self.cleared.add(timer_id)
            runtime = current_runtime_state()
            if runtime is not None:
                runtime.cancel_timer(timer_id)
            if self.scheduler is not None:
                for scheduled in self.scheduled:
                    if scheduled["id"] == timer_id and "task_id" in scheduled:
                        self.scheduler.cancel_task(int(scheduled["task_id"]), reason="clearTimeout")
                        break
        return None


@dataclass(slots=True)
class HostDocument:
    title: str = ""
    nodes_by_id: dict[str, HostObject] = field(default_factory=dict)

    def as_host_object(self) -> HostObject:
        document = HostObject()
        document.set("title", self.title)
        document.set("getElementById", HostCallable("document.getElementById", self._get_element_by_id))
        document.set("setTitle", HostCallable("document.setTitle", self._set_title))
        return document

    def _get_element_by_id(self, arguments: tuple[object, ...], _this: object | None) -> object:
        identifier = js_to_string(arguments[0] if arguments else "")
        return self.nodes_by_id.get(identifier)

    def _set_title(self, arguments: tuple[object, ...], this: object | None) -> object:
        self.title = js_to_string(arguments[0] if arguments else "")
        if isinstance(this, HostObject):
            this.set("title", self.title)
        return self.title


@dataclass(slots=True)
class HostLocation:
    href: str

    def as_host_object(self) -> HostObject:
        location = HostObject()
        location.set("href", self.href)
        location.set("assign", HostCallable("location.assign", self._assign))
        return location

    def _assign(self, arguments: tuple[object, ...], this: object | None) -> object:
        self.href = js_to_string(arguments[0] if arguments else "")
        if isinstance(this, HostObject):
            this.set("href", self.href)
        return None


@dataclass(slots=True)
class HostHistory:
    entries: list[str] = field(default_factory=list)
    index: int = -1

    def as_host_object(self) -> HostObject:
        history = HostObject()
        history.set("pushState", HostCallable("history.pushState", self._push_state))
        history.set("back", HostCallable("history.back", self._back))
        history.set("length", float(max(len(self.entries), 0)))
        return history

    def _push_state(self, arguments: tuple[object, ...], this: object | None) -> object:
        url = js_to_string(arguments[2] if len(arguments) > 2 else "")
        del self.entries[self.index + 1 :]
        self.entries.append(url)
        self.index = len(self.entries) - 1
        if isinstance(this, HostObject):
            this.set("length", float(len(self.entries)))
        return None

    def _back(self, _arguments: tuple[object, ...], _this: object | None) -> object:
        if self.index > 0:
            self.index -= 1
            return self.entries[self.index]
        return None


@dataclass(slots=True)
class BrowserHostStubs:
    console: HostConsole = field(default_factory=HostConsole)
    timers: HostTimers = field(default_factory=HostTimers)
    document: HostDocument = field(default_factory=HostDocument)
    location: HostLocation = field(default_factory=lambda: HostLocation("https://example.test/"))
    history: HostHistory = field(default_factory=HostHistory)
    scheduler: ScriptScheduler | None = None

    def install(self, environment) -> None:
        environment.declare("console", self.console.as_host_object(), kind="const")
        for name, callable_value in self.timers.as_bindings().items():
            environment.declare(name, callable_value, kind="const")
        environment.declare("document", self.document.as_host_object(), kind="const")
        environment.declare("location", self.location.as_host_object(), kind="const")
        environment.declare("history", self.history.as_host_object(), kind="const")
