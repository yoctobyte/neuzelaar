"""Box tree: the layout-time representation between DOM and display list.

A box is produced for every element and text node that participates in
layout, skipping `display: none`, `<head>`, `<title>`, `<script>`, and
`<style>`. Each box carries its computed style, a kind (block, inline,
anonymous-block, text, replaced), geometry (zeroed at construction
time; filled in by layout algorithms), and its children.

Key rules implemented here:

- Text nodes become TEXT boxes; runs of pure whitespace between
  block-level siblings are dropped (simple whitespace handling).
- `<img>` becomes a REPLACED box, inline-replaced by default.
- Elements with `display: none` and their subtrees are excluded.
- When a block container has a mix of block-level and inline-level
  children, inline runs are wrapped in ANONYMOUS_BLOCK boxes. This
  implements the CSS 2.1 rule (section 9.2.1.1) that forces a block
  container with any block child to contain only block-level boxes.

Layout behavior (block / inline / float / positioning algorithms) lives
in separate modules that consume this tree. The box tree is the shared
substrate they all attach to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from neuzelaar.document.dom import Document, Element, Node, NodeId, Text
from neuzelaar.document.styles import ComputedStyle


# Elements that never produce layout boxes regardless of computed style.
SKIPPED_TAGS: frozenset[str] = frozenset(
    {"head", "title", "script", "style", "meta", "link", "base"}
)


# Display values that behave as block-level boxes in normal flow.
BLOCK_LIKE_DISPLAYS: frozenset[str] = frozenset(
    {"block", "list-item", "table", "flex", "grid"}
)


# Display values that behave as inline-level boxes in normal flow.
# inline-block is inline-level for its parent's flow but establishes a
# block formatting context internally.
INLINE_LEVEL_DISPLAYS: frozenset[str] = frozenset(
    {"inline", "inline-block", "inline-table"}
)


class BoxKind(Enum):
    BLOCK = "block"
    INLINE = "inline"
    ANONYMOUS_BLOCK = "anonymous-block"
    TEXT = "text"
    REPLACED = "replaced"


@dataclass(slots=True)
class EdgeSizes:
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0


@dataclass(slots=True)
class BoxGeometry:
    """Positioned geometry of a box. Filled in by layout algorithms.

    Coordinates are relative to the containing block's content edge.
    content_width and content_height describe the content box; the
    border and padding edges are derived via the EdgeSizes.
    """

    x: int = 0
    y: int = 0
    content_width: int = 0
    content_height: int = 0
    padding: EdgeSizes = field(default_factory=EdgeSizes)
    border: EdgeSizes = field(default_factory=EdgeSizes)
    margin: EdgeSizes = field(default_factory=EdgeSizes)

    @property
    def border_box_width(self) -> int:
        return (
            self.border.left
            + self.padding.left
            + self.content_width
            + self.padding.right
            + self.border.right
        )

    @property
    def border_box_height(self) -> int:
        return (
            self.border.top
            + self.padding.top
            + self.content_height
            + self.padding.bottom
            + self.border.bottom
        )


@dataclass(slots=True)
class Box:
    kind: BoxKind
    style: ComputedStyle
    node_id: NodeId | None = None  # None for anonymous / text boxes without id
    tag: str | None = None  # original lower-cased tag name, for layout decisions
    text: str | None = None  # populated for TEXT boxes
    element: Element | None = None  # kept for replaced boxes needing attrs
    children: list["Box"] = field(default_factory=list)
    geometry: BoxGeometry = field(default_factory=BoxGeometry)

    @property
    def is_block_level(self) -> bool:
        return self.kind in (BoxKind.BLOCK, BoxKind.ANONYMOUS_BLOCK)

    @property
    def is_inline_level(self) -> bool:
        return self.kind in (BoxKind.INLINE, BoxKind.TEXT, BoxKind.REPLACED)


def build_box_tree(
    document: Document,
    styles: dict[NodeId, ComputedStyle],
) -> Box | None:
    """Build a box tree rooted at the document's first child element.

    Returns None if no renderable element exists (empty document).
    """
    for child in document.children:
        box = _build_from_node(child, styles, parent_style=ComputedStyle())
        if box is not None:
            return box
    return None


def _build_from_node(
    node: Node,
    styles: dict[NodeId, ComputedStyle],
    *,
    parent_style: ComputedStyle,
) -> Box | None:
    if isinstance(node, Text):
        text = node.data
        if text is None:
            return None
        if text == "":
            return None
        if parent_style.white_space in {"pre", "pre-wrap", "pre-line"}:
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            return Box(kind=BoxKind.TEXT, style=parent_style, text=normalized)
        stripped = text.strip()
        if not stripped:
            return None
        normalised = " ".join(text.split())
        return Box(kind=BoxKind.TEXT, style=parent_style, text=normalised)

    if not isinstance(node, Element):
        return None

    tag = node.tag.lower()
    if tag in SKIPPED_TAGS:
        return None

    style = styles.get(node.id, ComputedStyle())
    display = (style.display or "block").lower()
    if display == "none":
        return None

    # Replaced elements — img for now. Treated as inline-level by
    # default; an explicit `display: block` or `display: inline-block`
    # in styles would change that but both still map to a REPLACED box
    # since their layout is driven by intrinsic dimensions.
    if tag == "img":
        return Box(
            kind=BoxKind.REPLACED,
            style=style,
            node_id=node.id,
            tag=tag,
            element=node,
        )

    children: list[Box] = []
    for child in node.children:
        child_box = _build_from_node(child, styles, parent_style=style)
        if child_box is not None:
            children.append(child_box)

    if display in INLINE_LEVEL_DISPLAYS:
        kind = BoxKind.INLINE
    else:
        kind = BoxKind.BLOCK

    box = Box(
        kind=kind,
        style=style,
        node_id=node.id,
        tag=tag,
        children=children,
    )

    if kind == BoxKind.BLOCK:
        box.children = _wrap_inline_runs_if_mixed(children)
    return box


def _wrap_inline_runs_if_mixed(children: list[Box]) -> list[Box]:
    """Wrap inline-level runs in anonymous block boxes when the parent
    block has any block-level child. If all children are inline-level,
    leave them as-is so the parent establishes an IFC directly.
    """
    has_block = any(child.is_block_level for child in children)
    if not has_block:
        return children

    result: list[Box] = []
    current_run: list[Box] = []

    def flush() -> None:
        if not current_run:
            return
        # Drop runs that are pure whitespace-only text after collapsing.
        if all(child.kind == BoxKind.TEXT and not (child.text or "").strip() for child in current_run):
            current_run.clear()
            return
        result.append(
            Box(
                kind=BoxKind.ANONYMOUS_BLOCK,
                style=ComputedStyle(),
                children=list(current_run),
            )
        )
        current_run.clear()

    for child in children:
        if child.is_inline_level:
            current_run.append(child)
        else:
            flush()
            result.append(child)
    flush()
    return result


def walk_box_tree(root: Box):
    """Yield every box in depth-first pre-order starting at root."""
    yield root
    for child in root.children:
        yield from walk_box_tree(child)
