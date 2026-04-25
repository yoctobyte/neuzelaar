"""Runtime configuration for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScriptRuntimeConfig:
    max_steps: int | None = None
    max_wall_ms: float | None = None

