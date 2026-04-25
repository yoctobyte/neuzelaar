"""Execution-budget tracking for the standalone JS interpreter."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import time
from typing import Iterator

from neuzelaar.engines.js_own.config import ScriptRuntimeConfig
from neuzelaar.engines.js_own.errors import JavaScriptExecutionLimitError


@dataclass(slots=True)
class ExecutionBudget:
    config: ScriptRuntimeConfig
    steps: int = 0
    started_at: float = 0.0

    def __post_init__(self) -> None:
        self.started_at = time.monotonic()

    def tick(self) -> None:
        self.steps += 1
        if self.config.max_steps is not None and self.steps > self.config.max_steps:
            raise JavaScriptExecutionLimitError(
                f"Script step budget exceeded ({self.config.max_steps})"
            )
        if self.config.max_wall_ms is not None:
            elapsed_ms = (time.monotonic() - self.started_at) * 1000.0
            if elapsed_ms > self.config.max_wall_ms:
                raise JavaScriptExecutionLimitError(
                    f"Script wall-clock budget exceeded ({self.config.max_wall_ms} ms)"
                )


_CURRENT_BUDGET: ContextVar[ExecutionBudget | None] = ContextVar("js_own_budget", default=None)


@contextmanager
def execution_budget(config: ScriptRuntimeConfig | None) -> Iterator[None]:
    token = _CURRENT_BUDGET.set(None if config is None else ExecutionBudget(config=config))
    try:
        yield
    finally:
        _CURRENT_BUDGET.reset(token)


def budget_tick() -> None:
    budget = _CURRENT_BUDGET.get()
    if budget is not None:
        budget.tick()

