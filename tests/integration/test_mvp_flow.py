from pathlib import Path

from neuzelaar.core.session import BrowserSession
from neuzelaar.shells.console.shell import ConsoleShell
from neuzelaar.shells.tk.shell import TkShell


def fixture(name: str) -> str:
    return str(Path(f"tests/fixtures/sites/{name}"))


def test_mvp_console_navigation_forms_and_resources() -> None:
    shell = ConsoleShell()

    opened = shell.run_command(f"open {fixture('basic_links.html')}")
    links = shell.run_command("links")
    followed = shell.run_command("follow 2")
    back = shell.run_command("back")

    assert "Links Test" in opened
    assert "Relative Link" in links
    assert "Example Domain" in followed
    assert "Links Test" in back


def test_mvp_session_get_form_flow() -> None:
    session = BrowserSession()
    session.open_url(fixture("basic_form.html"))

    result = session.submit_form(1, {"q": "mvp"})

    assert "Form Result" in result.rendered_text
    assert "q=mvp" in result.resource.final_url


def test_mvp_tk_shell_produces_visual_frame_without_display() -> None:
    result, frame = TkShell(width=640, height=480).render_url_to_frame(fixture("styled_page.html"))

    assert result.root_style.background_color == "#eeeeee"
    assert frame.width == 640
    assert frame.height > 0
