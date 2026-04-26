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
    font_size: int
    font_weight: str = "normal"
    font_style: str = "normal"
    text_decoration: str = "none"
    max_width: int = 0
    align: str = "left"


@dataclass(frozen=True, slots=True)
class Placeholder:
    rect: Rect
    label: str


@dataclass(frozen=True, slots=True)
class Bitmap:
    width: int
    height: int
    stride: int
    pixels: bytes


@dataclass(frozen=True, slots=True)
class DrawImage:
    x: int
    y: int
    bitmap: Bitmap


@dataclass(frozen=True, slots=True)
class PushClip:
    rect: Rect


@dataclass(frozen=True, slots=True)
class PopClip:
    pass


DisplayOp = Union[FillRect, DrawText, Placeholder, DrawImage, PushClip, PopClip]


@dataclass(frozen=True, slots=True)
class DisplayList:
    width: int
    height: int
    ops: tuple[DisplayOp, ...]
