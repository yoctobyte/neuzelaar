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

from dataclasses import dataclass, field

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
    font_weight: str
    font_style: str
    text_decoration: str
    max_width: int
    text_align: str


@dataclass(frozen=True, slots=True)
class BoxPlacement:
    x: int
    y: int
    width: int
    height: int
    color: str
    node_id: NodeId | None = None


@dataclass(frozen=True, slots=True)
class ClipPushPlacement:
    """Begin a clipping region. All subsequent placements (until the
    matching ClipPopPlacement) are constrained to the rectangle. The
    rectangle is the box's padding edge; box-shadows, outlines, and
    overflow:visible content are not yet handled.
    """

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ClipPopPlacement:
    """End the most recently pushed clipping region."""


Placement = (
    TextPlacement | ImagePlacement | BoxPlacement | ClipPushPlacement | ClipPopPlacement
)


@dataclass(slots=True)
class FloatExclusion:
    """An active floated box's contribution to the float context.

    A float on the left occupies x in [bfc_left, edge_x); a float on
    the right occupies x in [edge_x, bfc_right). Vertical extent is
    [top, bottom). Inline content laid out at any y in that range
    must avoid the occupied side.
    """

    side: str  # "left" or "right"
    top: int
    bottom: int
    edge_x: int


@dataclass(slots=True)
class FloatContext:
    """List of active floats inside a Block Formatting Context.
    Queried by both block placement (for shifting in-flow blocks)
    and inline placement (for narrowing line boxes).
    """

    exclusions: list[FloatExclusion] = field(default_factory=list)

    def constrain(
        self,
        y: int,
        height: int,
        content_left: int,
        content_right: int,
    ) -> tuple[int, int]:
        """Return (adjusted_left, adjusted_right) at the given vertical
        range, narrowing around any floats that overlap.
        """
        left = content_left
        right = content_right
        for ex in self.exclusions:
            if ex.bottom <= y or ex.top >= y + max(height, 1):
                continue
            if ex.side == "left":
                left = max(left, ex.edge_x)
            else:
                right = min(right, ex.edge_x)
        return left, right

    def lowest(self, side: str | None = None) -> int:
        """y of the lowest active float bottom, optionally filtered by
        side. Used to implement `clear`.
        """
        result = 0
        for ex in self.exclusions:
            if side is None or side == ex.side:
                result = max(result, ex.bottom)
        return result


@dataclass(slots=True)
class _ContainingBlock:
    """Snapshot of a positioned ancestor's content edge. Used as the
    containing block for absolute children; viewport for fixed.
    """

    x: int
    y: int
    width: int


@dataclass(slots=True)
class _DeferredAbsolute:
    """An absolute/fixed box queued during the main layout pass and
    placed once its containing block is fully resolved.
    """

    box: Box
    containing_block: _ContainingBlock
    is_fixed: bool


@dataclass(slots=True)
class LayoutState:
    viewport_width: int
    images: dict[NodeId, ImageAsset]
    items: list[Placement]
    floats: FloatContext = field(default_factory=FloatContext)
    budget_exceeded: bool = False
    # Stack of positioned ancestors (innermost last). Each entry is
    # the containing block established by that ancestor.
    cb_stack: list[_ContainingBlock] = field(default_factory=list)
    # Absolute / fixed boxes captured during main pass; placed after.
    deferred_absolutes: list[_DeferredAbsolute] = field(default_factory=list)
    # Cumulative position-relative offset applied to placements.
    relative_offset_x: int = 0
    relative_offset_y: int = 0


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
    # The viewport itself is the initial containing block (also the
    # CB for `position: fixed` and for `position: absolute` when no
    # positioned ancestor exists).
    state.cb_stack.append(_ContainingBlock(x=0, y=0, width=viewport_width))
    _place_block(root, state, x=0, y=0, containing_width=viewport_width)
    state.cb_stack.pop()

    # Lay out absolutes / fixed elements that were deferred during
    # the main pass. Sort by z-index ascending (auto treated as 0) so
    # higher z-index paints later, on top of lower. Document order is
    # the stable tiebreak.
    deferred_with_z: list[tuple[int, int, _DeferredAbsolute]] = [
        (_parse_z_index(d.box.style.z_index), order, d)
        for order, d in enumerate(state.deferred_absolutes)
    ]
    deferred_with_z.sort(key=lambda triple: (triple[0], triple[1]))
    for _, _, deferred in deferred_with_z:
        if state.budget_exceeded:
            break
        _place_absolute(deferred, state)

    total_height = root.geometry.y + root.geometry.border_box_height + root.geometry.margin.bottom
    return total_height, state.items


