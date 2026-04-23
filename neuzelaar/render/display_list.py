"""Backend-neutral display list operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Color:
    r: int
    g: int
    b: int
    a: int = 255


@dataclass(frozen=True, slots=True)
class FillRect:
    rect: Rect
    color: Color


@dataclass(frozen=True, slots=True)
class DrawText:
    x: int
    y: int
    text: str
    color: Color


@dataclass(frozen=True, slots=True)
class Placeholder:
    rect: Rect
    label: str


DisplayOp = Union[FillRect, DrawText, Placeholder]


@dataclass(frozen=True, slots=True)
class DisplayList:
    width: int
    height: int
    ops: tuple[DisplayOp, ...]
