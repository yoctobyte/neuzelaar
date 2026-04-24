"""Block Formatting Context — the block-layout algorithm.

Consumes a Box tree (document.box) and populates each box's
BoxGeometry in the CSS normal-flow coordinate system. Emits the
existing LayoutText / LayoutImage / LayoutBox primitives so the
display builder stays unchanged.

What's here (Commit A2):

- Block-level boxes stack vertically inside a Block Formatting
  Context. Each block's x/y/content_width/content_height are
  resolved through a proper box model (margin + border + padding
  around content box).
- width: explicit px or "auto". auto fills the containing block's
  available inline space, minus horizontal margins.
- height: explicit px or "auto". auto grows to fit block-level and
  inline content.
- Margin collapse between adjacent vertical block siblings: the
  larger of the two wins, the other contributes nothing.
- Inline-level and text children of a block (or of an anonymous
  block wrapper) are stacked one-per-line with approximate height
  from font-size * line-height, using the current style's color
  and text-align. Full line-box wrapping (true IFC) lands in
  Commit B.

Not here: %, auto-margin centering (margin: 0 auto), per-edge
longhand (margin-top etc.), borders (rendered as zero), floats,
positioning, overflow, IFC line boxes. All of these land in later
commits per docs/layout_plan.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from neuzelaar.core.page import ImageAsset
from neuzelaar.document.box import Box, BoxGeometry, BoxKind, EdgeSizes
from neuzelaar.document.dom import NodeId
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.core.watchdog import check_resources


@dataclass(frozen=True, slots=True)
class ImagePlacement:
    """Where an image shows up. Mirrors document.layout.LayoutImage but
    decoupled to avoid a circular import.
    """

    x: int
    y: int
    width: int
    height: int
    label: str
    bitmap: ImageAsset | None


@dataclass(frozen=True, slots=True)
class TextPlacement:
    x: int
    y: int
    text: str
    color: str
    font_size: int
    max_width: int
    text_align: str


@dataclass(frozen=True, slots=True)
class BoxPlacement:
    x: int
    y: int
    width: int
    height: int
    color: str


Placement = TextPlacement | ImagePlacement | BoxPlacement


@dataclass(slots=True)
class LayoutState:
    viewport_width: int
    images: dict[NodeId, ImageAsset]
    items: list[Placement]
    budget_exceeded: bool = False


# Safety cap: stop emitting layout items after this many to prevent
# runaway computation on huge DOMs.
MAX_LAYOUT_ITEMS = 10_000


def layout_block(
    root: Box,
    *,
    viewport_width: int,
    images: dict[NodeId, ImageAsset] | None = None,
) -> tuple[int, list[Placement]]:
    """Lay out a root block box at viewport_width and return the
    total content height plus the flat placement list.
    """
    check_resources()
    state = LayoutState(
        viewport_width=viewport_width,
        images=images or {},
        items=[],
    )
    # The root sits at the viewport origin (0, 0). The containing
    # block width used for resolving the root's width is the whole
    # viewport.
    _place_block(root, state, x=0, y=0, containing_width=viewport_width)
    total_height = root.geometry.y + root.geometry.border_box_height + root.geometry.margin.bottom
    return total_height, state.items



def _place_block(box: Box, state: LayoutState, *, x: int, y: int, containing_width: int) -> int:
    """Resolve geometry and emit placements for a block-level box.
    Returns the bottom margin edge y-coordinate."""
    style = box.style
    margin = _resolve_margin(style)
    padding = _resolve_padding(style)
    border = EdgeSizes()  # borders not yet supported

    box.geometry.margin = margin
    box.geometry.padding = padding
    box.geometry.border = border

    content_width = _resolve_width(style, containing_width, margin, padding, border)
    box.geometry.content_width = content_width

    # Top-left of the border box.
    box.geometry.x = x + margin.left
    box.geometry.y = y + margin.top

    # Emit the background rect before children so painters see it
    # beneath them. We emit only when a non-default background exists.
    _maybe_emit_background(box, state)

    child_x = box.geometry.x + border.left + padding.left
    child_y = box.geometry.y + border.top + padding.top
    inner_width = content_width

    cursor_y = child_y
    if box.children and all(child.is_inline_level for child in box.children):
        # Pure inline formatting context: lay out all children as a
        # single run of line boxes with proper word wrapping.
        cursor_y = _layout_inline_context(
            box.children,
            state,
            x0=child_x,
            y0=child_y,
            content_width=inner_width,
            parent_style=style,
        )
    else:
        previous_margin_bottom = 0  # for sibling margin collapse
        for child in box.children:
            if state.budget_exceeded or len(state.items) >= MAX_LAYOUT_ITEMS:
                state.budget_exceeded = True
                break
            if child.is_block_level:
                # Collapse this child's top margin with the previous
                # sibling's bottom margin (or with the parent's top
                # edge if this is the first block child).
                child_margin_top = _resolve_margin(child.style).top
                collapse = max(previous_margin_bottom, child_margin_top)
                if cursor_y == child_y:
                    collapse = 0
                cursor_y = cursor_y - previous_margin_bottom + collapse - child_margin_top
                cursor_y = _place_block(child, state, x=child_x, y=cursor_y, containing_width=inner_width)
                previous_margin_bottom = _resolve_margin(child.style).bottom
            else:
                # Inline child appearing alongside blocks — should
                # have been wrapped in an anonymous block during box
                # tree construction. Fall back to the proto-IFC path
                # for safety.
                cursor_y = _place_inline_or_text(
                    child, state, x=child_x, y=cursor_y,
                    content_width=inner_width, parent_style=style,
                )
                previous_margin_bottom = 0

    used_content_height = max(cursor_y - child_y, 0)
    content_height = _resolve_height(style, used_content_height)
    box.geometry.content_height = content_height

    box_bottom = box.geometry.y + border.top + padding.top + content_height + padding.bottom + border.bottom
    return box_bottom + margin.bottom


@dataclass(frozen=True, slots=True)
class _InlineFragment:
    """A single atomic unit inside an IFC — either a word or a
    replaced element. Boundaries between inline boxes are not
    materialised; styles travel on each fragment so the rasterizer
    can still apply per-inline color / weight / size.
    """

    kind: str  # "word" or "image"
    text: str = ""
    style: ComputedStyle | None = None
    width: int = 0
    height: int = 0
    label: str = ""
    bitmap: ImageAsset | None = None


def _flatten_inline(
    children: list[Box],
    style: ComputedStyle,
    state: LayoutState,
) -> list[_InlineFragment]:
    fragments: list[_InlineFragment] = []
    for child in children:
        if child.kind == BoxKind.TEXT:
            text = child.text or ""
            for word in text.split():
                fragments.append(_InlineFragment(kind="word", text=word, style=style))
        elif child.kind == BoxKind.INLINE:
            # Recurse with the inline element's own computed style so
            # nested <strong><em>word</em></strong> picks up the inner
            # style for "word".
            fragments.extend(_flatten_inline(child.children, child.style, state))
        elif child.kind == BoxKind.REPLACED and child.tag == "img":
            asset = state.images.get(child.node_id) if child.node_id is not None else None
            attr_width = _attr_int(child.element.attr("width") if child.element is not None else None)
            attr_height = _attr_int(child.element.attr("height") if child.element is not None else None)
            if asset is not None:
                intrinsic_w = asset.bitmap.width
                intrinsic_h = asset.bitmap.height
            else:
                intrinsic_w, intrinsic_h = 240, 32
            width = attr_width or intrinsic_w
            height = attr_height or intrinsic_h
            label = (
                (child.element.attr("alt") if child.element is not None else None)
                or (child.element.attr("src") if child.element is not None else None)
                or "image"
            )
            fragments.append(
                _InlineFragment(
                    kind="image",
                    width=width,
                    height=height,
                    label=label,
                    bitmap=asset,
                    style=style,
                )
            )
    return fragments


def _layout_inline_context(
    children: list[Box],
    state: LayoutState,
    *,
    x0: int,
    y0: int,
    content_width: int,
    parent_style: ComputedStyle,
) -> int:
    """Lay out a sequence of inline-level children as a Block's
    Inline Formatting Context. Greedy word-wrap at content_width.
    Returns the y coordinate at the bottom of the last line box.
    """
    fragments = _flatten_inline(list(children), parent_style, state)
    if not fragments:
        return y0

    # A line-under-construction.
    line_items: list[tuple[int, _InlineFragment]] = []
    cursor_x = x0
    cursor_y = y0
    line_max_height = 0
    line_max_font_size = 0

    def flush_line(force: bool = False) -> None:
        nonlocal cursor_x, cursor_y, line_items, line_max_height, line_max_font_size
        if not line_items:
            if force:
                cursor_y += _line_height(line_max_font_size or _font_size_px(parent_style))
                line_max_height = 0
                line_max_font_size = 0
            return
        line_box_height = max(line_max_height, _line_height(line_max_font_size or _font_size_px(parent_style)))
        # Baseline-align text / image fragments to the bottom of the
        # line box. Simple alphabetic baseline approximation: smaller
        # fonts lift up so their bottoms align with the tallest.
        for x, fragment in line_items:
            if len(state.items) >= MAX_LAYOUT_ITEMS:
                state.budget_exceeded = True
                break
            if fragment.kind == "word":
                fs = _font_size_px(fragment.style)
                offset = line_box_height - max(int(round(fs * 1.3)), 10)
                state.items.append(
                    TextPlacement(
                        x=x,
                        y=cursor_y + max(offset, 0),
                        text=fragment.text,
                        color=(fragment.style or parent_style).color,
                        font_size=fs,
                        max_width=content_width,
                        text_align=(fragment.style or parent_style).text_align,
                    )
                )
            else:
                offset = max(line_box_height - fragment.height, 0)
                state.items.append(
                    ImagePlacement(
                        x=x,
                        y=cursor_y + offset,
                        width=fragment.width,
                        height=fragment.height,
                        label=fragment.label,
                        bitmap=fragment.bitmap,
                    )
                )
        cursor_y += line_box_height
        cursor_x = x0
        line_items = []
        line_max_height = 0
        line_max_font_size = 0

    for fragment in fragments:
        if state.budget_exceeded or len(state.items) >= MAX_LAYOUT_ITEMS:
            state.budget_exceeded = True
            return cursor_y
        if fragment.kind == "word":
            fs = _font_size_px(fragment.style)
            word_width = _measure_text(fragment.text, fs)
            space_width = _measure_text(" ", fs) if line_items else 0
            # Wrap if this word would overflow. Always place at least
            # one fragment on an empty line, even if oversized.
            if cursor_x + space_width + word_width > x0 + content_width and line_items:
                flush_line()
                space_width = 0
            if space_width:
                cursor_x += space_width
            line_items.append((cursor_x, fragment))
            cursor_x += word_width
            line_max_font_size = max(line_max_font_size, fs)
            line_max_height = max(line_max_height, _line_height(fs))
        else:  # image
            if cursor_x + fragment.width > x0 + content_width and line_items:
                flush_line()
            line_items.append((cursor_x, fragment))
            cursor_x += fragment.width
            line_max_height = max(line_max_height, fragment.height)
    flush_line()
    return cursor_y


def _measure_text(text: str, font_size: int) -> int:
    """Approximate the pixel width of text at the given font size.

    Uses a coefficient calibrated for DejaVuSans at common sizes. The
    rasterizer can still render crisply since it does real glyph
    measurement; this is only used to decide where line boxes break.
    """
    if not text:
        return 0
    return int(round(len(text) * font_size * 0.55))


def _place_inline_or_text(
    box: Box,
    state: LayoutState,
    *,
    x: int,
    y: int,
    content_width: int,
    parent_style: ComputedStyle,
) -> int:
    """Proto-IFC fallback for inline children that somehow appeared
    alongside block siblings without being wrapped in an anonymous
    block. Should rarely fire in practice — the box tree constructor
    wraps inline runs — but kept for defence in depth.
    """
    style = box.style if box.kind != BoxKind.TEXT else parent_style
    if state.budget_exceeded or len(state.items) >= MAX_LAYOUT_ITEMS:
        state.budget_exceeded = True
        return y
    if box.kind == BoxKind.TEXT:
        text = box.text or ""
        if not text.strip():
            return y
        font_size = _font_size_px(style)
        state.items.append(
            TextPlacement(
                x=x,
                y=y,
                text=text,
                color=style.color,
                font_size=font_size,
                max_width=content_width,
                text_align=style.text_align,
            )
        )
        return y + _line_height(font_size)

    if box.kind == BoxKind.REPLACED and box.tag == "img":
        label = (box.element.attr("alt") if box.element is not None else None) or (
            box.element.attr("src") if box.element is not None else None
        ) or "image"
        attr_width = _attr_int(box.element.attr("width") if box.element is not None else None)
        attr_height = _attr_int(box.element.attr("height") if box.element is not None else None)
        asset = state.images.get(box.node_id) if box.node_id is not None else None
        if asset is not None:
            intrinsic_w = asset.bitmap.width
            intrinsic_h = asset.bitmap.height
        else:
            intrinsic_w, intrinsic_h = 240, 32
        width = attr_width or intrinsic_w
        height = attr_height or intrinsic_h
        state.items.append(
            ImagePlacement(x=x, y=y, width=width, height=height, label=label, bitmap=asset)
        )
        return y + height + 12

    if box.kind == BoxKind.INLINE:
        # Proto-IFC: emit each inline child on its own line using the
        # inline element's own style so color/weight/size flow through.
        cursor = y
        for child in box.children:
            cursor = _place_inline_or_text(
                child,
                state,
                x=x,
                y=cursor,
                content_width=content_width,
                parent_style=style,
            )
        return cursor

    if box.kind == BoxKind.ANONYMOUS_BLOCK:
        # An anonymous block wraps inline-level siblings that coexisted
        # with block siblings. Lay out each child as-if inline.
        cursor = y
        for child in box.children:
            cursor = _place_inline_or_text(
                child,
                state,
                x=x,
                y=cursor,
                content_width=content_width,
                parent_style=parent_style,
            )
        return cursor

    return y


def _maybe_emit_background(box: Box, state: LayoutState) -> None:
    color = box.style.background_color
    if not color or color == "#ffffff":
        return
    # Background fills the border box; we render only the padding box
    # for now since borders are zero anyway.
    geom = box.geometry
    x = geom.x + geom.border.left
    y = geom.y + geom.border.top
    width = geom.padding.left + geom.content_width + geom.padding.right
    # Height isn't known yet at emission time; we use a zero-height
    # placeholder and patch it when layout finishes. Simpler path:
    # re-emit after layout completes. For Commit A2 we defer the
    # background rect until after children are placed by rewriting
    # the items list below via a post-pass.
    # To avoid ordering issues, we record a marker and resolve later.
    state.items.append(
        BoxPlacement(x=x, y=y, width=width, height=_BACKGROUND_PLACEHOLDER, color=color)
    )


_BACKGROUND_PLACEHOLDER = -1  # height sentinel for post-pass resolution


def finalize_backgrounds(root: Box, items: list[Placement]) -> list[Placement]:
    """Patch placeholder background heights now that all geometry is
    resolved. Walks the box tree once to match placeholders to their
    owning box by x/y.
    """
    # Build a lookup of (x, y) → height for every box that has a
    # background to render.
    heights: dict[tuple[int, int], int] = {}
    for box in _walk(root):
        if not box.is_block_level:
            continue
        color = box.style.background_color
        if not color or color == "#ffffff":
            continue
        geom = box.geometry
        x = geom.x + geom.border.left
        y = geom.y + geom.border.top
        height = geom.padding.top + geom.content_height + geom.padding.bottom
        heights[(x, y)] = height

    resolved: list[Placement] = []
    for item in items:
        if isinstance(item, BoxPlacement) and item.height == _BACKGROUND_PLACEHOLDER:
            height = heights.get((item.x, item.y), 0)
            if height <= 0:
                continue
            resolved.append(BoxPlacement(x=item.x, y=item.y, width=item.width, height=height, color=item.color))
        else:
            resolved.append(item)
    return resolved


def _walk(box: Box):
    yield box
    for child in box.children:
        yield from _walk(child)


def _resolve_margin(style: ComputedStyle) -> EdgeSizes:
    top, right, bottom, left = _expand_shorthand(style.margin)
    return EdgeSizes(top=top, right=right, bottom=bottom, left=left)


def _resolve_padding(style: ComputedStyle) -> EdgeSizes:
    top, right, bottom, left = _expand_shorthand(style.padding)
    return EdgeSizes(top=top, right=right, bottom=bottom, left=left)


def _expand_shorthand(value: str) -> tuple[int, int, int, int]:
    tokens = value.strip().split()
    if not tokens:
        return (0, 0, 0, 0)
    nums = [_length_to_px(token) for token in tokens]
    if len(nums) == 1:
        v = nums[0]
        return (v, v, v, v)
    if len(nums) == 2:
        t, h = nums
        return (t, h, t, h)
    if len(nums) == 3:
        t, h, b = nums
        return (t, h, b, h)
    return (nums[0], nums[1], nums[2], nums[3])


def _resolve_width(
    style: ComputedStyle,
    containing_width: int,
    margin: EdgeSizes,
    padding: EdgeSizes,
    border: EdgeSizes,
) -> int:
    available = containing_width - margin.left - margin.right - border.left - border.right - padding.left - padding.right
    width_value = style.width.strip().lower()
    if width_value and width_value != "auto":
        explicit = _length_to_px(width_value)
        if explicit > 0:
            return explicit
    return max(available, 0)


def _resolve_height(style: ComputedStyle, used_content_height: int) -> int:
    height_value = style.height.strip().lower()
    if height_value and height_value != "auto":
        explicit = _length_to_px(height_value)
        if explicit > 0:
            return explicit
    return used_content_height


def _length_to_px(value: str) -> int:
    text = value.strip().lower()
    if not text or text == "auto":
        return 0
    if text.endswith("px"):
        text = text[:-2]
    try:
        return max(int(round(float(text))), 0)
    except ValueError:
        return 0


def _attr_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return max(int(value), 1)
    except ValueError:
        return None


def _font_size_px(style: ComputedStyle) -> int:
    text = style.font_size.strip()
    if text.endswith("px"):
        try:
            return max(int(round(float(text[:-2]))), 1)
        except ValueError:
            pass
    return 16


def _line_height(font_size: int) -> int:
    return max(int(round(font_size * 1.3)), 10)
