# Work Done by Claude - 2026-08-29

## Summary

Landed the in-flight interactive-shell slice, closed P0 by automating
GUI smoke verification — and used it to find and fix six rendering bugs
that unit tests could not see — then took the top post-sweep backlog
item, iframes.

The through-line: the Tk shell was the one subsystem no test reached, so
defects that only show up as pixels had been accumulating. Four of the
six rendering bugs below were found by looking at screenshots, not by
reasoning about the code — and the sixth, the missing margin collapse,
was found while reading iframe layout output for something else.

## Commits

1. `c1e4bb0` — **tk+layout: real font metrics, hit regions, interactive
   form controls.** This was uncommitted work already in the tree; I
   verified it on a virtual display and committed it as found.
2. `f05eb65` — **document: collapse inline whitespace instead of
   discarding it.** `</a> <a>` rendered as one word; adjacent form
   controls touched.
3. `1814e84` — **styles+tests: paint links as links, skip test262
   without a corpus.** Anchors were indistinguishable from body text.
   `pytest -q` now passes from a clean checkout.
4. `01084cf` — **document/bfc: one text run per inline box per line.**
   A link's underline broke at every space and those gaps were not
   clickable.
5. `0063608` — **render: stop re-aligning text in the rasterizer.** A
   centered heading painted its words on top of each other.
6. `6fcae99` — **document/bfc: a text box cannot be floated.** Float
   contents did not wrap and painted over the text beside them.
7. `05abb1c` — **tools: automate GUI smoke verification.**
8. `da9dd7a` — **styles: resolve em/rem lengths, UA block margins.**
9. `7fec761` — **core+layout: render iframes as nested browsing
   contexts.** Backlog item #1. `FrameBudget` caps depth and count;
   `content.iframes.enabled` is the first content toggle with an engine
   behind it.
10. `f568ffc` — **document/bfc: collapse a first child's top margin
    through its parent.** Every page's first heading sat flush against
    the top of the content area — the UA margins in (8) were only half
    delivered without this.

## Files Changed

- `neuzelaar/document/box.py`, `neuzelaar/document/bfc.py` — whitespace
  collapsing, inline run merging, inline-context predicate
- `neuzelaar/document/styles.py` — `a[href]` UA rule, `em`/`rem`
  resolution, CSS 2.1 appendix D block margins
- `neuzelaar/render/{software,display_list,display_builder}.py` —
  removed per-op text alignment; placeholder label prefix moved to
  layout
- `neuzelaar/core/page.py` — `FrameBudget`, `FrameAsset`, nested frame
  loading; `_prepare` is nesting-aware
- `neuzelaar/shells/tk/shell.py` — iframe toggle wired to the loader
- `tools/gui_smoke.py`, `docs/gui_smoke.md` — new
- `TODO.md`, `docs/layout_plan.md`, `README.md` — status and stale
  claims
- tests: `test_ifc`, `test_floats`, `test_styles`, `test_positioning`,
  `test_polish`, `test_bfc`, `test_js_test262`, and a new `test_iframes`
- fixtures: `iframe_page`, `iframe_child`, `iframe_default_size`,
  `self_framing`, `third_party_iframe`

## Tests Run

- `.venv/bin/pytest -q`: 609 passed, 9 skipped
- `tools/check_guardrails.sh`: pass
- `.venv/bin/python tools/gui_smoke.py`: 14/14 scenarios pass

Note for whoever sets up next: this box had no `.venv` and no
`python3-tk`. `tools/setup.sh` builds the venv; the Tk shell and its
tests additionally need `sudo apt-get install python3-tk`, plus `xvfb`
and (optionally) `xdotool` for `gui_smoke.py`.

## Design Notes

- **Whitespace collapsing belongs to the inline formatting context, not
  to a text node.** The space between `</a>` and `<a>` is its own text
  node, and the space ending one node merges with the space starting
  the next. `box.py` now keeps a collapsed space rather than stripping
  the node away; `bfc.py` folds those into a leading space on the next
  fragment after the whole context is flattened, so nesting depth does
  not matter. Runs between block-level siblings are still dropped, but
  by `_wrap_anonymous_blocks`, which is where CSS 2.1 9.2.1.1 puts them.
- **Fragments now carry two identities.** `node_id` is the nearest
  interactive ancestor (for hit testing); `inline_id` is the innermost
  inline box (for joining a box's words into one run). Keeping them
  separate is what lets `<a><strong>x</strong></a>` merge as a `strong`
  run while still hit-testing as the anchor.
- **Alignment is a layout decision.** `DrawText` used to carry `align`
  and `max_width`, from when a paragraph was a single placement. With
  a real IFC that became a second, per-word alignment pass. Removed.
- **A TEXT box has no style of its own** — it borrows its parent's.
  Anything that asks a box for a property that only elements can have
  (`float`, and by the same logic `position`) must exempt TEXT. This
  bit us once; it is worth remembering before the next such guard.
- **Computed values should be absolute lengths.** Layout can resolve a
  percentage because it knows the containing block; it has no font
  context. So `em`/`rem` resolve in the cascade, not in `bfc`.
- **An iframe splits cleanly across the two layers.** `bfc` emits a
  `FramePlacement` and stops at the frame's edge; `document.layout`
  owns the recursion, because that is where `layout_document` lives.
  No display-list changes were needed — clip push/pop already existed.
- **Frame content loses its node ids on the way out.** They address the
  nested document and the display builder resolves ids against the
  top-level one, so letting them through would make a click inside a
  frame navigate the parent page.
- **Frame caps are security, not tuning.** `self_framing.html` in the
  fixtures is a page that iframes itself; the depth cap is what stops
  it. Do not raise these without thinking about it.

## Risks / Follow-Ups

- **UA margins moved every page.** Three tests had encoded their
  absence and were updated. If a fixture looks wrong now, suspect an
  author stylesheet that assumed no UA margin rather than a layout bug.
- **`:visited` deliberately absent.** Do not add it — it is a history
  leak. If someone asks for visited-link styling, that is a policy
  conversation, not a CSS one.
- **`gui_smoke.py` has no golden images.** It proves the window lives
  and paints, not that it paints correctly; a human still reads the
  screenshots. Baselines are worth adding once layout stops moving.
  Clicks are not scriptable yet because the shell does not expose the
  canvas origin — exposing it is the small change that would unlock
  scripted link/form scenarios.
- **`rem` uses the root element's computed font size**, which is the
  first element walked. That is right for normal documents; it would be
  wrong if a document ever had no root element style.
- **Bottom margins still do not collapse through a parent.** Top
  margins now do. The asymmetry only affects total document height, not
  where anything is painted, but it should be closed.
- **Replaced boxes do not paint borders.** `iframe { border: 1px solid }`
  in the fixture has no effect, and the same is true for `img`. Worth a
  small slice of its own.
- **Interaction inside a frame does nothing.** Links and forms in a
  nested context are inert by design until the frame gets its own hit
  testing. `sandbox` is likewise unimplemented — when it lands it maps
  onto the existing capability model rather than inventing a parallel
  one.
- **Lists skip the spec's 40px `padding-left`** because our marker
  gutter already indents them. If the marker gutter is ever replaced
  with real markers in padding, add the padding back in the same commit
  or lists will lose their indent.
