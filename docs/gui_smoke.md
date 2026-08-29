# GUI smoke verification

`TODO.md` P0 asked for the Tk shell to be run "on a machine with a
working display" and for the results to be recorded. This documents how
that is done and what the current run found.

## How to run it

No physical display is required — Xvfb is enough, and it is what CI
would use.

```sh
sudo apt-get install -y python3-tk xvfb xdotool   # xdotool optional
.venv/bin/python tools/gui_smoke.py
```

Screenshots and per-scenario logs land in `artifacts/gui_smoke/`
(git-ignored). Exit status is non-zero if any scenario fails, so the
script is usable as a CI gate.

Useful flags:

- `--only <name>` — run one scenario while iterating on a fix.
- `--keep` — leave Xvfb up so you can attach or re-grab the screen.
- `--display :N`, `--geometry WxHxD`, `--settle SECONDS`.

## What each scenario checks

Per fixture, the script launches `python -m neuzelaar.viewer`, waits for
the window to paint, and asserts:

| Check | Catches |
|---|---|
| window stayed open | crash on window construction |
| no traceback | exceptions during load, layout, or paint |
| page load finished | the load trace reached its terminal phase |
| browser pane painted | a blank or all-chrome window |
| scrolling repaints | a canvas that does not follow the scrollbar |

The pane check samples only the right-hand 45% of the screen so that
window chrome cannot satisfy it on its own. The scroll check is skipped
when `xdotool` is absent, and when nothing moved — a short page has
nothing to scroll and that is not a failure.

These are liveness checks, not pixel comparisons. There is no golden
image baseline; the screenshots exist so a human can look. That is a
deliberate limit — see below.

## Run of 2026-08-29

14/14 scenarios passed on Xvfb at 1920x1200x24, Python 3.14, Tk 8.6.

Fixtures covered: `example`, `basic_links`, `basic_lists`,
`basic_images`, `basic_form`, `styled_page`, `inline_flow`,
`float_layout`, `positioning`, `overflow`, `nested_blocks`,
`text_alignment`, `iframe_page`, `third_party_script`.

Verified by eye from the screenshots:

- Pages are visible, scroll, and do not overlap window chrome.
- Links paint blue and underlined, with the underline continuous across
  the whole anchor.
- Form controls render as real ttk widgets over their hit regions;
  clicking a link navigates and Back/Forward light up; submitting a
  form posts the edited values.
- Floated callouts contain their own text, and body text flows around
  them and clears below them.
- `text-align: center | right` place lines correctly.
- An iframe renders its nested document with that document's own
  styles and background, clipped to the frame box, with parent text
  flowing before and after it. Turning the Iframes toggle off reloads
  the page with the frame as a placeholder.
- List markers, image placeholders, and the blocked-subresource counter
  all render.

Three rendering bugs were found by looking at the first run's
screenshots and are fixed:

- whitespace between adjacent inline elements was dropped, so
  `</a> <a>` rendered as one word and adjacent form controls touched
- the rasterizer re-applied `text-align` per draw op, stacking every
  word of a centered heading on the same point
- a floated block's own text did not wrap, because the guard for "these
  children form one inline formatting context" asked a TEXT box for its
  `float` — and a TEXT box borrows its parent's style

## Known gaps

- **No golden images.** Pixel baselines would catch regressions the
  liveness checks cannot, but they are also brittle across font and Tk
  versions. Worth doing once the layout engine stops moving; the
  screenshots this script already writes are the raw material.
- **Interaction is barely driven.** Only Page Down is sent. Clicking a
  link or submitting a form is verified by hand today, because mapping
  a page coordinate to a screen coordinate needs the canvas origin,
  which the shell does not expose. Exposing it would make click
  scenarios scriptable.
- **One window size.** Reflow at other widths is covered by unit tests,
  not here.