def _parse_z_index(value: str) -> int:
    text = (value or "auto").strip().lower()
    if text in ("", "auto"):
        return 0
    try:
        return int(text)
    except ValueError:
        return 0



def _place_block(box: Box, state: LayoutState, *, x: int, y: int, containing_width: int) -> int:
    """Resolve geometry and emit placements for a block-level box.
    Returns the bottom margin edge y-coordinate."""
    style = box.style
    position = style.position

    # Absolute and fixed are taken out of normal flow; capture their
    # containing block now and lay them out after the main pass.
    if position in ("absolute", "fixed"):
        if position == "fixed":
            cb = state.cb_stack[0] if state.cb_stack else _ContainingBlock(0, 0, containing_width)
        else:
            cb = state.cb_stack[-1] if state.cb_stack else _ContainingBlock(0, 0, containing_width)
        state.deferred_absolutes.append(
            _DeferredAbsolute(box=box, containing_block=cb, is_fixed=(position == "fixed"))
        )
        return y

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

    # If overflow is non-visible, wrap the box's children in a clip
    # region. The clip rect's height isn't known yet — use a sentinel
    # patched in finalize_clips, mirroring the background flow.
    clip_open_index: int | None = None
    if style.overflow == "hidden":
        clip_open_index = len(state.items)
        state.items.append(
            ClipPushPlacement(
                x=box.geometry.x + border.left + state.relative_offset_x,
                y=box.geometry.y + border.top + state.relative_offset_y,
                width=padding.left + content_width + padding.right,
                height=_BACKGROUND_PLACEHOLDER,
            )
        )

    # Apply relative-position offset for this box and its descendants.
    saved_offset = (state.relative_offset_x, state.relative_offset_y)
    pushed_cb = False
    if position == "relative":
        dx, dy = _relative_offset(style)
        state.relative_offset_x += dx
        state.relative_offset_y += dy
        # A relative box establishes a containing block for absolute
        # descendants at its content edge.
        state.cb_stack.append(
            _ContainingBlock(
                x=box.geometry.x + border.left + padding.left,
                y=box.geometry.y + border.top + padding.top,
                width=content_width,
            )
        )
        pushed_cb = True

    # Emit the background rect before children so painters see it
    # beneath them. We emit only when a non-default background exists.
    _maybe_emit_background(box, state)

    child_x = box.geometry.x + border.left + padding.left
    child_y = box.geometry.y + border.top + padding.top
    inner_width = content_width

    cursor_y = child_y
    bfc_left = child_x
    bfc_right = child_x + inner_width
    if box.children and all(
        child.is_inline_level and child.style.float == "none"
        for child in box.children
    ):
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

            # Honour `clear` before placing, regardless of float
            # status of this child.
            clear = child.style.clear
            if clear != "none":
                clear_side = None if clear == "both" else clear
                clear_y = state.floats.lowest(clear_side)
                if cursor_y < clear_y:
                    cursor_y = clear_y

            if child.style.float in ("left", "right"):
                _place_float(
                    child, state,
                    bfc_left=bfc_left, bfc_right=bfc_right,
                    available_y=cursor_y, containing_width=inner_width,
                )
                # Float does not advance cursor for in-flow content.
                previous_margin_bottom = 0
                continue

            if child.is_block_level:
                child_margin_top = _resolve_margin(child.style).top
                collapse = max(previous_margin_bottom, child_margin_top)
                if cursor_y == child_y:
                    collapse = 0
                cursor_y = cursor_y - previous_margin_bottom + collapse - child_margin_top
                # Narrow the in-flow block around active floats at this y.
                avail_left, avail_right = state.floats.constrain(
                    cursor_y + child_margin_top, 1, bfc_left, bfc_right,
                )
                block_x = avail_left
                block_width = max(avail_right - avail_left, 0)
                cursor_y = _place_block(child, state, x=block_x, y=cursor_y, containing_width=block_width)
                previous_margin_bottom = _resolve_margin(child.style).bottom
            else:
                cursor_y = _place_inline_or_text(
                    child, state, x=child_x, y=cursor_y,
                    content_width=inner_width, parent_style=style,
                )
                previous_margin_bottom = 0
        # Containing block expands to enclose any floats that would
        # otherwise escape — clearfix-by-default. Real CSS only does
        # this for new BFC roots; we apply broadly for now and revisit
        # when overflow lands.
        cursor_y = max(cursor_y, state.floats.lowest())

    used_content_height = max(cursor_y - child_y, 0)
    content_height = _resolve_height(style, used_content_height)
    box.geometry.content_height = content_height

    # Restore relative offset / CB stack before returning.
    if pushed_cb:
        state.cb_stack.pop()
    state.relative_offset_x, state.relative_offset_y = saved_offset

    # Close the clip region opened above, with the now-known content
    # height and a matching pop.
    if clip_open_index is not None:
        clip = state.items[clip_open_index]
        assert isinstance(clip, ClipPushPlacement)
        clip_height = padding.top + content_height + padding.bottom
        state.items[clip_open_index] = ClipPushPlacement(
            x=clip.x, y=clip.y, width=clip.width, height=clip_height,
        )
        state.items.append(ClipPopPlacement())

    box_bottom = box.geometry.y + border.top + padding.top + content_height + padding.bottom + border.bottom
    return box_bottom + margin.bottom


