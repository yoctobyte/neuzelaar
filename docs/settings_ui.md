# Settings UI plan

Design reference for the Preferences window and the shield popover.
Companion to `docs/config_format.md` (on-disk shape) and the broader
security-settings discussion in `chat/`.

## Goal

Granular yet navigable. A user who wants the ten everyday toggles
finds them in one click; a user who wants to set
`scripts.budget.max_steps` per-site can do that without leaving the
same window. The structure must keep working after we add 100 more
settings, so the UI is data-driven from a registry rather than
hand-wired per setting.

## Architectural separation

The settings model is decoupled from the UI by design:

```
shells/tk/preferences_window.py        ← Tk renderer (stateless view)
shells/tk/shield_popover.py            ← Tk renderer (stateless view)
                ↓ reads
core/config/registry.py                ← SettingDef declarations
                ↓ reads/writes
core/config/service.py                 ← Config service (load/resolve/save)
                ↓ persists
~/.config/neuzelaar/{config.toml, sites.toml, state.json}
```

The Tk windows only know how to enumerate SettingDefs by group, read
the current resolved value for a key, and write a new value at a
chosen scope. No setting-specific logic lives in the UI. A future
GTK / web / curses shell renders the same registry without changes
to core.

## SettingDef registry

Each setting is declared once:

```python
@dataclass(frozen=True, slots=True)
class SettingDef:
    key: str                 # dotted path, e.g. "scripts.allow"
    kind: SettingKind        # BOOL | ENUM | INT | FLOAT | STRING | DOMAIN_LIST
    default: object
    label: str               # short, human-friendly
    help: str                # one-line plain-language description
    group: str               # top-level topic, e.g. "scripts"
    subgroup: str | None     # optional collapsible header
    weight: int              # ordering within (group, subgroup)
    enum_values: tuple[str, ...] | None = None
    unit: str | None = None  # "ms", "px", etc.
    everyday: bool = False   # surfaces in the shield popover
    advanced: bool = False   # subgroup collapsed by default
    confirm: Literal["never", "when_relaxing", "always"] = "never"
```

Adding a setting = appending one `SettingDef`. The Preferences window
discovers it; the shield popover picks it up if `everyday=True`.

## Confirmation policy

Live-apply is the default — flipping a switch writes immediately.
Three kinds of exceptions:

- `confirm = "never"` — vast majority of settings. Apply silently.
- `confirm = "when_relaxing"` — confirm only when the change
  *increases* attack surface (e.g. `scripts.allow` going
  `same_origin → all`, or third-party iframes going
  `block → click_to_load → allow`). Tightening is silent.
- `confirm = "always"` — destructive operations only: "Reset all
  preferences," "Clear all per-site overrides," "Disable tracker
  block list."

The "relaxing" direction is encoded once per enum/setting in the
registry (e.g. an ordered list `["off", "same_origin", "all"]` where
moving toward the tail is relaxing).

## Window structure

