## 2026-04-23 20:05 CET — note to self

Evening session. User confirmed the agent role split and then pivoted
to "set up messenger-style chat channels" instead of consolidating
coordination docs. That's the right call — consolidation would flatten
the signal; multiple narrow channels preserve it.

**Tonight is not for code.** User's rhythm: evening plan, 05:00
execute. I've hit that rhythm. Don't drift.

### Things I almost did tonight and should not

- Writing core code myself to "help" — would step on Codex's M1
  completion path tomorrow.
- Consolidating `CLAUDE_TASKS.md` + `GEMINI_FLASH_TASKS.md` into
  one `AGENTS.md` — user explicitly said no. More channels, not fewer.
- Designing the M3 Tk shell — not blocking anything, skip.

### Things worth holding in mind for next evening

- **Default policy profile**: I saw `PolicyEngine` with strict-ish
  rules (third-party script/iframe block, tracker host block) but
  did not verify that `PolicyEngine()` default construction actually
  *is* Strict by profile name, or whether profiles even exist yet.
  The §3 open question about Strict-vs-Balanced default is still
  open in PLAN.md. If Codex's Task 5 work lands first, the profile
  wiring may shift — revisit then.
- **Bus integration for events**: `PageLoader.load()` currently
  returns structured data and emits nothing. Fine for M1. M2 console
  shell needs `PageLoadProgress` / `ResourceBlocked` events on the
  bus. Note for the M2 plan update.
- **Header composition for outbound requests**: where does
  referer/UA live — `PageLoader` or `FetchClient`? I told Codex I
  lean `FetchClient`. If they disagree with a real argument, listen;
  this is their specialty.

### Open question for user that I should not forget

The §2 proposals (Tk, html5lib, tinycss2, Pillow, urllib) haven't
been explicitly approved. Most have landed in code already, which
is de facto approval. But **Tk hasn't** — M1 needs no shell, M2 is
console. Tk doesn't get touched until M3. So the §2 Tk decision can
wait until late M2 without blocking anyone. Don't keep nagging about
it.

### Self-discipline

Stop second-guessing Codex's implementation before seeing it. When
the Task 3/4/5 work lands tomorrow, review what *exists* — don't
review what I *imagined* Codex would write. My instinct to speculate
about `PageLoadResult` missing MIME confidence was wrong; I assumed,
I read the code, I was wrong. Read first, then opine.

— c

---

## 2026-04-24 05:45 CET — note to self

Walked into massive delta overnight. 20+ commits. Codex blew through
M2/M3/M4a/M4b/P8 and deep into P9+P10 in one session. 109 tests green.
MVP standing.

User's explicit instruction: "user doesnt know. agents should fight this
out." Meaning: the P1 "next package" call (P9 vs P10 vs M7) and the
PageLoader split + permission service shape are ours to resolve. Not a
green light to wander — a green light to *decide*.

### What I did

Read `page.py` (388 lines), `policy/permissions.py`, `policy/capability.py`,
`engines/js/interface.py`, `shell_api/events.py`. Replied to Codex
(`chat/claude-to-codex.md`) with:

1. Gateway extraction first, before passive/script split. Duplication in
   `_fetch_stylesheets` / `_evaluate_planned_subresources` / `_fetch_images`
   is the real signal. `extract_subresources` is called 3x — kill that.
2. Push back on callable resolvers in `PermissionRequested`. Grants go
   through the command bus (`GrantPermission` / `DenyPermission` with
   `request_id`), not via event callbacks. Keep events as serializable
   data per PLAN.md §3.2.
3. Flagged a sequencing bug that's hidden by the noop engine:
   `_publish_script_permissions` fires AFTER the engine returns BLOCKED.
   Harmless now, breaks when a real engine arrives. Fix order when doing
   permission service work.

### What I did NOT do

- Did not refactor `PageLoader` myself. That's Codex's lane.
- Did not touch TODO.md to mark "P1 Claude review" done. Let Codex or
  user close the dashboard item when they pick up the refactor work.
- Did not weigh in on P9 vs P10 next-package selection. Both are already
  in progress; the "fight it out" mandate is about the architectural
  questions, not forcing a milestone choice.

### For next evening

- Check if Codex pushes back on any of the three recommendations.
  Gateway extraction specifically — if they have a reason it's wrong,
  listen hard; they've been living in the code.
- If they adopt, review the refactor PR — **review what exists, not
  what I imagined** (prior self-note still applies).
- If `PermissionService` lands, verify the command-bus roundtrip
  actually works end-to-end from a console shell test.
- P1 "next package" choice is still open per TODO.md. If codex doesn't
  make the call, I should. My lean: finish P10 (real grant flow) before
  expanding P9 CSS surface — policy correctness matters more than
  styling breadth for this project's identity.

### Self-discipline check

Resist writing code in evening mode. The chat reply is the deliverable.
Code happens at 05:00 execution cycle by whoever picks it up.

— c

---

## 2026-04-25 CET — note to self — [layout-sweep-closed]

Layout sweep landed in one extended session: A1, A2 (sis), B, C, D,
E, F. 366 tests green, guardrails clean. Broadcast at
`chat/claude-to-all.md` summarises what works and what's deferred.

Things I deliberately did *not* do, so future-me knows these are
not gaps to "discover":

- **Borders** — `BoxGeometry.border` is in the model as `EdgeSizes`
  but always zero. `border-style` / `border-color` / `border-width`
  parsing not in. Add when needed; a small slice on top of the box
  model.
- **Per-edge longhand** for margin/padding (`margin-top: 5px` over
  `margin: 10px`). Shorthand expands at layout time, not at parse
  time, so longhand overrides don't cascade correctly. Fix: expand
  at parse time and add the eight longhands to
  `SUPPORTED_PROPERTIES`.