def _relative_offset(style: ComputedStyle) -> tuple[int, int]:
    """Compute the (dx, dy) offset implied by top/right/bottom/left
    on a `position: relative` box. left/top win over right/bottom when
    both are non-auto, matching CSS 2.1.
    """

    def axis(start: str, end: str, sign_end: int) -> int:
        if start.strip().lower() not in ("", "auto"):
            return _length_to_px(start)
        if end.strip().lower() not in ("", "auto"):
            return sign_end * _length_to_px(end)
        return 0

    dx = axis(style.left, style.right, -1)
    dy = axis(style.top, style.bottom, -1)
    return dx, dy


def _place_absolute(deferred: _DeferredAbsolute, state: LayoutState) -> None:
    """Lay out an absolute / fixed box at its captured containing
    block. Only `top` and `left` are honoured for now; `right` and
    `bottom` are deferred to a polish pass.
    """
    box = deferred.box
    cb = deferred.containing_block
    style = box.style

    margin = _resolve_margin(style)
    padding = _resolve_padding(style)
    border = EdgeSizes()
    box.geometry.margin = margin
    box.geometry.padding = padding
    box.geometry.border = border

    explicit = _length_to_px(style.width.strip().lower()) if style.width.strip().lower() not in ("", "auto") else 0
    if explicit > 0:
        content_width = explicit
    else:
        content_width = max(cb.width - margin.left - margin.right - padding.left - padding.right, 0)
    box.geometry.content_width = content_width

    # Resolve positional offsets. left/top win when both sides are
    # specified, mirroring the CSS 2.1 over-constrained-box rule. We
    # estimate the box's width/height for right/bottom resolution.
    left = style.left.strip().lower()
    right = style.right.strip().lower()
    top = style.top.strip().lower()
    bottom = style.bottom.strip().lower()
    explicit_h = _length_to_px(style.height.strip().lower()) if style.height.strip().lower() not in ("", "auto") else 0
    border_box_width = (
        border.left + padding.left + content_width + padding.right + border.right
    )

    if left and left != "auto":
        offset_x = _length_to_px(left)
    elif right and right != "auto":
        offset_x = cb.width - _length_to_px(right) - border_box_width - margin.left - margin.right
    else:
        offset_x = 0

    if top and top != "auto":
        offset_y = _length_to_px(top)
    elif bottom and bottom != "auto" and explicit_h > 0:
        # bottom only makes sense with a known height; otherwise we'd
        # need a two-pass measurement we don't do yet.
        # For an unknown CB height we cannot resolve bottom-from-CB
        # reliably; fall back to 0.
        offset_y = 0
    else:
        offset_y = 0

    box.geometry.x = cb.x + offset_x + margin.left
    box.geometry.y = cb.y + offset_y + margin.top

    _maybe_emit_background(box, state)

    # Absolute / fixed boxes establish a CB for their descendants.
    state.cb_stack.append(
        _ContainingBlock(
            x=box.geometry.x + border.left + padding.left,
            y=box.geometry.y + border.top + padding.top,
            width=content_width,
        )
    )
    saved_floats = state.floats
    state.floats = FloatContext()
    try:
        child_x = box.geometry.x + border.left + padding.left
        child_y = box.geometry.y + border.top + padding.top
        cursor = child_y
        if box.children and all(c.is_inline_level and c.style.float == "none" for c in box.children):
            cursor = _layout_inline_context(
                box.children, state,
                x0=child_x, y0=child_y, content_width=content_width, parent_style=style,
            )
        else:
            for child in box.children:
                if state.budget_exceeded:
                    break
                if child.is_block_level:
                    cursor = _place_block(child, state, x=child_x, y=cursor, containing_width=content_width)
                else:
                    cursor = _place_inline_or_text(child, state, x=child_x, y=cursor, content_width=content_width, parent_style=style)
        used_height = max(cursor - child_y, 0)
        content_height = _resolve_height(style, used_height)
        box.geometry.content_height = content_height
    finally:
        state.cb_stack.pop()
        state.floats = saved_floats


