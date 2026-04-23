from pathlib import Path

from neuzelaar.shells.console.shell import ConsoleShell


def fixture_path(name: str) -> str:
    return str(Path(f"tests/fixtures/sites/{name}"))


def test_console_open_and_links() -> None:
    shell = ConsoleShell()

    output = shell.run_command(f"open {fixture_path('basic_links.html')}")
    links = shell.run_command("links")

    assert "Links Test" in output
    assert "3 link(s)" in output
    assert "2. Relative Link" in links
    assert "example.html" in links


def test_console_follow_back_forward() -> None:
    shell = ConsoleShell()
    shell.run_command(f"open {fixture_path('basic_links.html')}")

    followed = shell.run_command("follow 2")
    back = shell.run_command("back")
    forward = shell.run_command("forward")

    assert "Example Domain" in followed
    assert "Links Test" in back
    assert "Example Domain" in forward


def test_console_resources_reports_blocked_script() -> None:
    shell = ConsoleShell()
    shell.run_command(f"open {fixture_path('third_party_script.html')}")

    output = shell.run_command("resources")

    assert "[block] script https://cdn.third-party.test/app.js" in output


def test_console_permissions_reports_blocked_script_capability() -> None:
    shell = ConsoleShell()

    opened = shell.run_command(f"open {fixture_path('inline_script.html')}")
    output = shell.run_command("permissions")

    assert "1 active content request(s)" in opened
    assert "1. [requested] [blocked] exec_inline_js inline" in output
    assert "JavaScript execution is disabled" in output


def test_console_can_grant_script_permission_without_enabling_execution() -> None:
    shell = ConsoleShell()
    shell.run_command(f"open {fixture_path('inline_script.html')}")

    granted = shell.run_command("grant 1 origin")
    reloaded = shell.run_command("reload")
    permissions = shell.run_command("permissions")

    assert "1. [granted] [blocked] exec_inline_js inline" in granted
    assert "1 active content request(s)" in reloaded
    assert "1. [granted] [blocked] exec_inline_js inline" in permissions


def test_console_reports_command_errors() -> None:
    shell = ConsoleShell()

    assert shell.run_command("back") == "error: No previous history entry"
    assert shell.run_command("follow nope") == "usage: follow <link-number>"
    assert shell.run_command("wat") == "unknown command: wat"


def test_console_supports_tab_commands() -> None:
    shell = ConsoleShell()

    created = shell.run_command("newtab tests/fixtures/sites/example.html")
    tabs = shell.run_command("tabs")
    switched = shell.run_command("switch 1")

    assert "Example Domain" in created
    assert "1:" in tabs
    assert "Example Domain" in switched or "tab 1 active" in switched
