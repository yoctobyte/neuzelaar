"""Runtime state for standalone JS execution."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Iterator

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.scheduler import (
    ScriptScheduler,
    ScriptTaskKind,
    ScriptTaskPriority,
)


MicrotaskCallback = Callable[[], None]


@dataclass(slots=True)
class PendingMicrotask:
    callback: MicrotaskCallback
    reason: str
    task_id: int | None = None


@dataclass(slots=True)
class ScriptRuntimeState:
    config: ScriptRuntimeConfig
    scheduler: ScriptScheduler | None = None
    microtasks: deque[PendingMicrotask] = field(default_factory=deque)

    def queue_microtask(self, callback: MicrotaskCallback, *, reason: str) -> None:
        task_id: int | None = None
        if self.scheduler is not None:
            task = self.scheduler.queue_task(
                kind=ScriptTaskKind.MICROTASK,
                priority=ScriptTaskPriority.FOREGROUND,
                reason=reason,
            )
            task_id = task.task_id
        self.microtasks.append(PendingMicrotask(callback=callback, reason=reason, task_id=task_id))

    def drain_microtasks(self) -> None:
        while self.microtasks:
            pending = self.microtasks.popleft()
            if self.scheduler is not None and pending.task_id is not None:
                started = self.scheduler.start_next()
                if started is not None and started.task_id != pending.task_id:
                    self.scheduler.yield_task(started.task_id, reason="out-of-order")
                    started = None
            try:
                pending.callback()
            except Exception as exc:
                if self.scheduler is not None and pending.task_id is not None:
                    self.scheduler.fail_task(pending.task_id, reason=f"{type(exc).__name__}: {exc}")
                raise
            else:
                if self.scheduler is not None and pending.task_id is not None:
                    self.scheduler.complete_task(pending.task_id, reason=pending.reason)


_CURRENT_RUNTIME_STATE: ContextVar[ScriptRuntimeState | None] = ContextVar(
    "js_own_runtime_state",
    default=None,
)


@contextmanager
def runtime_session(
    config: ScriptRuntimeConfig | None,
    *,
    scheduler: ScriptScheduler | None = None,
) -> Iterator[ScriptRuntimeState]:
    effective_config = config or ScriptRuntimeConfig()
    effective_scheduler = scheduler
    if effective_scheduler is None and effective_config.debug_track_tasks:
        effective_scheduler = ScriptScheduler(config=effective_config)
    state = ScriptRuntimeState(config=effective_config, scheduler=effective_scheduler)
    token = _CURRENT_RUNTIME_STATE.set(state)
    try:
        yield state
    finally:
        _CURRENT_RUNTIME_STATE.reset(token)


def current_runtime_state() -> ScriptRuntimeState | None:
    return _CURRENT_RUNTIME_STATE.get()