def _place_float(
    box: Box,
    state: LayoutState,
    *,
    bfc_left: int,
    bfc_right: int,
    available_y: int,
    containing_width: int,
) -> None:
    """Place a floated block at the appropriate edge of its BFC,
    register the resulting exclusion, and emit its contents. The
    cursor in the parent BFC is not advanced; in-flow siblings will
    be narrowed via FloatContext.constrain at their own y.
    """
    style = box.style
    margin = _resolve_margin(style)
    padding = _resolve_padding(style)
    border = EdgeSizes()
    box.geometry.margin = margin
    box.geometry.padding = padding
    box.geometry.border = border

    # Float width: explicit, else the containing block's width minus
    # margins (CSS would shrink-to-fit; we approximate by using the
    # full available width as a ceiling).
    explicit = _length_to_px(style.width.strip().lower()) if style.width.strip().lower() not in ("", "auto") else 0
    if explicit > 0:
        content_width = explicit
    else:
        content_width = max(containing_width - margin.left - margin.right - padding.left - padding.right, 0)
    box.geometry.content_width = content_width

    border_box_width = (
        border.left + padding.left + content_width + padding.right + border.right
    )

    # Find a y at-or-below available_y where the float fits between
    # active floats on its preferred side.
    side = style.float  # "left" or "right"
    candidate_y = available_y
    while True:
        avail_left, avail_right = state.floats.constrain(
            candidate_y, 1, bfc_left, bfc_right,
        )
        if avail_right - avail_left >= border_box_width + margin.left + margin.right:
            break
        next_clear = _next_clearance(state.floats, candidate_y)
        if next_clear is None:
            break  # no more floats to clear — place anyway, may overflow
        candidate_y = next_clear

    if side == "left":
        box.geometry.x = avail_left + margin.left
    else:
        box.geometry.x = avail_right - margin.right - border_box_width
    box.geometry.y = candidate_y + margin.top

    _maybe_emit_background(box, state)

    # Floats establish their own BFC for their contents, so we
    # recursively lay out their children with a fresh float context.
    saved_floats = state.floats
    state.floats = FloatContext()
    try:
        child_x = box.geometry.x + border.left + padding.left
        child_y = box.geometry.y + border.top + padding.top
        cursor = child_y
        if box.children and all(c.is_inline_level and c.style.float == "none" for c in box.children):
            cursor = _layout_inline_context(
                box.children, state,
                x0=child_x, y0=child_y, content_width=content_width, parent_style=style,
            )
        else:
            for child in box.children:
                if state.budget_exceeded:
                    break
                if child.is_block_level:
                    cursor = _place_block(child, state, x=child_x, y=cursor, containing_width=content_width)
                else:
                    cursor = _place_inline_or_text(child, state, x=child_x, y=cursor, content_width=content_width, parent_style=style)
        used_height = max(cursor - child_y, 0)
        content_height = _resolve_height(style, used_height)
        box.geometry.content_height = content_height
    finally:
        state.floats = saved_floats

    box_bottom = box.geometry.y + border.top + padding.top + box.geometry.content_height + padding.bottom + border.bottom
    bottom_with_margin = box_bottom + margin.bottom

    if side == "left":
        edge_x = box.geometry.x + border_box_width + margin.right
    else:
        edge_x = box.geometry.x - margin.left
    state.floats.exclusions.append(
        FloatExclusion(side=side, top=candidate_y, bottom=bottom_with_margin, edge_x=edge_x)
    )


