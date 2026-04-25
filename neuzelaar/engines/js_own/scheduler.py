"""Minimal scheduler/task model for standalone JS runtime planning."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
import time

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig


class ScriptTaskState(Enum):
    QUEUED = "queued"
    RUNNING = "running"
    YIELDED = "yielded"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScriptTaskSnapshot:
    task_id: int
    kind: str
    origin: str | None
    url: str | None
    state: str
    priority: str
    created_at: float
    last_started_at: float | None
    run_slices: int
    steps_used: int
    wall_ms_used: float
    budget_steps: int | None
    budget_ms: float | None
    reason: str | None
    metadata: dict[str, object]


@dataclass(slots=True)
class ScriptTask:
    task_id: int
    kind: str
    origin: str | None
    url: str | None
    priority: str
    created_at: float
    state: ScriptTaskState = ScriptTaskState.QUEUED
    last_started_at: float | None = None
    run_slices: int = 0
    steps_used: int = 0
    wall_ms_used: float = 0.0
    budget_steps: int | None = None
    budget_ms: float | None = None
    reason: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def snapshot(self) -> ScriptTaskSnapshot:
        return ScriptTaskSnapshot(
            task_id=self.task_id,
            kind=self.kind,
            origin=self.origin,
            url=self.url,
            state=self.state.value,
            priority=self.priority,
            created_at=self.created_at,
            last_started_at=self.last_started_at,
            run_slices=self.run_slices,
            steps_used=self.steps_used,
            wall_ms_used=self.wall_ms_used,
            budget_steps=self.budget_steps,
            budget_ms=self.budget_ms,
            reason=self.reason,
            metadata=dict(self.metadata),
        )


@dataclass(slots=True)
class ScriptScheduler:
    config: ScriptRuntimeConfig = field(default_factory=ScriptRuntimeConfig)
    _next_task_id: int = 1
    _queue: deque[int] = field(default_factory=deque)
    _tasks: dict[int, ScriptTask] = field(default_factory=dict)
    _history: deque[ScriptTaskSnapshot] = field(default_factory=deque)

    def queue_task(
        self,
        *,
        kind: str,
        origin: str | None = None,
        url: str | None = None,
        priority: str = "normal",
        reason: str | None = None,
        metadata: dict[str, object] | None = None,
        budget_steps: int | None = None,
        budget_ms: float | None = None,
    ) -> ScriptTask:
        task = ScriptTask(
            task_id=self._next_task_id,
            kind=kind,
            origin=origin,
            url=url,
            priority=priority,
            created_at=time.monotonic(),
            reason=reason,
            metadata={} if metadata is None else dict(metadata),
            budget_steps=budget_steps,
            budget_ms=budget_ms,
        )
        self._next_task_id += 1
        self._tasks[task.task_id] = task
        self._queue.append(task.task_id)
        return task

    def start_next(self) -> ScriptTask | None:
        if not self._queue:
            return None
        task = self._tasks[self._queue.popleft()]
        task.state = ScriptTaskState.RUNNING
        task.last_started_at = time.monotonic()
        task.run_slices += 1
        return task

    def yield_task(self, task_id: int, *, reason: str | None = None) -> ScriptTask:
        task = self._tasks[task_id]
        task.state = ScriptTaskState.YIELDED
        task.reason = reason
        self._queue.append(task_id)
        return task

    def complete_task(self, task_id: int, *, reason: str | None = None) -> ScriptTask:
        task = self._tasks[task_id]
        task.state = ScriptTaskState.COMPLETED
        task.reason = reason
        self._record_history(task)
        return task

    def fail_task(self, task_id: int, *, reason: str | None = None) -> ScriptTask:
        task = self._tasks[task_id]
        task.state = ScriptTaskState.FAILED
        task.reason = reason
        self._record_history(task)
        return task

    def cancel_task(self, task_id: int, *, reason: str | None = None) -> ScriptTask:
        task = self._tasks[task_id]
        task.state = ScriptTaskState.CANCELLED
        task.reason = reason
        self._queue = deque(candidate for candidate in self._queue if candidate != task_id)
        self._record_history(task)
        return task

    def note_progress(self, task_id: int, *, steps_used: int = 0, wall_ms_used: float = 0.0) -> ScriptTask:
        task = self._tasks[task_id]
        task.steps_used += steps_used
        task.wall_ms_used += wall_ms_used
        return task

    def snapshots(self) -> tuple[ScriptTaskSnapshot, ...]:
        return tuple(task.snapshot() for task in self._tasks.values())

    def history(self) -> tuple[ScriptTaskSnapshot, ...]:
        return tuple(self._history)

    def _record_history(self, task: ScriptTask) -> None:
        if not self.config.debug_track_tasks or not self.config.debug_keep_history:
            return
        self._history.append(task.snapshot())
        while len(self._history) > self.config.debug_max_history:
            self._history.popleft()
