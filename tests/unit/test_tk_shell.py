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
