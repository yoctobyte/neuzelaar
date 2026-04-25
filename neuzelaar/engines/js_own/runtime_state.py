"""Runtime state for standalone JS execution."""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import time
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


TimerCallback = Callable[[], None]


@dataclass(slots=True)
class PendingTimer:
    callback: TimerCallback
    reason: str
    timer_id: int
    due_at: float
    task_id: int | None = None
    cancelled: bool = False


@dataclass(frozen=True, slots=True)
class EventLoopStepResult:
    progressed: bool
    task_kind: str | None
    task_id: int | None
    reason: str | None


@dataclass(slots=True)
class ScriptRuntimeState:
    config: ScriptRuntimeConfig
    scheduler: ScriptScheduler | None = None
    microtasks: deque[PendingMicrotask] = field(default_factory=deque)
    timers: list[PendingTimer] = field(default_factory=list)

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

    def queue_timer(
        self,
        callback: TimerCallback,
        *,
        timer_id: int,
        delay_ms: float,
        reason: str,
        origin: str | None = None,
        url: str | None = None,
    ) -> None:
        task_id: int | None = None
        if self.scheduler is not None:
            task = self.scheduler.queue_task(
                kind=ScriptTaskKind.TIMER,
                origin=origin,
                url=url,
                priority=ScriptTaskPriority.BACKGROUND,
                reason=reason,
                metadata={
                    "timer_id": timer_id,
                    "delay": delay_ms,
                },
            )
            task_id = task.task_id
        self.timers.append(
            PendingTimer(
                callback=callback,
                reason=reason,
                timer_id=timer_id,
                due_at=time.monotonic() + (delay_ms / 1000.0),
                task_id=task_id,
            )
        )

    def cancel_timer(self, timer_id: int) -> None:
        for pending in self.timers:
            if pending.timer_id == timer_id and not pending.cancelled:
                pending.cancelled = True
                if self.scheduler is not None and pending.task_id is not None:
                    self.scheduler.cancel_task(pending.task_id, reason="clearTimeout")
                break

    def step(self) -> EventLoopStepResult:
        if self.microtasks:
            pending = self.microtasks.popleft()
            self._run_task_callback(
                pending.callback,
                task_id=pending.task_id,
                reason=pending.reason,
            )
            return EventLoopStepResult(
                progressed=True,
                task_kind=ScriptTaskKind.MICROTASK.value,
                task_id=pending.task_id,
                reason=pending.reason,
            )
        due_timer = self._pop_due_timer()
        if due_timer is not None:
            self._run_task_callback(
                due_timer.callback,
                task_id=due_timer.task_id,
                reason=due_timer.reason,
            )
            return EventLoopStepResult(
                progressed=True,
                task_kind=ScriptTaskKind.TIMER.value,
                task_id=due_timer.task_id,
                reason=due_timer.reason,
            )
        return EventLoopStepResult(progressed=False, task_kind=None, task_id=None, reason=None)

    def run_until_idle(self) -> int:
        steps = 0
        while True:
            result = self.step()
            if not result.progressed:
                break
            steps += 1
        return steps

    def has_pending_work(self) -> bool:
        return bool(self.microtasks or any(not timer.cancelled for timer in self.timers))

    def _pop_due_timer(self) -> PendingTimer | None:
        if not self.timers:
            return None
        now = time.monotonic()
        self.timers.sort(key=lambda timer: timer.due_at)
        for index, pending in enumerate(self.timers):
            if pending.cancelled:
                self.timers.pop(index)
                return self._pop_due_timer()
            if pending.due_at <= now:
                return self.timers.pop(index)
        return None

    def _run_task_callback(self, callback: Callable[[], None], *, task_id: int | None, reason: str) -> None:
        if self.scheduler is not None and task_id is not None:
            started = self.scheduler.start_next()
            if started is not None and started.task_id != task_id:
                self.scheduler.yield_task(started.task_id, reason="out-of-order")
        try:
            callback()
        except Exception as exc:
            if self.scheduler is not None and task_id is not None:
                self.scheduler.fail_task(task_id, reason=f"{type(exc).__name__}: {exc}")
            raise
        else:
            if self.scheduler is not None and task_id is not None:
                self.scheduler.complete_task(task_id, reason=reason)

    def drain_microtasks(self) -> None:
        while self.microtasks:
            result = self.step()
            if not result.progressed:
                break


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
