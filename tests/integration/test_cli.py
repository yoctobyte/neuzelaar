import subprocess
import sys
from pathlib import Path


def test_cli_renders_local_fixture() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "neuzelaar", "tests/fixtures/sites/example.html"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "[html]" in result.stdout
    assert "# Example Fixture" in result.stdout
    assert "Example Domain" in result.stdout


def test_cli_reports_blocked_subresource() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "neuzelaar", "tests/fixtures/sites/third_party_script.html"],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "[block] script https://cdn.third-party.test/app.js" in result.stdout


def test_cli_accepts_file_uri() -> None:
    fixture = Path("tests/fixtures/sites/example.html").resolve().as_uri()
    result = subprocess.run(
        [sys.executable, "-m", "neuzelaar", fixture],
        check=True,
        text=True,
        capture_output=True,
    )

    assert fixture in result.stdout
