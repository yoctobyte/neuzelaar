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
    tasks_run: int
    microtasks_run: int
    timers_run: int
    elapsed_ms: float
    last_task_kind: str | None
    last_task_id: int | None
    last_reason: str | None
    still_pending: bool


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

    def step(
        self,
        *,
        timeout_ms: float | None = None,
        max_tasks: int | None = 1,
        until_idle: bool = False,
    ) -> EventLoopStepResult:
        started_at = time.monotonic()
        tasks_run = 0
        microtasks_run = 0
        timers_run = 0
        last_task_kind: str | None = None
        last_task_id: int | None = None
        last_reason: str | None = None

        while True:
            if max_tasks is not None and tasks_run >= max_tasks:
                break
            if timeout_ms is not None and ((time.monotonic() - started_at) * 1000.0) >= timeout_ms:
                break
            next_ready = self._pop_next_ready_task()
            if next_ready is None:
                break
            task_kind, callback, task_id, reason = next_ready
            self._run_task_callback(callback, task_id=task_id, reason=reason)
            tasks_run += 1
            if task_kind == ScriptTaskKind.MICROTASK.value:
                microtasks_run += 1
            elif task_kind == ScriptTaskKind.TIMER.value:
                timers_run += 1
            last_task_kind = task_kind
            last_task_id = task_id
            last_reason = reason
            if not until_idle:
                break

        return EventLoopStepResult(
            progressed=tasks_run > 0,
            tasks_run=tasks_run,
            microtasks_run=microtasks_run,
            timers_run=timers_run,
            elapsed_ms=(time.monotonic() - started_at) * 1000.0,
            last_task_kind=last_task_kind,
            last_task_id=last_task_id,
            last_reason=last_reason,
            still_pending=self.has_pending_work(),
        )

    def run_until_idle(self, *, max_tasks: int | None = None) -> int:
        result = self.step(until_idle=True, max_tasks=max_tasks)
        return result.tasks_run

    def has_pending_work(self) -> bool:
        return bool(self.microtasks or any(not timer.cancelled for timer in self.timers))

    def has_ready_work(self) -> bool:
        if self.microtasks:
            return True
        self._prune_cancelled_timers()
        now = time.monotonic()
        return any(timer.due_at <= now for timer in self.timers)

    def _pop_next_ready_task(self) -> tuple[str, Callable[[], None], int | None, str] | None:
        if self.microtasks:
            pending = self.microtasks.popleft()
            return (ScriptTaskKind.MICROTASK.value, pending.callback, pending.task_id, pending.reason)
        due_timer = self._pop_due_timer()
        if due_timer is not None:
            return (ScriptTaskKind.TIMER.value, due_timer.callback, due_timer.task_id, due_timer.reason)
        return None

    def _pop_due_timer(self) -> PendingTimer | None:
        self._prune_cancelled_timers()
        if not self.timers:
            return None
        now = time.monotonic()
        self.timers.sort(key=lambda timer: timer.due_at)
        for index, pending in enumerate(self.timers):
            if pending.due_at <= now:
                return self.timers.pop(index)
        return None

    def _prune_cancelled_timers(self) -> None:
        if self.timers:
            self.timers = [timer for timer in self.timers if not timer.cancelled]

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
