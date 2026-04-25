# Layout engine plan

Durable reference for the layout sweep that replaces the current
recursive walker with a real CSS 2.1 visual formatting model behind
a box-tree abstraction. Referenced from `TODO.md`. Update this doc
when the plan changes; do not bury the rationale in chat history.

## Goal

One coherent architectural shift: DOM + ComputedStyle → **BoxTree**
→ layout algorithms → existing `LayoutResult` primitives. The
output shape and display-builder stay unchanged; the internals are
replaced.

## Scope of the sweep

- **Box tree**: every element becomes a box with display type, real
  box model (content / padding / border / margin), and a formatting
  context. Anonymous boxes where block + inline siblings mix.
- **Block Formatting Context (BFC)**: proper vertical stacking,
  margin collapse, real widths/heights including `%` / `auto`.
  Supports `box-sizing: content-box | border-box`.
- **Inline Formatting Context (IFC)**: line boxes, word wrap at
  content-box edges, `display: inline` flowing through UA defaults
  for `<a>` / `<strong>` / `<em>` / `<span>` / `<code>` / etc.
- **Floats**: `float: left | right`, `clear: left | right | both`.
  Line boxes shrink around float exclusions.
- **Positioning**: `position: static | relative | absolute | fixed`
  with correct containing-block resolution.
- **Overflow + clipping**: `overflow: visible | hidden | auto | scroll`.
- **Stacking basics**: `z-index` and stacking-context creation.

## Commits in the sweep

- **A1** — Box tree types and DOM-to-tree construction. ✓
- **A2** — BFC with margin collapse and real box model. ✓
- **B** — IFC: line boxes, word wrap, `display: inline`. ✓
- **C** — Floats + `clear`. ✓
- **D** — Positioning: relative, absolute, fixed, containing block. ✓
- **E** — Overflow + clipping (visible / hidden / scroll-as-hidden /
  auto-as-hidden). Real scrollbar UI deferred. ✓
- **F** — Polish: z-index for positioned content, right/bottom on
  absolute boxes, fixtures and tests. ✓

The sweep is closed. Remaining layout-adjacent work moves to the
post-sweep backlog below.

## Out of scope (deferred, listed so they are not forgotten)

Each is a later named slice of its own, post-sweep. Order there is
flexible.

- **Tables** (`<table>` / `<tr>` / `<td>` / `display: table*`).
  Their own layout algorithm: column sizing, row layout, cell spans,
  caption placement. Currently render as naive block stack — good
  enough to stay readable, wrong for tabular data. Keep in mind when
  building the box tree: table tags should already map to a `table`
  display kind so we can plug the real algorithm in without another
  restructure.
- **Iframes** (`<iframe>`, nested browsing contexts). HTML5 has
  `<iframe>` only; `<frame>` / `<frameset>` / `<noframes>` were
  removed from HTML5 and we deliberately never support them. An
  iframe is a replaced inline-block box hosting a nested
  `PageLoadResult` — recursion, with its own origin / cookies /
  capabilities. `FetchReason.IFRAME` already exists and Strict
  already blocks cross-origin iframes, so iframe blocking is
  already a usable ad-blocker toggle today. The `sandbox`
  attribute will map onto the existing capability model when the
  slice lands.
- **Flex** (`display: flex`). Separate formatting algorithm.
- **Grid** (`display: grid`). Separate formatting algorithm.
- **Transforms / animations** (`transform`, `@keyframes`, CSS
  transitions). CSS3+ concerns.
- **Pseudo-classes / pseudo-elements** (`:hover`, `:focus`,
  `::before`, `::after`). Later; needs event loop integration for
  state-based ones.
- **Advanced selectors**: child combinator `>`, adjacent-sibling
  `+`, general-sibling `~`, attribute selectors (`[type="text"]`),
  `:nth-child(n)`. Current selector support is tag / class / id +
  descendant. Small follow-up slice.
- **Units**: `calc()`, viewport units (`vh` / `vw` / `vmin` /
  `vmax`), `min()` / `max()` / `clamp()` functions, `ch` / `ex`.
- **RTL / writing modes** (`direction: rtl`, `writing-mode: vertical-*`).
  We only support LTR / horizontal-tb for now.
- **Text**: `text-decoration`, `text-transform`, `word-break`,
  `hyphens`, full `white-space` nuances. Basic support only.
- **Generated content**: `content:`, CSS counters.
- **Custom properties / variables** (`--foo`, `var()`).
- **Media queries** (`@media`).
- **`@import`, `@font-face`, `@supports`, `@keyframes`**.
- **`frame` / `frameset`**: removed from HTML5. Will never be
  supported.

## Design principles

- **Textbook CSS 2.1.** Faithful implementation of the visual
  formatting model. Shortcuts here rot fast and the spec is not
  dramatically more code than a fake.
- **Box tree first, then algorithms.** Every positioning feature
  attaches cleanly to the box tree; none attach cleanly to the
  current DOM walker. Resist the urge to special-case.
- **Output shape is a public contract.** `LayoutResult` /
  `LayoutText` / `LayoutImage` / `LayoutBox` stay. Display builder
  and rasterizer do not change during the sweep.
- **Anonymous boxes in Commit A.** When block and inline siblings
  mix, CSS wraps inline runs in anonymous block boxes. Cheap to
  get right up-front; expensive to retrofit once B / C / D depend
  on the box tree.
- **Each commit ships green.** A partial sweep that breaks tests is
  worse than slower progress.

## Known-subtle areas

- **Margin collapse** between vertical siblings and between
  parent / first-child (and last-child). Does not collapse through
  padding / border / clearance.
- **Float + line-box interaction**: line boxes narrow around float
  exclusions on the same line. IFC therefore consults float state
  computed in the containing BFC.
- **Containing-block resolution**. `absolute` → nearest positioned
  ancestor. `fixed` → viewport. `relative` children of a `relative`
  parent form the containing block for absolute descendants.
- **Stacking contexts**. `position != static` with non-`auto`
  `z-index` creates a stacking context; later: `opacity < 1`,
  `transform`, etc.
- **% resolution** depends on containing-block size, which can be
  block-width or block-height depending on property (width vs
  height).

## Security / policy angle

- **Iframe blocking** is already effective under Strict profile via
  `FetchReason.IFRAME`. Blocking iframes is a legitimate
  ad-blocker vector and a standing affordance for privacy-minded
  users. When iframes land, the `sandbox` attribute plugs into
  the capability model rather than inventing a parallel concept.
- **Overflow clipping** is a privacy concern as well as layout:
  clipped content must not leak via side channels (e.g. text
  measurement in ways that expose hidden content to scripts once
  scripts run).
- **Stacking / z-index**: overlays must not let cross-origin
  content occlude legitimate UI (clickjacking). We will not
  implement cross-origin occlusion defenses in this sweep, but
  they belong in the iframe / frame-ancestor policy slice.

## Post-sweep backlog (ordered roughly by expected value)

1. Iframes (nested browsing contexts + `sandbox`)
2. Selector upgrades (combinators, attribute selectors, `:nth-*`)
3. Tables (real table algorithm)
4. Flex
5. Grid
6. Pseudo-classes / pseudo-elements
7. Media queries + `@import`
8. Transforms / animations
9. Custom properties
10. RTL / writing-modes
