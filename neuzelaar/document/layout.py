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

from dataclasses import dataclass, replace

from neuzelaar.core.page import FrameAsset, ImageAsset
from neuzelaar.document.bfc import (
    BoxPlacement,
    ClipPopPlacement,
    ClipPushPlacement,
    FramePlacement,
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
    node_id: NodeId | None = None


@dataclass(frozen=True, slots=True)
class LayoutImage:
    x: int
    y: int
    width: int
    height: int
    label: str
    bitmap: ImageAsset | None
    node_id: NodeId | None = None


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
    frames: dict[NodeId, FrameAsset] | None = None,
    chrome: bool = True,
) -> LayoutResult:
    """Lay a document out into `width` x `height`.

    `chrome` is on for a top-level page: a 16px outer frame and the
    document `<title>` rendered above the content, both debug
    affordances rather than CSS. A nested browsing context gets neither
    — inside an iframe, the author's box is the whole viewport.
    """
    base_style = root_style or ComputedStyle()
    outer_margin = OUTER_MARGIN if chrome else 0
    viewport_width = max(width - outer_margin * 2, 120)
    viewport_height = max(height - outer_margin * 2, 120)

    items: list[LayoutItem] = []
    cursor_y = outer_margin
    if chrome and document.title:
        title_font_size = max(_font_size_px(base_style), 24)
        items.append(
            LayoutText(
                x=outer_margin,
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
            if isinstance(placement, FramePlacement):
                items.extend(
                    _layout_frame(
                        placement,
                        frames or {},
                        dx=outer_margin,
                        dy=cursor_y,
                    )
                )
                continue
            items.append(_to_layout_item(placement, dx=outer_margin, dy=cursor_y))
        content_height = bfc_height

    total_height = max(cursor_y + content_height + outer_margin, 64 if chrome else 0)
    # Preserve emission order so clip push / pop pairs stay paired and
    # background-before-content order from BFC is honoured.
    return LayoutResult(width=width, height=total_height, items=tuple(items))


def _layout_frame(
    placement: FramePlacement,
    frames: dict[NodeId, FrameAsset],
    *,
    dx: int,
    dy: int,
) -> list[LayoutItem]:
    """Lay a nested browsing context into the box its iframe reserved.

    The nested document is laid out at the frame's own size and its
    items are translated into the parent's coordinate space, wrapped in
    a clip so nothing escapes the frame box. This is where iframe
    recursion lives — `bfc` stops at the frame's edge.

    Node ids are stripped on the way out. They address nodes in the
    nested document, and the display builder resolves ids against the
    top-level one; letting them through would make a click inside a
    frame navigate the parent page, which is exactly the confused-deputy
    bug that nested contexts exist to prevent. Interaction inside a
    frame is its own slice.
    """
    x = placement.x + dx
    y = placement.y + dy
    asset = frames.get(placement.node_id) if placement.node_id is not None else None
    if asset is None or asset.result.handler_result.kind != "document":
        # Not loaded: blocked by policy, over budget, or not a document.
        return [
            LayoutImage(
                x=x,
                y=y,
                width=placement.width,
                height=placement.height,
                label=f"iframe: {placement.label}",
                bitmap=None,
            )
        ]

    nested = asset.result
    inner = layout_document(
        nested.handler_result.value,
        width=placement.width,
        height=placement.height,
        styles=nested.styles,
        images=nested.images,
        root_style=nested.root_style,
        frames=nested.frames,
        chrome=False,
    )
    items: list[LayoutItem] = [
        LayoutClipPush(x=x, y=y, width=placement.width, height=placement.height),
        # The nested page's canvas. A top-level page gets this from the
        # display builder's opening fill; a frame has to paint its own.
        LayoutBox(
            x=x,
            y=y,
            width=placement.width,
            height=placement.height,
            color=nested.root_style.background_color,
        ),
    ]
    items.extend(_translate_item(item, dx=x, dy=y) for item in inner.items)
    items.append(LayoutClipPop())
    return items


def _translate_item(item: LayoutItem, *, dx: int, dy: int) -> LayoutItem:
    if isinstance(item, LayoutText):
        return replace(item, x=item.x + dx, y=item.y + dy, node_id=None)
    if isinstance(item, LayoutImage):
        return replace(item, x=item.x + dx, y=item.y + dy, node_id=None)
    if isinstance(item, (LayoutBox, LayoutClipPush)):
        return replace(item, x=item.x + dx, y=item.y + dy)
    return item


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
            node_id=placement.node_id,
        )
    if isinstance(placement, ImagePlacement):
        return LayoutImage(
            x=placement.x + dx,
            y=placement.y + dy,
            width=placement.width,
            height=placement.height,
            label=placement.label,
            bitmap=placement.bitmap,
            node_id=placement.node_id,
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
