import base64

import pytest

from neuzelaar.engines.image.pillow_adapter import ImageDecodeError, decode_image_info


def test_decode_image_info_returns_dimensions() -> None:
    png_body = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    info = decode_image_info(png_body)

    assert info.width == 1
    assert info.height == 1
    assert info.format == "PNG"


def test_decode_image_info_raises_on_invalid_bytes() -> None:
    with pytest.raises(ImageDecodeError):
        decode_image_info(b"not an image")
