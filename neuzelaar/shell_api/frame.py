"""Renderer-neutral frame object exposed to shells."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PixelFormat(Enum):
    RGBA8888 = "rgba8888"


@dataclass(frozen=True, slots=True)
class Frame:
    width: int
    height: int
    format: PixelFormat
    pixels: bytes | memoryview
    stride: int
