# Config format

Short reference for how Neuzelaar stores user configuration on disk
and how modules read it. Cross-module shared contract — keep it stable.

## File format: TOML

Two files, both TOML, both under `~/.config/neuzelaar/` (XDG-aware via
`XDG_CONFIG_HOME`):

- `config.toml` — global user config.
- `sites.toml` — per-site overrides.

Why TOML:

- Stdlib reader (`tomllib`, Python 3.11+). Writer is hand-rolled or
  `tomli_w`; the schema is small and we control it.
- Comments allowed. Section headers organise without indentation
  traps (unlike YAML).
- Far less typo-sensitive than YAML — no significant whitespace, no
  quoting surprises around booleans / numbers.
- More user-readable than JSON.

The previous `settings.json` (zoom) stays readable as a legacy
fallback during migration; new writes go to `config.toml`.

## API contract: flat dotted keys

Modules never read TOML directly. They go through a single config
service that exposes a typed registry keyed by **dotted lowercase
paths**:

```
scripts.engine               = "own"
scripts.budget.max_steps     = 100000
scripts.budget.max_ms        = 250
iframes.policy               = "click_to_load"
iframes.max_depth            = 4
content.images.third_party   = "block"
ui.zoom                      = 1.0
```

Compound leaf names use `_` (`max_steps`, `third_party`). Section
prefixes use `.` (`scripts.budget`).

Why flat dotted keys at the API:

- One uniform shape for callers. `cfg["scripts.engine"]` works
  regardless of how deeply the file nests.
- Easy to flatten / unflatten between TOML sections and the runtime
  dict.
- Drop-in compatible with sis's existing
  `ScriptRuntimeConfig.from_settings(dict)` once the keys are
  renamed (see migration below).

## On-disk shape

`config.toml`:

```toml
# Global user configuration. Per-site overrides live in sites.toml.

[ui]
zoom = 1.0

[scripts]
engine = "own"           # noop | own | quickjs | js2py
allow  = "same_origin"   # off | same_origin | all

[scripts.budget]
max_steps = 100000
max_ms    = 250

[iframes]
policy    = "click_to_load"   # block | click_to_load | allow
max_depth = 4
max_count = 20

[content.images]
third_party = "allow"   # off | same_origin | allow

[content.css]
third_party = "allow"

[network]
block_known_trackers = true
```

`sites.toml`:

```toml
# Per-site overrides keyed by registrable domain.

[sites."slashdot.org"]
"scripts.allow"             = "all"
"content.images.third_party" = "allow"

[sites."example.com"]
"iframes.policy" = "block"
```

Inside a `[sites."<domain>"]` section, keys are the same flat dotted
strings used by callers — no further nesting. This keeps the
override layer trivial: a `dict[domain, dict[key, value]]`.

## Resolution order

```
defaults (in code) → profile (Strict/Balanced/Compatibility) → config.toml → sites.toml[domain]
```

Per-site overrides win. Profile is a *named bundle of defaults* — it
moves the baseline, but never overwrites user-set values above it.

## Sections (top-level topics)

Keep the topic list small and stable. Add a topic only when a real
setting needs it.

| Topic       | What goes here                                              |
|-------------|-------------------------------------------------------------|
| `ui`        | zoom, viewport memory, default homepage                     |
| `scripts`   | JS engine, allow level, budgets, debug                      |
| `iframes`   | iframe policy, depth/count limits, sandbox defaults         |
| `content`   | css/images/fonts/media — per-resource third-party policy    |
| `network`   | tracker block, referer policy, UA, third-party class policy |
| `cookies`   | cookie policy, third-party cookies, persistent storage      |
| `privacy`   | DNT, fingerprint surface, etag/cache leakage                |
| `permissions` | capability defaults (form submit, canvas, wasm, …)        |

## Reading and writing

Suggested API (not yet implemented — sketch for sis):

```python
class Config:
    def get(self, key: str) -> object: ...
    def get_typed(self, key: str, kind: type[T]) -> T: ...
    def set(self, key: str, value: object) -> None: ...      # writes config.toml
    def set_for_site(self, domain: str, key: str, value: object) -> None: ...   # writes sites.toml
    def reload(self) -> None: ...
```

Resolution is bottom-up; `get` returns the highest-priority value.
`set` only writes the layer it targets — a global `set` does not
clear a per-site override.

## Naming rules

- Lowercase only.
- Section separator: `.`
- Word separator inside a leaf: `_`
- No abbreviations unless they're already universal (`ms`, `url`, `ua`).
- Boolean keys are positive: `block_known_trackers`, not
  `allow_trackers`. Easier to read at a glance.

## Migration note for sis

`ScriptRuntimeConfig` currently uses keys like
`script-budget-max_steps`. To fit this format:

```
script-budget-max_steps        → scripts.budget.max_steps
script-budget-max_ms           → scripts.budget.max_ms
script-debug-track_tasks       → scripts.debug.track_tasks
script-debug-keep_history      → scripts.debug.keep_history
script-debug-max_history       → scripts.debug.max_history
```

Pluralised topic (`scripts`) and `.` instead of `-` for the section
separator. The existing `from_settings(dict)` / `to_settings()`
shape is unchanged — only the key strings rename.

## What this doc is and isn't

- **Is**: the on-disk and in-API contract for user config across all
  modules.
- **Isn't**: the GUI design for the Preferences window, or the list
  of every setting we'll ever add. Those evolve separately.
