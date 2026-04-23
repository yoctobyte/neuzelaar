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