- **`%` widths/heights** relative to containing-block. CB stack is
  there; `_resolve_width` / `_resolve_height` need to detect `%`
  and look up the relevant CB axis.
- **`bottom` for absolute when height is `auto`** falls back to
  zero. Real CSS does over-constrained two-pass resolution we
  don't run.
- **Partial clipping** — rasterizer skips ops fully outside an
  active clip; partial overlaps draw fully. PIL alpha mask
  composition would fix it.
- **`z-index` for non-positioned in-flow content** doesn't apply.
  Per CSS 2.1 it shouldn't (in-flow always paints behind
  positioned), so this is not a bug — but when stacking contexts
  arrive (opacity, transform), it'll need revisiting.

Best next slice if user signals "keep rolling": **iframes**. Layout
side is a replaced inline-block sized by `width`/`height` attrs
(HTML5 default 300×150). Pipeline side is a recursive
`PageLoadResult` per browsing context — the loader becomes a tree
rather than a single result, with each iframe carrying its own
origin / cookies / capability scope. Policy side already mostly
wired (`FetchReason.IFRAME`, sis's PermissionService for
capability grants). The interesting architectural call is how
nested page loads inherit policy + cookie scope from the parent —
mirror what the existing PageLoader does, with origin checks at
each iframe boundary.

If user shifts focus or stops, the natural floor is here. The
sweep is complete enough that real pages should look materially
closer to author intent at any viewport / zoom.

Sister AIs continued JS interpreter work in parallel; only shared
code I touched was `BoxPlacement` (added optional `node_id`) and
the watchdog `check_resources` calls remained sis's. JS work
shouldn't be blocked by anything I landed.

### What I did NOT do this session, deliberately

- Touch `neuzelaar/engines/js*` or any JS test — sis's lane.
- Add iframes — flagged for next slice, not started.
- Mark P9 "Done" in `TODO.md` — sis owns that dashboard line; let
  her close it on her pass when she sees the layout work land.
- Post-sweep backlog reordering — kept the priority list as-is in
  `docs/layout_plan.md`.

— c

---

## 2026-04-25 CET — note to self — [settings-system-v1]

Evening session. User pivot from "make iframes work" to "first
build the security/settings model that iframes will plug into."
Right call — iframe policy is half a dozen settings, building
those without a settings system would have meant hard-coding
toggles into the iframe slice and ripping them out later.

### What landed

Four commits, in this order:

1. `4d36b2d` — `docs/config_format.md` (TOML + JSON split, flat
   dotted keys, sections vs leaves)
2. `3468c24` — `docs/settings_ui.md` + multi-format clarification
   in config_format.md
3. `7f4e202` — `core/config/{registry,service}.py`,
   `shells/tk/widgets/setting_row.py`,
   `shells/tk/preferences_window.py`, wired into `shell.py`
4. `bb08fc5` — high-DPI Treeview rowheight fix
   (font linespace + 8px padding instead of hardcoded 34)

### Key decisions worth holding in mind

- **Registry is data, UI is dumb**. `SettingDef` is the contract;
  the Preferences window enumerates and renders. A future GTK or
  web shell renders the same registry without touching core. If
  you find yourself adding setting-specific code to the window,
  stop — make it a `SettingDef` field instead.
- **Confirm policy is one-sided**. `when_relaxing` only prompts
  when the change increases attack surface. Tightening is
  silent. The relax direction is encoded in `relax_order` per
  enum. Other settings that ever need this rule:
  `iframes.policy`, `cookies.allow`, `content.images.third_party`
  — register `relax_order` for each.
- **Hand-rolled TOML writer is fine**. We control the schema. If
  it ever gets bigger than the current ~70 lines, switch to
  `tomli_w` — but right now the dep cost isn't worth it.
- **Live-apply is the default** but I haven't tested confirm
  dialogs in a real running window. The `messagebox.askyesno`
  paths exist; verify on next UI session that they don't trigger
  on every `_refresh()` (they shouldn't — only on `_apply` —
  but flag if you see redundant prompts).

### Things I almost did and should not have

- **Did NOT** touch sis's `script-budget-max_steps` keys
  directly. Migration is hers to do; I left a note in
  `config_format.md` describing the rename.
- **Did NOT** delete the `Settings`/`settings.json` legacy code.
  ConfigService imports from it on first load and
  `self.settings.zoom` is still read by the rendering path. When
  the entire shell reads from `ConfigService`, that'll be a
  follow-up cleanup — not now.
- **Did NOT** add per-site UI even though the resolver supports
  it. Without an iframe or per-site-policy backing setting,
  there's nothing to scope yet. The shield popover (Slice 5)
  brings the per-site UX; that's the natural pairing.

### For next evening

- User signalled "new job" after this — so the next session may
  be unrelated. If it IS settings continuation, the natural
  next slice is **shield popover** because it gives the
  per-site UI a use case before iframes land.
- If iframes get prioritised first, register the iframe
  settings (`iframes.policy`, `iframes.max_depth`,
  `iframes.max_count`) in the registry as part of that slice —
  they'll show up in Preferences automatically.
- Watch for sis renaming her runtime config keys. If she does,
  the keys need to also get registered as `SettingDef`s under
  `scripts` group, subgroup `Budgets` / `Debug`. The
  `from_settings(dict)` shape doesn't need to change.

### Self-discipline check

User tried to "go ahead, my dear" and I correctly switched modes
from planning to building. The four-commit shape (docs first,
then implementation, then a tiny bug fix the user caught) is the
right grain — small enough to revert any one without losing the
others. Hold this rhythm.

— c

