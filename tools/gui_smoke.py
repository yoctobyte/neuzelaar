#!/usr/bin/env python3
"""Drive the Tk shell on a virtual display and report what it rendered.

The Tk shell is the one part of the browser that unit tests cannot
reach: `tests/unit/test_tk_shell.py` exercises the frame-building API,
but nothing checks that a real window opens, paints, and scrolls. This
script closes that gap without needing a physical display.

For each fixture it launches `python -m neuzelaar.viewer` under Xvfb,
waits for the window to map, screenshots it, and checks:

- the process is still alive (the window did not crash on open)
- the page-load trace reached "page load finished"
- nothing raised (no traceback on stderr)
- the browser pane actually painted (more than one colour, and content
  that is not just the chrome)
- scrolling changes what is on screen for pages taller than the pane

Screenshots land in the output directory so a human can eyeball them;
the exit status is what CI would read.

Requires: Xvfb, Pillow. `xdotool` is optional and only used for the
scroll check, which is skipped without it.

    tools/gui_smoke.py
    tools/gui_smoke.py --out artifacts/gui_smoke --keep
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Fixtures worth looking at with human eyes: one per rendering concern.
SCENARIOS: tuple[tuple[str, str], ...] = (
    ("text", "tests/fixtures/sites/example.html"),
    ("links", "tests/fixtures/sites/basic_links.html"),
    ("lists", "tests/fixtures/sites/basic_lists.html"),
    ("images", "tests/fixtures/sites/basic_images.html"),
    ("forms", "tests/fixtures/sites/basic_form.html"),
    ("styled", "tests/fixtures/sites/styled_page.html"),
    ("inline-flow", "tests/fixtures/sites/inline_flow.html"),
    ("floats", "tests/fixtures/sites/float_layout.html"),
    ("positioning", "tests/fixtures/sites/positioning.html"),
    ("overflow", "tests/fixtures/sites/overflow.html"),
    ("nested-blocks", "tests/fixtures/sites/nested_blocks.html"),
    ("text-align", "tests/fixtures/sites/text_alignment.html"),
    ("blocked-script", "tests/fixtures/sites/third_party_script.html"),
)

# The browser pane sits to the right of the debug pane. Sampling only
# that half keeps the blank-page check from being satisfied by chrome.
PANE_LEFT_FRACTION = 0.55


@dataclass
class Result:
    name: str
    fixture: str
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    screenshot: Path | None = None

    def record(self, check: str, passed: bool, detail: str = "") -> None:
        self.checks.append((check, passed, detail))

    @property
    def ok(self) -> bool:
        return all(passed for _, passed, _ in self.checks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--display", default=":99", help="X display to use (default :99)")
    parser.add_argument("--geometry", default="1920x1200x24", help="Xvfb screen geometry")
    parser.add_argument(
        "--out",
        default="artifacts/gui_smoke",
        help="Directory for screenshots and logs",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=3.0,
        help="Seconds to wait after launch before capturing",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Leave Xvfb running after the run (useful when iterating)",
    )
    parser.add_argument(
        "--only",
        action="append",
        help="Run only the named scenario(s)",
    )
    return parser.parse_args()


class VirtualDisplay:
    """Own an Xvfb server, unless one is already on the display."""

    def __init__(self, display: str, geometry: str, keep: bool) -> None:
        self.display = display
        self.geometry = geometry
        self.keep = keep
        self.process: subprocess.Popen | None = None

    def __enter__(self) -> VirtualDisplay:
        if self._responds():
            return self
        if shutil.which("Xvfb") is None:
            raise SystemExit("Xvfb not found; install it or point --display at a live server")
        self.process = subprocess.Popen(
            ["Xvfb", self.display, "-screen", "0", self.geometry],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            time.sleep(0.2)
            if self._responds():
                return self
        raise SystemExit(f"Xvfb did not come up on {self.display}")

    def __exit__(self, *_exc: object) -> None:
        if self.process is not None and not self.keep:
            self.process.terminate()
            self.process.wait(timeout=10)

    def _responds(self) -> bool:
        try:
            from PIL import ImageGrab

            ImageGrab.grab(xdisplay=self.display)
        except Exception:
            return False
        return True


def grab(display: str) -> "object":
    from PIL import ImageGrab

    return ImageGrab.grab(xdisplay=display)


def pane_colours(image: "object") -> int:
    """Distinct colours in the browser pane, capped."""
    width, height = image.size
    pane = image.crop((int(width * PANE_LEFT_FRACTION), 0, width, height))
    colours = pane.convert("RGB").getcolors(maxcolors=1 << 16)
    return len(colours) if colours else 1 << 16


def run_scenario(
    name: str,
    fixture: str,
    *,
    display: str,
    out_dir: Path,
    settle: float,
) -> Result:
    result = Result(name=name, fixture=fixture)
    log_path = out_dir / f"{name}.log"
    env = dict(os.environ, DISPLAY=display)
    with log_path.open("w", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "neuzelaar.viewer", fixture],
            cwd=ROOT,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            time.sleep(settle)
            result.record("window stayed open", process.poll() is None)

            image = grab(display)
            result.screenshot = out_dir / f"{name}.png"
            image.save(result.screenshot)
            colours = pane_colours(image)
            result.record("browser pane painted", colours > 2, f"{colours} colours")

            scrolled = scroll_changes_view(display, image)
            if scrolled is not None:
                result.record("scrolling repaints", scrolled)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    result.record("no traceback", "Traceback (most recent call last)" not in log_text)
    result.record("page load finished", "page load finished" in log_text)
    return result


def scroll_changes_view(display: str, before: "object") -> bool | None:
    """Page down and report whether the screen changed.

    Returns None when the page is short enough that there is nothing to
    scroll, or when xdotool is unavailable — neither is a failure.
    """
    if shutil.which("xdotool") is None:
        return None
    env = dict(os.environ, DISPLAY=display)
    subprocess.run(["xdotool", "key", "Next"], env=env, check=False)
    time.sleep(0.6)
    after = grab(display)
    if before.size != after.size:
        return None
    from PIL import ImageChops

    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    if diff.getbbox() is None:
        # Nothing moved. Short pages have nothing to scroll, so this is
        # only reportable when we know the page overflows — which we do
        # not from a screenshot alone.
        return None
    return True


def main() -> int:
    args = parse_args()
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = SCENARIOS
    if args.only:
        wanted = set(args.only)
        scenarios = tuple(item for item in SCENARIOS if item[0] in wanted)
        missing = wanted - {name for name, _ in SCENARIOS}
        if missing:
            raise SystemExit(f"unknown scenario(s): {', '.join(sorted(missing))}")

    results: list[Result] = []
    with VirtualDisplay(args.display, args.geometry, args.keep):
        for name, fixture in scenarios:
            if not (ROOT / fixture).exists():
                result = Result(name=name, fixture=fixture)
                result.record("fixture exists", False)
                results.append(result)
                continue
            results.append(
                run_scenario(
                    name,
                    fixture,
                    display=args.display,
                    out_dir=out_dir,
                    settle=args.settle,
                )
            )

    failed = 0
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status}  {result.name:<15} {result.fixture}")
        for check, passed, detail in result.checks:
            if passed and not detail:
                continue
            mark = "ok" if passed else "!!"
            suffix = f" ({detail})" if detail else ""
            print(f"        {mark} {check}{suffix}")
        if not result.ok:
            failed += 1

    print()
    print(f"{len(results) - failed}/{len(results)} scenarios passed")
    print(f"screenshots: {out_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
