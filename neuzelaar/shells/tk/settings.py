"""Persistent user preferences for the Tk viewer.

Kept intentionally small: a single JSON file at
~/.config/neuzelaar/settings.json with typed getters so callers do
not need to know the on-disk shape. Unknown or malformed values fall
back to defaults silently — settings are advisory, not critical.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ZOOM = 1.0
ALLOWED_ZOOM_LEVELS: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".config"
    return root / "neuzelaar" / "settings.json"


@dataclass(slots=True)
class Settings:
    zoom: float = DEFAULT_ZOOM

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        target = path or settings_path()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            return cls()
        zoom = data.get("zoom", DEFAULT_ZOOM)
        if not isinstance(zoom, (int, float)) or zoom <= 0:
            zoom = DEFAULT_ZOOM
        return cls(zoom=float(zoom))

    def save(self, path: Path | None = None) -> None:
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"zoom": self.zoom}, indent=2), encoding="utf-8")

    def nearest_allowed_zoom(self) -> float:
        return min(ALLOWED_ZOOM_LEVELS, key=lambda level: abs(level - self.zoom))
