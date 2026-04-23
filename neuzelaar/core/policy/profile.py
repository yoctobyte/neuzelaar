"""User-visible policy profiles."""

from __future__ import annotations

from enum import Enum


class PolicyProfile(Enum):
    STRICT = "strict"
    BALANCED = "balanced"
    COMPATIBILITY = "compatibility"
