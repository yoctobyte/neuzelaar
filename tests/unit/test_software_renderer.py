from pathlib import Path

from neuzelaar.core.page import PageLoader
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.render.display_list import DrawImage
from neuzelaar.render.software import rasterize
from neuzelaar.shell_api.frame import PixelFormat


def test_rasterize_returns_neutral_frame() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/example.html").resolve().as_uri())
    display_list = build_display_list(result.handler_result.value)

    frame = rasterize(display_list)

    assert frame.width == display_list.width
    assert frame.height == display_list.height
    assert frame.format == PixelFormat.RGBA8888
    assert frame.stride == frame.width * 4
    assert len(frame.pixels) == frame.height * frame.stride


def test_rasterize_blits_local_images() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())
    display_list = build_display_list(
        result.handler_result.value,
        styles=result.styles,
        images=result.images,
    )
    image_op = next(op for op in display_list.ops if isinstance(op, DrawImage))

    frame = rasterize(display_list)

    pixel_offset = (image_op.y * frame.stride) + (image_op.x * 4)
    assert frame.pixels[pixel_offset : pixel_offset + 4] == bytes((255, 0, 0, 255))


def test_rasterize_with_viewport_returns_viewport_sized_frame() -> None:
    from neuzelaar.render.display_list import Rect

    result = PageLoader().load(Path("tests/fixtures/sites/example.html").resolve().as_uri())
    display_list = build_display_list(result.handler_result.value)

    viewport = Rect(x=0, y=0, width=400, height=200)
    frame = rasterize(display_list, viewport=viewport)

    assert frame.width == 400
    assert frame.height == 200
    assert len(frame.pixels) == 400 * 200 * 4


def test_rasterize_with_viewport_translates_content_to_zero_origin() -> None:
    # An image positioned at y=50 on the page should appear at y=0 in
    # a viewport that starts at y=50.
    from neuzelaar.render.display_list import Rect

    result = PageLoader().load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())
    display_list = build_display_list(
        result.handler_result.value,
        styles=result.styles,
        images=result.images,
    )
    image_op = next(op for op in display_list.ops if isinstance(op, DrawImage))

    viewport = Rect(
        x=0,
        y=image_op.y,
        width=display_list.width,
        height=200,
    )
    frame = rasterize(display_list, viewport=viewport)

    # The first red pixel of the image now sits at (image_op.x, 0) in
    # the frame, not (image_op.x, image_op.y).
    pixel_offset = (0 * frame.stride) + (image_op.x * 4)
    assert frame.pixels[pixel_offset : pixel_offset + 4] == bytes((255, 0, 0, 255))


def test_rasterize_viewport_skips_offscreen_ops() -> None:
    # Render a viewport that's far below any content; the frame should
    # come back as the default white background since every op is
    # filtered out by the frame clip.
    from neuzelaar.render.display_list import Rect

    result = PageLoader().load(Path("tests/fixtures/sites/example.html").resolve().as_uri())
    display_list = build_display_list(result.handler_result.value)

    viewport = Rect(x=0, y=display_list.height + 1000, width=400, height=200)
    frame = rasterize(display_list, viewport=viewport)

    # All white background.
    assert frame.pixels[: frame.stride] == b"\xff\xff\xff\xff" * 400
