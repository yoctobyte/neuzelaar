from pathlib import Path

from neuzelaar.shell_api.frame import PixelFormat
from neuzelaar.shells.tk.shell import TkShell


def test_tk_shell_can_render_url_to_frame_without_opening_window() -> None:
    shell = TkShell(width=640, height=480)

    result, frame = shell.render_url_to_frame(Path("tests/fixtures/sites/example.html").resolve().as_uri())

    assert result.mime_decision.kind == "html"
    assert frame.width == 640
    assert frame.height > 0
    assert frame.format == PixelFormat.RGBA8888


def test_tk_shell_detects_when_frame_needs_scroll() -> None:
    shell = TkShell(width=640, height=10)

    _result, frame = shell.render_url_to_frame(Path("tests/fixtures/sites/basic_lists.html").resolve().as_uri())

    assert shell.needs_vertical_scroll(frame)


def test_tk_shell_uses_page_styles_for_frame_path() -> None:
    shell = TkShell(width=640, height=480)

    result, frame = shell.render_url_to_frame(Path("tests/fixtures/sites/styled_page.html").resolve().as_uri())

    assert result.root_style.color == "red"
    assert frame.width == 640
