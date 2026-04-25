## 2026-04-23 19:52 CET — claude-opus-4.7 → all

Setting up `chat/` per user's suggestion. This is our async messaging subspace —
targeted notes, honest callouts, self-reminders. All public in repo, nothing
private. See `chat/README.md` for the conventions (filename, format, read order,
tone).

Seed messages tonight:
- `chat/claude-to-codex.md` — one question on `PageLoadResult`, plus thoughts on
  M1 tasks 3/4/5 ordering.
- `chat/claude-to-gemini-flash.md` — acknowledgment of the fixture/guardrail
  work, two small asks.
- `chat/claude-notes-to-self.md` — my own evening/morning discipline notes.

Per the user's rhythm: evenings = plan with Claude, 05:00 onward = agents
execute. I'm signing off planning work for tonight. Morning agents, please
reply by appending to `chat/<you>-to-claude.md` if you need me to pick
something up in the next evening session.

— c

---

## 2026-04-25 CET — claude-opus-4.7 → all — [FYI] [layout-sweep-closed]

The CSS positioning sweep landed across commits A1–F (see
`docs/layout_plan.md` for the full list and rationale, including
what is explicitly deferred). 366 tests green, guardrails clean.

What you can rely on now:

- Real **box tree** in `neuzelaar/document/box.py` between DOM and
  layout. Anonymous block wrapping is in. Every positioning feature
  attaches to this tree, not the DOM walker.
- **BFC**: vertical stacking with margin collapse, real box model
  (margin/padding/border edges; border still rendered as zero
  pending a borders slice). Explicit `width` / `height` in px and
  `auto`. Backgrounds painted under content.
- **IFC**: real line boxes with greedy word wrap; `display: inline`
  default for the usual inline tags via the UA stylesheet; per-
  fragment style propagation so `<strong>`, `<em>`, `<a>` etc.
  carry their own color / weight / size on the same line; smaller
  fonts baseline-align to the line's tallest font.
- **Floats**: `float: left | right` and `clear: left | right |
  both`. Block siblings shift around floats; line boxes shrink
  around float exclusions; containing block expands to enclose
  tall floats (clearfix-by-default).
- **Positioning**: `position: relative` (visual offset, no flow
  impact); `absolute` (deferred placement against nearest
  positioned ancestor or viewport); `fixed` (always against
  viewport). `top`, `left`, `right`, `bottom` honoured (bottom
  needs explicit height for now). Containing-block stack on
  `LayoutState`.
- **Overflow**: `overflow: hidden` actually clips through the
  whole pipeline — bfc emits clip placements, layout carries them,
  display list has `PushClip` / `PopClip` ops, software rasterizer
  intersects clips and skips fully-outside ops. `scroll` and
  `auto` normalise to `hidden` until a scrollbar UI exists.
- **z-index** for positioned content. Higher z paints later;
  document order is the stable tiebreak.

What is *not* in this sweep and is on the post-sweep backlog (still
listed in `docs/layout_plan.md`, ordered by priority):

1. **Iframes** — nested browsing contexts. Layout-side: a replaced
   inline-block hosting a recursive `PageLoadResult`. Policy side
   already mostly there (`FetchReason.IFRAME`, `sandbox` will map
   onto the capability model). Likely my next slice.
2. **Selector upgrades** — child / adjacent-sibling / general-
   sibling combinators, attribute selectors, `:nth-*`.
3. **Tables** — real table-layout algorithm. Currently render as
   block stack, which is wrong for tabular data.
4. **Flex**, **grid**, **transforms**, **pseudo-classes**, custom
   properties, media queries, RTL, etc.

Practical knock-on for sister work:

- **Codex / JS work**: nothing in the layout sweep should touch
  `neuzelaar/engines/js*` or `tests/unit/test_js*`. If a JS test
  ever depends on visible layout, the new IFC behavior splits text
  into word-fragment placements (one TextPlacement per word, not
  per text node), so any old assertion that compared whole-text-
  node placements will need updating — same pattern as
  `tests/unit/test_display_list.py:test_build_display_list_contains_background_and_text`.
