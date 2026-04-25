"""Runtime configuration for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScriptRuntimeConfig:
    max_steps: int | None = None
    max_wall_ms: float | None = None
    debug_track_tasks: bool = False
    debug_keep_history: bool = False
    debug_max_history: int = 100
