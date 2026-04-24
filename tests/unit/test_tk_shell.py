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


def test_tk_shell_normalize_address_defaults_blank_to_example() -> None:
    shell = TkShell(width=640, height=480)

    assert shell.normalize_address("") == "https://example.com"


def test_tk_shell_default_split_position_centers_view() -> None:
    shell = TkShell(width=640, height=480)

    assert shell.default_split_position(1720) == 860
    assert shell.default_split_position(500) == 320


def test_tk_shell_normalize_address_defaults_web_input_to_https() -> None:
    shell = TkShell(width=640, height=480)

    assert shell.normalize_address("msn.com") == "https://msn.com"
    assert shell.normalize_address("example.com/path") == "https://example.com/path"


def test_tk_shell_normalize_address_keeps_local_paths_local() -> None:
    shell = TkShell(width=640, height=480)

    normalized = shell.normalize_address("tests/fixtures/sites/example.html")

    assert normalized.startswith("file:///")
    assert normalized.endswith("/tests/fixtures/sites/example.html")


def test_tk_shell_requests_text_reports_blocked_and_allowed_requests() -> None:
    shell = TkShell(width=640, height=480)

    blocked_result, _ = shell.render_url_to_frame(Path("tests/fixtures/sites/third_party_script.html").resolve().as_uri())
    allowed_result, _ = shell.render_url_to_frame(Path("tests/fixtures/sites/linked_styles.html").resolve().as_uri())

    blocked = shell.requests_text(blocked_result)
    allowed = shell.requests_text(allowed_result)

    assert "[block] script https://cdn.third-party.test/app.js" in blocked
    assert "[allow] stylesheet" in allowed


def test_tk_shell_source_text_returns_html_source() -> None:
    shell = TkShell(width=640, height=480)
    result, _ = shell.render_url_to_frame(Path("tests/fixtures/sites/example.html").resolve().as_uri())

    source = shell.source_text(result)

    assert "<title>Example Fixture</title>" in source


def test_tk_shell_error_report_includes_context() -> None:
    shell = TkShell(width=640, height=480)
    shell.render_url_to_frame(Path("tests/fixtures/sites/example.html").resolve().as_uri())

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        report = shell.error_report(exc)

    assert "current_url:" in report
    assert "error_type: RuntimeError" in report
    assert "error: boom" in report
    assert "RuntimeError: boom" in report


def test_tk_shell_write_error_report_creates_latest_and_timestamped_log(tmp_path: Path) -> None:
    shell = TkShell(width=640, height=480, log_dir=tmp_path)

    path = shell.write_error_report("sample report")

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "sample report\n"
    latest = tmp_path / "latest.log"
    assert latest.exists()
    assert latest.read_text(encoding="utf-8") == "sample report\n"