def _next_clearance(context: FloatContext, y: int) -> int | None:
    """Lowest active float bottom strictly greater than y, or None."""
    candidates = [ex.bottom for ex in context.exclusions if ex.bottom > y]
    if not candidates:
        return None
    return min(candidates)


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

    # A line-under-construction. line_x_start and line_max_width are
    # refreshed each line so the line narrows around active floats at
    # the line's y.
    line_items: list[tuple[int, _InlineFragment]] = []
    line_x_start = x0
    line_max_width = content_width
    cursor_x = x0
    cursor_y = y0
    line_max_height = 0
    line_max_font_size = 0

    def refresh_line_bounds() -> None:
        nonlocal line_x_start, line_max_width, cursor_x
        # Estimate a default line height for float overlap testing.
        probe_h = _line_height_px(parent_style, fallback_font_size=line_max_font_size or _font_size_px(parent_style))
        avail_left, avail_right = state.floats.constrain(
            cursor_y, probe_h, x0, x0 + content_width,
        )
        line_x_start = avail_left
        line_max_width = max(avail_right - avail_left, 0)
        cursor_x = line_x_start

    refresh_line_bounds()

    def flush_line(force: bool = False) -> None:
        nonlocal cursor_x, cursor_y, line_items, line_max_height, line_max_font_size
        if not line_items:
            if force:
                cursor_y += _line_height_px(
                    parent_style,
                    fallback_font_size=line_max_font_size or _font_size_px(parent_style),
                )
                line_max_height = 0
                line_max_font_size = 0
            return
        line_box_height = max(
            line_max_height,
            _line_height_px(parent_style, fallback_font_size=line_max_font_size or _font_size_px(parent_style)),
        )
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
                        x=x + state.relative_offset_x,
                        y=cursor_y + max(offset, 0) + state.relative_offset_y,
                        text=fragment.text,
                        color=(fragment.style or parent_style).color,
                        font_size=fs,
                        font_weight=(fragment.style or parent_style).font_weight,
                        font_style=(fragment.style or parent_style).font_style,
                        text_decoration=(fragment.style or parent_style).text_decoration,
                        max_width=content_width,
                        text_align=(fragment.style or parent_style).text_align,
                    )
                )
            else:
                offset = max(line_box_height - fragment.height, 0)
                state.items.append(
                    ImagePlacement(
                        x=x + state.relative_offset_x,
                        y=cursor_y + offset + state.relative_offset_y,
                        width=fragment.width,
                        height=fragment.height,
                        label=fragment.label,
                        bitmap=fragment.bitmap,
                    )
                )
        cursor_y += line_box_height
        line_items = []
        line_max_height = 0
        line_max_font_size = 0
        refresh_line_bounds()

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
            if cursor_x + space_width + word_width > line_x_start + line_max_width and line_items:
                flush_line()
                space_width = 0
            if space_width:
                cursor_x += space_width
            line_items.append((cursor_x, fragment))
            cursor_x += word_width
            line_max_font_size = max(line_max_font_size, fs)
            line_max_height = max(
                line_max_height,
                _line_height_px(fragment.style or parent_style, fallback_font_size=fs),
            )
        else:  # image
            if cursor_x + fragment.width > line_x_start + line_max_width and line_items:
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
                x=x + state.relative_offset_x,
                y=y + state.relative_offset_y,
                text=text,
                color=style.color,
                font_size=font_size,
                font_weight=style.font_weight,
                font_style=style.font_style,
                text_decoration=style.text_decoration,
                max_width=content_width,
                text_align=style.text_align,
            )
        )
        return y + _line_height_px(style, fallback_font_size=font_size)

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
            ImagePlacement(
                x=x + state.relative_offset_x,
                y=y + state.relative_offset_y,
                width=width,
                height=height,
                label=label,
                bitmap=asset,
            )
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
    geom = box.geometry
    x = geom.x + geom.border.left + state.relative_offset_x
    y = geom.y + geom.border.top + state.relative_offset_y
    width = geom.padding.left + geom.content_width + geom.padding.right
    state.items.append(
        BoxPlacement(
            x=x,
            y=y,
            width=width,
            height=_BACKGROUND_PLACEHOLDER,
            color=color,
            node_id=box.node_id,
        )
    )


