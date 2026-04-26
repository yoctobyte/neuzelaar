from neuzelaar.render.software import _font_filename


def test_font_filename_chooses_regular_variant() -> None:
    assert _font_filename("normal", "normal") == "DejaVuSans.ttf"


def test_font_filename_chooses_bold_variant() -> None:
    assert _font_filename("bold", "normal") == "DejaVuSans-Bold.ttf"
    assert _font_filename("700", "normal") == "DejaVuSans-Bold.ttf"


def test_font_filename_chooses_italic_variant() -> None:
    assert _font_filename("normal", "italic") == "DejaVuSans-Oblique.ttf"
    assert _font_filename("normal", "oblique") == "DejaVuSans-Oblique.ttf"


def test_font_filename_chooses_bold_italic_variant() -> None:
    assert _font_filename("bold", "italic") == "DejaVuSans-BoldOblique.ttf"
