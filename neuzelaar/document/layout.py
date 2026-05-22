"""Visual layout: document + styles -> positioned primitives.

The layout is produced in two steps:

1. `build_box_tree` converts DOM + computed styles into a box tree.
2. `bfc.layout_block` walks that tree and populates geometry for
   every box, emitting TextPlacement / ImagePlacement / BoxPlacement
   records.

This module is the thin boundary that translates the box-tree
placements into the LayoutText / LayoutImage / LayoutBox primitives
the display builder consumes. A small 16px outer frame is applied
around the rendered document, and the document `<title>` (if any)
is rendered at the top for headless / debug utility.
"""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.page import ImageAsset
from neuzelaar.document.bfc import (
    BoxPlacement,
    ClipPopPlacement,
    ClipPushPlacement,
    ImagePlacement,
    TextPlacement,
    finalize_backgrounds,
    layout_block,
)
from neuzelaar.document.box import build_box_tree
from neuzelaar.document.dom import Document, NodeId
from neuzelaar.document.styles import ComputedStyle


OUTER_MARGIN = 16
TITLE_ADVANCE = 28


@dataclass(frozen=True, slots=True)
class LayoutText:
    x: int
    y: int
    text: str
    color: str
    font_size: int
    font_weight: str = "normal"
    font_style: str = "normal"
    text_decoration: str = "none"
    max_width: int = 0
    text_align: str = "left"


@dataclass(frozen=True, slots=True)
class LayoutImage:
    x: int
    y: int
    width: int
    height: int
    label: str
    bitmap: ImageAsset | None


@dataclass(frozen=True, slots=True)
class LayoutBox:
    x: int
    y: int
    width: int
    height: int
    color: str


@dataclass(frozen=True, slots=True)
class LayoutClipPush:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class LayoutClipPop:
    pass


LayoutItem = LayoutText | LayoutImage | LayoutBox | LayoutClipPush | LayoutClipPop


@dataclass(frozen=True, slots=True)
class LayoutResult:
    width: int
    height: int
    items: tuple[LayoutItem, ...]


def layout_document(
    document: Document,
    *,
    width: int = 800,
    height: int = 600,
    styles: dict[NodeId, ComputedStyle] | None = None,
    images: dict[NodeId, ImageAsset] | None = None,
    root_style: ComputedStyle | None = None,
) -> LayoutResult:
    base_style = root_style or ComputedStyle()
    viewport_width = max(width - OUTER_MARGIN * 2, 120)
    viewport_height = max(height - OUTER_MARGIN * 2, 120)

    items: list[LayoutItem] = []
    cursor_y = OUTER_MARGIN
    if document.title:
        title_font_size = max(_font_size_px(base_style), 24)
        items.append(
            LayoutText(
                x=OUTER_MARGIN,
                y=cursor_y,
                text=document.title,
                color=base_style.color,
                font_size=title_font_size,
                font_weight=base_style.font_weight,
                font_style=base_style.font_style,
                text_decoration=base_style.text_decoration,
                max_width=viewport_width,
                text_align=base_style.text_align,
            )
        )
        cursor_y += TITLE_ADVANCE

    content_height = 0
    root_box = build_box_tree(document, styles or {})
    if root_box is not None:
        bfc_height, placements = layout_block(
            root_box,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            images=images or {},
        )
        placements = finalize_backgrounds(root_box, placements)
        for placement in placements:
            items.append(_to_layout_item(placement, dx=OUTER_MARGIN, dy=cursor_y))
        content_height = bfc_height

    total_height = max(cursor_y + content_height + OUTER_MARGIN, 64)
    # Preserve emission order so clip push / pop pairs stay paired and
    # background-before-content order from BFC is honoured.
    return LayoutResult(width=width, height=total_height, items=tuple(items))


def _to_layout_item(placement, *, dx: int, dy: int) -> LayoutItem:
    if isinstance(placement, TextPlacement):
        return LayoutText(
            x=placement.x + dx,
            y=placement.y + dy,
            text=placement.text,
            color=placement.color,
            font_size=placement.font_size,
            font_weight=placement.font_weight,
            font_style=placement.font_style,
            text_decoration=placement.text_decoration,
            max_width=placement.max_width,
            text_align=placement.text_align,
        )
    if isinstance(placement, ImagePlacement):
        return LayoutImage(
            x=placement.x + dx,
            y=placement.y + dy,
            width=placement.width,
            height=placement.height,
            label=placement.label,
            bitmap=placement.bitmap,
        )
    if isinstance(placement, BoxPlacement):
        return LayoutBox(
            x=placement.x + dx,
            y=placement.y + dy,
            width=placement.width,
            height=placement.height,
            color=placement.color,
        )
    if isinstance(placement, ClipPushPlacement):
        return LayoutClipPush(
            x=placement.x + dx,
            y=placement.y + dy,
            width=placement.width,
            height=placement.height,
        )
    if isinstance(placement, ClipPopPlacement):
        return LayoutClipPop()
    raise TypeError(f"Unknown placement type: {type(placement).__name__}")


def _sort_backgrounds_behind(items: list[LayoutItem]) -> list[LayoutItem]:
    """Background rects must render before overlapping text/images so
    the painter order is correct. BFC emits backgrounds as it enters
    a block, so they already precede their children in document order;
    this function is a safety net for cases where the title is
    inserted before BFC output.
    """
    boxes = [item for item in items if isinstance(item, LayoutBox)]
    others = [item for item in items if not isinstance(item, LayoutBox)]
    return boxes + others


def _font_size_px(style: ComputedStyle) -> int:
    value = style.font_size.strip()
    if value.endswith("px"):
        try:
            return max(int(round(float(value[:-2]))), 1)
        except ValueError:
            pass
    return 16
