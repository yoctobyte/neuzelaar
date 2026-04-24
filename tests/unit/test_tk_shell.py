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


def test_tk_shell_uses_linked_styles_in_frame_path() -> None:
    shell = TkShell(width=640, height=480)

    result, frame = shell.render_url_to_frame(Path("tests/fixtures/sites/linked_styles.html").resolve().as_uri())

    assert result.root_style.color == "blue"
    assert result.root_style.background_color == "#dddddd"
    assert frame.width == 640


def test_tk_shell_supports_back_forward_and_reload_without_window() -> None:
    shell = TkShell(width=640, height=480)

    first, _ = shell.render_url_to_frame(Path("tests/fixtures/sites/basic_links.html").resolve().as_uri())
    second, _ = shell.render_url_to_frame(Path("tests/fixtures/sites/example.html").resolve().as_uri())
    back, _ = shell.back_to_frame()
    forward, _ = shell.forward_to_frame()
    reloaded, _ = shell.reload_to_frame()

    assert "Links Test" in first.rendered_text
    assert "Example Domain" in second.rendered_text
    assert "Links Test" in back.rendered_text
    assert "Example Domain" in forward.rendered_text
    assert reloaded.resource.final_url == forward.resource.final_url


def test_tk_shell_page_summary_reports_navigation_and_requests() -> None:
    shell = TkShell(width=640, height=480)

    result, _frame = shell.render_url_to_frame(Path("tests/fixtures/sites/basic_links.html").resolve().as_uri())
    summary = shell.page_summary(result)

    assert "html" in summary
    assert "3 link(s)" in summary
