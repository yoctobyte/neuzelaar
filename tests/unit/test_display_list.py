from pathlib import Path

from neuzelaar.core.page import PageLoader
from neuzelaar.render.display_builder import build_display_list
from neuzelaar.document.styles import ComputedStyle
from neuzelaar.render.display_list import Color, DrawImage, DrawText, FillRect, Placeholder


def document_from_fixture(name: str):
    result = PageLoader().load(Path(f"tests/fixtures/sites/{name}").resolve().as_uri())
    return result.handler_result.value


def test_build_display_list_contains_background_and_text() -> None:
    display_list = build_display_list(document_from_fixture("example.html"))

    assert isinstance(display_list.ops[0], FillRect)
    assert any(isinstance(op, DrawText) and op.text == "Example Domain" for op in display_list.ops)
    assert display_list.width == 800
    assert display_list.height > 0


def test_build_display_list_contains_image_placeholders() -> None:
    display_list = build_display_list(document_from_fixture("basic_images.html"))

    assert any(isinstance(op, Placeholder) and "Local Placeholder" in op.label for op in display_list.ops)


def test_build_display_list_draws_decoded_images_when_provided() -> None:
    result = PageLoader().load(Path("tests/fixtures/sites/basic_images.html").resolve().as_uri())
    display_list = build_display_list(
        result.handler_result.value,
        styles=result.styles,
        images=result.images,
    )

    assert any(isinstance(op, DrawImage) for op in display_list.ops)


def test_build_display_list_uses_root_style_colors() -> None:
    display_list = build_display_list(
        document_from_fixture("example.html"),
        root_style=ComputedStyle(color="blue", background_color="#eeeeee"),
    )

    assert isinstance(display_list.ops[0], FillRect)
    assert display_list.ops[0].color == Color(238, 238, 238)
    assert any(isinstance(op, DrawText) and op.color == Color(0, 0, 180) for op in display_list.ops)