Two-pane plus scope switcher plus search:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Preferences                                              [_] [□] [×] │
├──────────────────────────────────────────────────────────────────────┤
│ Scope:  [● Global]  [○ This site: slashdot.org]    🔍 [search...   ] │
├────────────────────┬─────────────────────────────────────────────────┤
│ Browsing & UI      │  ▾ Scripts                                      │
│ Scripts        [●] │                                                 │
│ Iframes        [○] │  Engine                                         │
│ Content        [○] │     Preferred  [own ▾]      ● Global            │
│   CSS              │     Help: try this engine first; falls back     │
│   Images           │           to noop if it can't load.             │
│   Fonts            │                                                 │
│   Media            │  Allow level                                    │
│ Network            │     [○ Off  ● Same-origin  ○ All]   ● Global    │
│ Cookies & Storage  │                                                 │
│ Privacy            │  ▸ Budgets                                      │
│ Permissions        │  ▸ Debug                                        │
│ ─────────────      │                                                 │
│ About              │                                                 │
├────────────────────┴─────────────────────────────────────────────────┤
│                                  [Reset section]  [Revert]  [Close]  │
└──────────────────────────────────────────────────────────────────────┘
```

### Left rail (navigation)

- Tk `ttk.Treeview` with collapsible parents.
- One entry per top-level group from the registry; nested entries
  per subgroup *only when* the group has many subsettings (e.g.
  `Content` shows CSS / Images / Fonts / Media as children).
- Indicator `[●]` on a section = the current scope has at least one
  override in that section. Helps users find their own changes.

### Right pane (controls)

- Sections rendered as collapsible blocks with `▾` (open) / `▸`
  (collapsed) glyphs.
- Subsections marked `advanced=True` start collapsed (e.g.
  `Budgets`, `Debug`).
- Section dividers render the subgroup label as a small caps header,
  with controls beneath.
- Bottom action bar: `Reset section` reverts every setting in the
  visible section to default; `Revert` undoes changes made since the
  window opened; `Close` dismisses.

### Scope switcher

`[● Global]  [○ This site: <domain>]` at the top of the window.

- **Global mode** writes to `config.toml`.
- **Site mode** writes to `sites.toml` under the current registrable
  domain. Controls show the inherited global value as a watermark;
  changing one adds a per-site override; right-click → "Reset to
  global" removes it.
- Site button is greyed if no current page is open.

The same window handles both — one mental model, two write targets.

### Search

- `🔍 [search...]` at the top, always visible.
- Empty search ⇒ default hierarchy.
- Non-empty search ⇒ substring match across `label` + `help`,
  non-matching controls dim, matched subsections auto-expand,
  hierarchy stays visible. **No flat-list mode.** The point of
  search is to *find a control inside its topic*, not to flatten the
  topology.
- Substring is enough for several hundred settings. Defer fuzzy
  matching until we actually need it.

## Control row pattern

Every control renders the same way regardless of type:

```
Label                              [control widget]    ● Global  [info]
Help text — one line, plain language.
```

- **Help text** is always visible inline. No `[?]` tooltips. Granular
  UI hides too much when help is one click away.
- **Scope dot**: grey = inheriting Default, blue = Global value set,
  orange = Site override. Hover shows where the value lives. Right-
  click → `Reset to default` / `Reset to global` / `Set for this
  site only` (the right options depending on current scope).
- **Changed values render bold** so a glance over a section tells
  you what you've touched.

### Widgets per kind

| `kind`        | Widget                                              |
|---------------|-----------------------------------------------------|
| `BOOL`        | Checkbox or two-state segmented control             |
| `ENUM`        | Segmented buttons inline if ≤ 4 options, else combobox |
| `INT`/`FLOAT` | Spinbox with `unit` suffix                          |
| `STRING`      | Entry field                                         |
| `DOMAIN_LIST` | Editable listbox with `Add` / `Remove` buttons      |

## Shield popover (the everyday path)

Reached from a shield button next to the address bar. Shows only
`SettingDef`s flagged `everyday=True` for the current site:

```
slashdot.org
─────────────────────────
Scripts        [Same-origin ▾]
Iframes        [Click to load ▾]
Images         [Allow ▾]
Cookies        [Session-only ▾]
─────────────────────────
[ Open full preferences for this site… ]
```

- Always opens in *site* scope — these are quick per-site toggles.
- "Reload now" link appears below when a change requires a fresh
  page load (most policy changes do).
- Bottom button switches to the full Preferences window with site
  scope pre-selected.

The shield popover is the daily driver; Preferences is the
occasional dive. Lock icon (HTTPS state) stays separate and remains
read-only.

## Implementation slicing

Order assumes config service from `docs/config_format.md` lands
first.

1. **Config service** (`core/config/service.py`) — TOML loader/writer
   for `config.toml` and `sites.toml`, JSON for `state.json`, scope
   resolver, typed `get`/`set`/`set_for_site`. Tested without UI.
2. **Settings registry** (`core/config/registry.py`) — `SettingDef`
   plus the initial declarations for what already exists today:
   `ui.zoom`, `scripts.engine`, plus the policy profile mapping.
3. **Control widget library** (`shells/tk/widgets/setting_row.py`) —
   one widget per `SettingKind`, plus the scope dot. Reusable across
   Preferences and Shield.
4. **Preferences window shell** (`shells/tk/preferences_window.py`)
   — left rail + right pane + scope switcher + search. Renders
   whatever is in the registry; empty groups hide.
5. **Shield popover** (`shells/tk/shield_popover.py`) — same widget
   library, `everyday=True` filter, address-bar button binding.
6. **Per-site override store** wired through the resolver — site
   scope writes hit `sites.toml`; Preferences shows watermarks.
7. **Categories filled in as backing engine code lands** — iframes,
   cookies, network classes, etc. UI stays alive automatically
   because the registry drives it.

Each slice ships green on its own. Slices 4 and 5 can land without
filling every category — the registry can grow afterward.

## What this doc is and isn't

- **Is**: the Preferences window and shield popover design, the
  abstraction boundary between UI and config, and the slicing for
  building it.
- **Isn't**: the full setting list. That lives in the registry as
  it grows. Likewise, this doc does not prescribe specific Tk
  geometry or styling — only structure.