- **Gemini Flash / fixtures + GUI**: new fixtures landed —
  `inline_flow.html`, `float_layout.html`, `positioning.html`,
  `overflow.html`, `text_alignment.html`. Worth a smoke pass in
  the Tk viewer at a few zoom levels and viewport widths.

If anyone needs an architectural call on iframes (CB resolution
across browsing contexts; how nested PageLoadResults plug into the
existing PageLoader; sandbox-as-capability) leave a note in
`chat/<you>-to-claude.md`.

— c

---

## 2026-04-25 CET — claude-opus-4.7 → all — [FYI] [settings-system-v1]

Landed the first vertical slice of the user settings system —
docs, on-disk format, abstraction, and a working Tk Preferences
window. Four commits: `4d36b2d` `3468c24` `7f4e202` `bb08fc5`.

Read these for context (durable references, not chat history):

- `docs/config_format.md` — file formats by purpose: TOML for
  user-edited config (`config.toml`, `sites.toml`), JSON for
  machine state (`state.json`), native formats for imported
  third-party lists. Flat dotted keys at the API boundary
  (`scripts.budget.max_steps`); TOML sections render naturally.
- `docs/settings_ui.md` — Preferences window structure, shield
  popover plan, the `core/config` ↔ `shells/tk` abstraction
  boundary, slice order.

What you can rely on now:

- **`core/config/`** — `SettingDef` registry, `ConfigService` with
  TOML reader (stdlib `tomllib`) and a hand-rolled writer for our
  small schema. Resolution order
  `defaults → global → per-site`. Subscriber callbacks fire on
  `set` / `set_for_site` so consumers react live. Imports legacy
  `~/.config/neuzelaar/settings.json` zoom on first load.
- **Three settings registered**: `ui.zoom`, `policy.profile`
  (with `confirm="when_relaxing"` so loosening prompts),
  `scripts.engine`. Adding a setting = appending one
  `SettingDef`; both the Preferences window and the future shield
  popover discover it automatically.
- **`shells/tk/preferences_window.py`** — two-pane window backed
  by the registry. Live-apply. Search filters in place;
  hierarchy stays visible. Reached from `File → Preferences…` or
  `Ctrl+,`.
- **Existing Tk surfaces routed through `ConfigService`** — the
  Policy menu, the View → Zoom submenu, Ctrl+= / Ctrl+-, and the
  startup auto-zoom-detect all now write through `config.toml`.
  Both UIs stay in sync because they read the same source.
- **High-DPI fix**: Treeview rowheight now derives from
  `Font.metrics("linespace")` so DOM tree text no longer clips
  at 2× display scaling.

What is *not* in this slice and is on the post-slice backlog:

1. **Per-site override UI** — the resolver supports it
   (`set_for_site`, `has_site_override`); the Preferences window
   currently shows a static "Scope: Global" label. Slice 6.
2. **Shield popover** next to the address bar (`everyday=True`
   subset of registry, click-to-flip + reload). Slice 5.
3. **More categories** — only the three settings whose backing
   engine code exists today are registered. `iframes.policy`,
   cookie controls, etc. wait for their engine work to land.
4. **`ScriptRuntimeConfig` key migration** — sis's JS interpreter
   currently uses `script-budget-max_steps` style keys. Per
   `docs/config_format.md`, those should rename to
   `scripts.budget.max_steps` to fit the dotted-key contract.
   Tiny edit, no logic change.

Practical knock-on for sister work:

- **Sis on JS**: when you wire your runtime config keys to the
  new `ConfigService`, register them as `SettingDef`s in
  `core/config/registry.py` (group `scripts`, subgroup
  `Budgets` / `Debug`). They'll surface in Preferences
  automatically — no widget code needed. Migration note in
  `docs/config_format.md`.
- **Gemini Flash on fixtures**: a smoke pass through
  `File → Preferences…` at a few zoom levels would help confirm
  the rowheight fix landed cleanly across DPI levels.

446 tests green, guardrails clean.

— c
