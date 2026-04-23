from pathlib import Path

from neuzelaar.shells.headless.shell import HeadlessShell


def test_headless_shell_formats_page_result() -> None:
    shell = HeadlessShell()
    result = shell.open_url(Path("tests/fixtures/sites/example.html").resolve().as_uri())

    output = shell.format_result(result)

    assert output.startswith("200 file://")
    assert "[html]" in output
    assert "# Example Fixture" in output


def test_headless_shell_formats_blocked_subresource() -> None:
    shell = HeadlessShell()
    result = shell.open_url(Path("tests/fixtures/sites/third_party_script.html").resolve().as_uri())

    output = shell.format_result(result)

    assert "[block] script https://cdn.third-party.test/app.js" in output
