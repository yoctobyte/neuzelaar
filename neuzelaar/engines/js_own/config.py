"""Runtime configuration for the standalone JS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


SCRIPT_BUDGET_MAX_STEPS_KEY = "script-budget-max_steps"
SCRIPT_BUDGET_MAX_MS_KEY = "script-budget-max_ms"
SCRIPT_DEBUG_TRACK_TASKS_KEY = "script-debug-track_tasks"
SCRIPT_DEBUG_KEEP_HISTORY_KEY = "script-debug-keep_history"
SCRIPT_DEBUG_MAX_HISTORY_KEY = "script-debug-max_history"


@dataclass(frozen=True, slots=True)
class ScriptRuntimeConfig:
    max_steps: int | None = None
    max_wall_ms: float | None = None
    debug_track_tasks: bool = False
    debug_keep_history: bool = False
    debug_max_history: int = 100

    @classmethod
    def from_settings(cls, settings: dict[str, object] | None) -> "ScriptRuntimeConfig":
        if settings is None:
            return cls()
        return cls(
            max_steps=_coerce_int(settings.get(SCRIPT_BUDGET_MAX_STEPS_KEY)),
            max_wall_ms=_coerce_float(settings.get(SCRIPT_BUDGET_MAX_MS_KEY)),
            debug_track_tasks=_coerce_bool(settings.get(SCRIPT_DEBUG_TRACK_TASKS_KEY), default=False),
            debug_keep_history=_coerce_bool(settings.get(SCRIPT_DEBUG_KEEP_HISTORY_KEY), default=False),
            debug_max_history=_coerce_int(
                settings.get(SCRIPT_DEBUG_MAX_HISTORY_KEY),
                default=100,
                minimum=0,
            )
            or 0,
        )

    def to_settings(self) -> dict[str, object]:
        return {
            SCRIPT_BUDGET_MAX_STEPS_KEY: self.max_steps,
            SCRIPT_BUDGET_MAX_MS_KEY: self.max_wall_ms,
            SCRIPT_DEBUG_TRACK_TASKS_KEY: self.debug_track_tasks,
            SCRIPT_DEBUG_KEEP_HISTORY_KEY: self.debug_keep_history,
            SCRIPT_DEBUG_MAX_HISTORY_KEY: self.debug_max_history,
        }


def _coerce_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_int(value: object, *, default: int | None = None, minimum: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and result < minimum:
        return minimum
    return result


def _coerce_float(value: object, *, default: float | None = None, minimum: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and result < minimum:
        return minimum
    return result
