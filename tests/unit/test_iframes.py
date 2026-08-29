from pathlib import Path

from neuzelaar.core.page import FrameBudget, PageLoader
from neuzelaar.core.policy.profile import PolicyProfile
from neuzelaar.core.policy.rules import PolicyEngine
from neuzelaar.document.layout import layout_document
from neuzelaar.document.layout import LayoutClipPop, LayoutClipPush, LayoutImage, LayoutText


def fixture_url(name: str) -> str:
    return Path(f"tests/fixtures/sites/{name}").resolve().as_uri()


def load(name: str, **loader_kwargs) -> object:
    return PageLoader(**loader_kwargs).load(fixture_url(name))


def test_iframe_loads_the_nested_document_as_its_own_page() -> None:
    result = load("iframe_page.html")

    assert len(result.frames) == 1
    frame = next(iter(result.frames.values()))
    assert frame.url.endswith("iframe_child.html")
    # A nested context is a full page load: its own document, its own
    # stylesheet, its own computed styles.
    assert frame.result.handler_result.value.title == "Framed Child"
    assert "Nested document" in frame.result.rendered_text
    assert frame.result.styles


def test_iframes_can_be_turned_off_entirely() -> None:
    result = load("iframe_page.html", frame_budget=FrameBudget(enabled=False))

    assert result.frames == {}


def test_frame_budget_caps_nesting_depth() -> None:
    # self_framing.html iframes itself. Without a depth cap this
    # recurses until the machine gives out.
    result = load("self_framing.html", frame_budget=FrameBudget(max_depth=2))

    depth = 0
    node = result
    while node.frames:
        node = next(iter(node.frames.values())).result
        depth += 1
    assert depth == 2


def test_frame_budget_caps_total_frame_count_across_the_tree() -> None:
    result = load("self_framing.html", frame_budget=FrameBudget(max_depth=10, max_frames=3))

    total = 0
    stack = [result]
    while stack:
        node = stack.pop()
        total += len(node.frames)
        stack.extend(frame.result for frame in node.frames.values())
    assert total == 3


def test_strict_profile_still_blocks_third_party_iframes() -> None:
    strict = PageLoader(policy_engine=PolicyEngine(PolicyProfile.STRICT))
    result = strict.load(fixture_url("third_party_iframe.html"))

    assert result.frames == {}
    blocked = [
        planned
        for planned in result.planned_subresources
        if not planned.decision.allowed
    ]
    assert any("iframe" in planned.decision.reason for planned in blocked)


def test_layout_places_frame_content_clipped_inside_the_frame_box() -> None:
    result = load("iframe_page.html")
    layout = layout_document(
        result.handler_result.value,
        width=800,
        styles=result.styles,
        images=result.images,
        root_style=result.root_style,
        frames=result.frames,
    )

    items = list(layout.items)
    push_index = next(i for i, item in enumerate(items) if isinstance(item, LayoutClipPush))
    pop_index = next(i for i, item in enumerate(items) if isinstance(item, LayoutClipPop))
    clip = items[push_index]
    assert (clip.width, clip.height) == (420, 160)

    inside = [item for item in items[push_index:pop_index] if isinstance(item, LayoutText)]
    assert any(item.text == "Nested" for item in inside)
    # Frame content is translated into the parent's space and clipped.
    for item in inside:
        assert clip.x <= item.x < clip.x + clip.width
        assert clip.y <= item.y < clip.y + clip.height
    # Node ids are dropped: they address the nested document, and a
    # click resolved against the parent would navigate the wrong page.
    assert all(item.node_id is None for item in inside)


def test_unloaded_frame_renders_as_a_placeholder() -> None:
    result = load("iframe_page.html", frame_budget=FrameBudget(enabled=False))
    layout = layout_document(
        result.handler_result.value,
        width=800,
        styles=result.styles,
        root_style=result.root_style,
        frames=result.frames,
    )

    placeholder = next(
        item
        for item in layout.items
        if isinstance(item, LayoutImage) and item.label.startswith("iframe:")
    )
    assert (placeholder.width, placeholder.height) == (420, 160)
    assert placeholder.bitmap is None
    assert not any(isinstance(item, LayoutClipPush) for item in layout.items)


def test_iframe_falls_back_to_the_html_default_size() -> None:
    result = load("iframe_default_size.html", frame_budget=FrameBudget(enabled=False))
    layout = layout_document(
        result.handler_result.value,
        width=800,
        styles=result.styles,
        root_style=result.root_style,
        frames=result.frames,
    )

    placeholder = next(
        item
        for item in layout.items
        if isinstance(item, LayoutImage) and item.label.startswith("iframe:")
    )
    assert (placeholder.width, placeholder.height) == (300, 150)