_BACKGROUND_PLACEHOLDER = -1  # height sentinel for post-pass resolution


def finalize_backgrounds(root: Box, items: list[Placement]) -> list[Placement]:
    """Patch placeholder background heights now that all geometry is
    resolved. Lookup is keyed by node_id so it survives any relative-
    position offset applied at emit time.
    """
    heights: dict[NodeId, int] = {}
    for box in _walk(root):
        if not box.is_block_level or box.node_id is None:
            continue
        color = box.style.background_color
        if not color or color == "#ffffff":
            continue
        geom = box.geometry
        height = geom.padding.top + geom.content_height + geom.padding.bottom
        heights[box.node_id] = height

    resolved: list[Placement] = []
    for item in items:
        if isinstance(item, BoxPlacement) and item.height == _BACKGROUND_PLACEHOLDER:
            height = heights.get(item.node_id, 0) if item.node_id is not None else 0
            if height <= 0:
                continue
            resolved.append(
                BoxPlacement(
                    x=item.x,
                    y=item.y,
                    width=item.width,
                    height=height,
                    color=item.color,
                    node_id=item.node_id,
                )
            )
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


def _line_height_px(style: ComputedStyle, *, fallback_font_size: int | None = None) -> int:
    font_size = fallback_font_size if fallback_font_size is not None else _font_size_px(style)
    value = style.line_height.strip().lower()
    if not value or value == "normal":
        return max(int(round(font_size * 1.3)), 10)
    try:
        return max(int(round(font_size * float(value))), 1)
    except ValueError:
        pass
    if value.endswith("px"):
        try:
            return max(int(round(float(value[:-2]))), 1)
        except ValueError:
            return max(int(round(font_size * 1.3)), 10)
    if value.endswith("em"):
        try:
            return max(int(round(font_size * float(value[:-2]))), 1)
        except ValueError:
            return max(int(round(font_size * 1.3)), 10)
    if value.endswith("%"):
        try:
            return max(int(round(font_size * float(value[:-1]) / 100)), 1)
        except ValueError:
            return max(int(round(font_size * 1.3)), 10)
    return max(int(round(font_size * 1.3)), 10)
