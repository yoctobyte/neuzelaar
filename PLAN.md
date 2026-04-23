# Neuzelaar 2 — Implementation Plan

Companion to `concept_pub_talk.md`. That doc is the *why* and the architecture.
This doc is the *what gets built first, with what, in what order*.

Living document. Decisions flagged `[LOCKED]`, `[PROPOSED]`, or `[OPEN]`.

---

## 1. Locked decisions

These are firm from the concept doc or from project setup:

- **Language**: Python 3. `[LOCKED]`
- **Renderer first**: software. GPU is a later backend. `[LOCKED]`
- **Policy-first**: deny-by-default for third-party fetches and active content. `[LOCKED]`
- **One GUI shell in MVP**, plus a headless/console shell always. `[LOCKED]`
- **No real JS engine in MVP**. Architecture reserves the hook. `[LOCKED]`
- **No multimedia / no canvas execution / no WASM execution in MVP** — recognized, placeholder only. `[LOCKED]`
- **Core owns internal representations**. No third-party library objects cross subsystem boundaries. `[LOCKED]`
- **Git workflow**: single `main` branch, small incremental commits. `[LOCKED]`

## 2. Proposed decisions (need your call before code lands)

| Area | Proposal | Why |
|---|---|---|
| First visual shell | **Tk** | Stdlib. `Canvas` + `PhotoImage` is enough to blit a framebuffer. Forces the "shell is thin" thesis. GTK/Qt become *later* shells that prove pluggability. |
| HTML parser | **html5lib** (adapted via its `etree` tree builder) | Forgiving, produces a proper tree, permissively-licensed. Adapter discards their node objects and emits our `DocumentNode`. |
| CSS parser | **tinycss2** | Right level: tokens + simple rule parsing. We own cascade + computed styles ourselves. |
| Fetch | **stdlib `urllib`** | No new deps. Full control over headers / redirects / cookies for policy. `httpx` later if we want async. |
| Image decode | **Pillow** | Also serves as the raster target (`PIL.Image`) for the software renderer. One dep, two jobs. |
| Font / text | **Pillow + FreeType** (`ImageFont.truetype`) | Gets us glyph masks and metrics without writing a shaper. Good enough for MVP text. |
| Config format | **TOML** (stdlib `tomllib`) | Plugin/engine registry config lives in `neuzelaar.toml`. |
| Test runner | **pytest** | Standard. |

If you want a different pick for any row, say so — each one is a cheap flip before there is code.

## 3. Open questions

- **Tab model in MVP**: single-tab process, or multi-tab from day one? I lean single-tab in M1, multi-tab by M4.
- **History persistence**: in-memory only in MVP, or SQLite-backed?
- **Cookie jar persistence**: session-only in MVP, or persist to disk?
- **User agent string**: what do we identify as? Matters for some sites gating on UA.
- **Default policy profile**: Strict / Balanced / Compatibility — which is the out-of-box default? I lean **Strict/Safe** for MVP because policy-first should be the default identity, with Balanced available via flag/config.
- **License**: unspecified. MIT / Apache-2.0 / GPLv3 / unlicensed-for-now?

## 4. Dependency inventory

MVP runtime deps if proposals stand:

```
html5lib        # HTML parsing
tinycss2        # CSS parsing
Pillow          # image decode + raster target + font rendering
```

Stdlib covers runtime plumbing: `urllib`, `http.cookiejar`, `tomllib`, `tkinter`, `dataclasses`, `enum`, `logging`, `sqlite3` later if needed.

Dev deps:

```
pytest          # tests
```

No JS engine dep in MVP. When we add one later, PyMiniRacer or QuickJS bindings are candidates.

## 5. Module layout

Refinement of concept doc §24. Python package rooted at `neuzelaar/`.

```
neuzelaar/
  __init__.py
  __main__.py              # `python -m neuzelaar <url>`
  core/
    bus.py                 # command/event bus
    origin.py              # URL normalization, origin calculation, 1p/3p classification
    session.py             # session + tabs + history
    policy/
      profile.py           # Strict / Balanced / Compat
      rules.py             # third-party/ad/tracker rules
      capability.py        # capability + permission model
    mime/
      classifier.py        # claimed + sniffed + confidence
      sniff.py             # content sniffing table
    fetch/
      client.py            # urllib-backed fetcher
      resource.py          # Resource dataclass
      cookies.py           # cookie jar wrapper
    handlers/
      registry.py          # MIME -> handler
      html_handler.py
      text_handler.py
      image_handler.py
      download_handler.py
  document/
    dom.py                 # DocumentNode tree
    subresources.py        # planned fetch extraction from DocumentNode
    styles.py              # selector matching + cascade
    layout.py              # block/inline/text-run layout
    surfaces.py            # embedded surface box placeholder
    hit_test.py
  render/
    display_list.py        # backend-neutral paint ops
    software.py            # Pillow-backed rasterizer
    text_only.py           # semantic text dump
    debug.py               # dumps: layout boxes, display list, etc.
  engines/
    html/
      html5lib_adapter.py
    css/
      tinycss2_adapter.py
    image/
      pillow_adapter.py
    js/
      interface.py         # abstract engine interface
      noop.py              # MVP default
    wasm/
      interface.py
      noop.py
  shell_api/
    commands.py            # command dataclasses
    events.py              # event dataclasses
    frame.py               # renderer-neutral frame object
    surface.py             # viewport-host contract
  shells/
    headless/
      shell.py
    console/
      shell.py             # text-only TTY
    tk/
      shell.py             # MVP visual shell (if Tk locked)
  plugins/
    registry.py            # shell/engine/renderer registry
  tests/
    unit/
    integration/
    fixtures/
  tools/
    dump_fetch_graph.py
    dump_document_tree.py
```

The `engines/*/` directories hold adapters. Core never imports `html5lib` or `tinycss2` directly; only the adapter does.

## 6. Core data types

Python-level sketches. Field names provisional; semantics are the contract.

**Resource**
```
Resource:
  id: ResourceId
  request: Request            # url, method, headers, body, initiator
  final_url: str
  status: int
  headers: Mapping[str, str]
  body: bytes
  encoding: str | None
  claimed_mime: str | None
  detected_mime: str | None
  mime_confidence: float
  trust: TrustDecision        # allow | block | prompt | download
  handler: HandlerId | None
  cache: CacheMeta
  content_hash: bytes
```

**Request / FetchReason**
```
FetchReason = enum: TOP_LEVEL | STYLESHEET | IMAGE | SCRIPT | FORM_SUBMIT |
                    IFRAME | MEDIA | SCRIPT_INITIATED | FAVICON
Request:
  url: str
  method: HttpMethod
  headers: dict
  body: bytes | None
  reason: FetchReason
  initiator: ResourceId | None
  origin: Origin
  context_origin: Origin      # the page's origin, for 1p/3p decision
```

**Origin / URL**
```
Origin:
  scheme: str
  host: str | None
  port: int | None
  opaque: bool                 # true for schemes like data: and about:

UrlRecord:
  raw: str
  normalized: str
  origin: Origin
  fragment: str | None
```

`core/origin.py` owns URL normalization, relative URL resolution, origin calculation,
and first-party vs third-party classification. Policy code must call this module
instead of doing ad hoc string comparisons.

**DocumentNode tree**
```
DocumentNode (sum type):
  Document { children, url, title }
  Element  { tag, attrs, children, parent, source_loc?, computed_style?, layout_box? }
  Text     { data, parent }
  Comment  { data, parent }          # optional
  SurfaceBox { kind, bounds, fallback }   # canvas / video / iframe placeholder
```

**SubresourceRequest**
```
SubresourceRequest:
  url: str
  reason: FetchReason
  node_id: NodeId
  attr: str                       # src, href, srcset later, etc.
  policy_hint: Passive | Active
```

`document/subresources.py` scans the internal document tree and emits planned
subresource requests. The core then asks policy before any subresource fetch.
Initial extraction covers `<script src>`, `<img src>`, `<link rel=stylesheet>`,
and `<iframe src>` as a placeholder-only future surface.

**LayoutBox**
```
LayoutBox (sum type):
  BlockBox   { rect, padding, border, margin, children, node }
  InlineBox  { rect, children, node }
  TextRun    { rect, glyphs, font, node }
  ReplacedBox{ rect, resource_id, node }
  SurfaceBox { rect, clip, z, alpha, node }
```

**DisplayList op sequence**
```
DisplayOp (sum type):
  FillRect(rect, color)
  DrawBorder(rect, sides)
  DrawTextRun(origin, glyphs, font, color)
  DrawImage(rect, resource_id)
  PushClip(rect)
  PopClip()
  CompositeSurface(surface_id, rect, alpha)
  Placeholder(rect, kind)
```

**Frame**
```
PixelFormat = enum: RGBA8888
Frame:
  width: int
  height: int
  format: PixelFormat
  pixels: bytes | memoryview
  stride: int
```

The software renderer may use Pillow internally, but `shell_api` exposes only
`Frame`. Shells do not receive `PIL.Image` or any renderer-specific object.

**Capability / Permission**
```
Capability = enum: EXEC_INLINE_JS | EXEC_SAMEORIGIN_JS | EXEC_THIRDPARTY_JS |
                   NET_FETCH_FROM_SCRIPT | TIMERS | DOM_MUTATE | FORM_SUBMIT |
                   SET_COOKIE | PERSISTENT_STORAGE | USE_CANVAS | LOAD_WASM
PermissionScope = enum: ONCE | TAB | SESSION | ORIGIN | PERSISTENT
Permission { capability, scope, origin?, granted_at, expires_at? }
```

**Commands / Events** — see §7.

## 7. Shell ↔ Core protocol

Core exposes a bus. Shells only know these types.

**Commands in** (shell → core):
```
OpenUrl(url), Reload(), StopLoad(), Back(), Forward(),
ClickAt(x, y), HoverAt(x, y), ScrollBy(dx, dy),
KeyPress(key, mods), TextInput(text),
SubmitForm(form_id),
AllowCapabilityOnce(capability, origin),
SetSitePolicy(origin, profile),
CloseTab(id), DuplicateTab(id), OpenInNewTab(url)
```

**Events out** (core → shell):
```
PageLoadStarted(url), PageLoadProgress(done, total),
PageLoadFinished(url, status), PageFailed(url, reason),
TitleChanged(title), UrlChanged(url), HistoryChanged(),
RenderInvalidated(rect | FULL),
PermissionRequested(capability, origin, resolver),
ResourceBlocked(url, reason), ScriptBlocked(origin, reason),
StatusMessage(text), ConsoleLog(level, text), HandlerWarning(text)
```

Core must never import from `shells/`. Shells must never import from `render/software.py` directly — they get a `Surface` from the core.

**Surface contract** (`shell_api/surface.py`):
```
Surface:
  size: (w, h)
  present(frame: Frame) -> None
  invalidate(rect) -> None
Shell provides a Surface and forwards input events.
```

## 8. Milestone 1 — "Headless skeleton"

**Goal**: `python -m neuzelaar https://example.com` prints a semantic text dump of the page, logs every fetch decision, and exits clean. No GUI yet.

**In scope**:
- [ ] Repo skeleton per §5 (empty `__init__.py` files, no code in GUI/engines beyond stubs)
- [ ] `core/bus.py` — dataclass commands + events, sync dispatch
- [ ] `shell_api/commands.py` + `shell_api/events.py`
- [ ] `shell_api/frame.py` + `surface.py` — neutral `Frame`, no Pillow types in shell API
- [ ] `core/origin.py` — normalize URLs, resolve relative URLs, calculate origins, classify 1p/3p
- [ ] `core/fetch/resource.py` — `Resource`, `Request`, `FetchReason`
- [ ] `core/fetch/client.py` — urllib GET with redirect cap, timeout, byte cap
- [ ] `core/mime/classifier.py` — header + extension + minimal sniff (HTML / plain / image / binary)
- [ ] `core/handlers/registry.py` + `html_handler.py` (parse via html5lib adapter) + `text_handler.py` + `download_handler.py`
- [ ] `engines/html/html5lib_adapter.py` — html5lib tree → our `DocumentNode`
- [ ] `document/dom.py` — node types, tree walk
- [ ] `document/subresources.py` — extract planned subresource fetches from the document tree
- [ ] `render/text_only.py` — semantic dump (indented tree with `<h1>`, `<p>`, links, etc.)
- [ ] `shells/headless/shell.py` — drives core, prints events + final text dump
- [ ] `core/policy/profile.py` + `rules.py` — hardcoded third-party block list (a few known ad hosts) just so the pipeline runs
- [ ] `__main__.py` — CLI entry
- [ ] `tests/integration/test_m1_example_com.py` — fetch-or-fixture, assert text contains "Example Domain"
- [ ] `tests/integration/test_m1_blocked_resource.py` — fixture page that includes a third-party script, assert it was blocked before fetch
- [ ] `tests/unit/test_origin.py` — relative URL resolution and 1p/3p classification
- [ ] `tests/unit/test_subresources.py` — fixture document emits script/image/stylesheet planned requests
- [ ] `README.md` — run instructions

**Out of scope for M1** (explicitly):
- CSS (engine exists as stub; no cascade)
- Images (recognized, not decoded)
- Layout (text-only renderer in M1)
- Forms, cookies, navigation history
- GUI shell
- JS / canvas / WASM (all `noop`)

**Done criterion**: the two integration tests pass offline (fixtures), and `python -m neuzelaar <local-file.html>` against a saved copy of a real blog post produces a readable text dump.

## 9. Milestones 2–6 (sketched)

Each is ~1–2 weeks of focused work, roughly. Ordering preserved from concept doc §26, tightened.

**M2 — Minimal document browser**
- Cookie jar (session-only)
- Navigation + history (back/forward, in-memory)
- Link following (click events abstracted)
- Console shell that can actually `open_url` and show pages interactively in a terminal
- Benchmark: read a Wikipedia article end-to-end via console

**M3 — Basic visual browser**
- Tk shell (or whatever §2 resolves to)
- Software rasterizer (Pillow) via display list
- Layout tree (block + inline + text runs)
- Headings / paragraphs / lists / links / images (now decoded) / scroll
- Tiny CSS slice: inline `style=""`, `<style>` blocks, and only `display`, `color`, `background-color`, `font-size`, `font-weight`, `margin`, `padding`
- External stylesheets may be discovered and policy-logged, but full stylesheet fetching/application can wait until M5
- Debug overlays: layout boxes, display list dump
- Benchmark: render a static blog post and a docs page readably

**M4a — Interaction and forms**
- `<form>` GET + POST
- `<input>`, `<textarea>`, `<button>`, `<select>`
- Text entry, focus, keyboard routing
- Session cookies sufficient for fixture login
- Benchmark: log into a simple forum-style site and post a comment on a fixture server

**M4b — Persistence and tabs**
- Persistent cookie jar (disk)
- Multi-tab
- Per-tab history/session isolation
- Benchmark: two tabs with different page state, back/forward remains independent

**M5 — Styling and policy maturity**
- CSS subset per concept doc §14.1
- Policy modes: Strict / Balanced / Compatibility switchable at runtime
- Blocklist rules externalized (load from file)
- Resource budgets (request count, total bytes, DOM node count)
- "What got blocked on this page" UI panel
- Benchmark: render Hacker News, GitHub README, Python docs with correct basic styling

**M6 — Active content framework (no real JS yet)**
- `engines/js/interface.py` formalized
- Capability bridge
- Permission prompts UI
- `noop` engine still default; `stub` engine that logs what scripts *would* do
- Benchmark: visit a JS-heavy site and produce a clean report of blocked scripts and requested capabilities

After M6 the path forks (restricted JS, canvas, WASM, GPU) per concept doc §27. We replan then.

## 10. Benchmark sites

"MVP done" is measured against real pages, not specs. Each milestone adds to the suite. Fixtures saved under `tests/fixtures/sites/` for offline CI. Live sites are manual smoke tests only; CI must not depend on the current network, current site markup, CDN behavior, or bot defenses.

| Site | Tests what | Added at |
|---|---|---|
| `example.com` | baseline fetch + parse | M1 |
| `info.cern.ch` (the original) | tiny HTML, no deps | M1 |
| A saved Wikipedia article | real-world HTML complexity | M2 |
| Python docs (`docs.python.org`) | dense text, anchors, navigation | M2 |
| A static blog post (e.g. a Jekyll page) | typical modern-but-simple markup | M3 |
| Hacker News front page | tables-for-layout, forum density | M3 |
| GitHub README render | mixed content, images | M3 |
| A saved forum thread (phpBB-style) | pagination, nested content | M4 |
| A fixture server we control | form POST, cookies, login | M4 |
| A JS-heavy SPA (e.g. a React docs page) | what degrades, what blocks | M6 |

## 11. Risks and guardrails

From concept doc §28, plus operational guardrails:

- **CSS rabbit hole** → freeze CSS scope at M5's subset; new properties need a written reason.
- **GUI leakage into core** → CI check: `grep -r "import tkinter\|import gi\|PySide" neuzelaar/core neuzelaar/document neuzelaar/render` must return empty.
- **Library objects leaking** → same check for `import html5lib` / `import tinycss2` outside `engines/`; same check for `from PIL\|import PIL` outside `engines/image`, `render/software.py`, and narrowly-approved conversion helpers.
- **Origin bugs** → policy never compares host strings directly; all origin and 1p/3p decisions go through `core/origin.py`.
- **Subresource policy bypass** → subresource discovery produces planned requests; core asks policy before fetch; handlers must not fetch nested resources directly.
- **Premature JS** → `engines/js/noop.py` stays the default until M6 is *complete*.
- **Scope drift** → every PR names the milestone it belongs to. Out-of-milestone work needs a note in this doc first.
- **"Fix by disabling"** → if a test or policy check blocks progress, don't bypass; update this plan and the concept doc instead.

## 12. Test strategy

Tests are part of the architecture, not an afterthought. M1 should bias toward
small unit tests for contracts and a few offline integration tests for the full
headless path.

### 12.1 Unit tests

Unit tests live under `tests/unit/` and should not perform network access.
They cover:

- `core/origin.py`: URL normalization, relative resolution, origins, opaque origins, 1p/3p classification.
- `core/bus.py`: subscription and synchronous event delivery.
- `core/mime/`: claimed MIME handling, conservative sniffing, extension fallback, safe text-vs-HTML behavior.
- `core/policy/`: top-level allow, strict third-party script/iframe block, tracker host block, first-party passive resource allow.
- `document/dom.py`: parent/child ownership and tree walking.
- `document/subresources.py`: planned resource extraction without fetching.
- `render/text_only.py`: headings, links, images, lists, and script/style suppression.

### 12.2 Integration tests

Integration tests live under `tests/integration/` and use only offline fixtures
or local fixture servers. No test may depend on live website markup or network
availability.

M1 integration tests cover:

- local fixture fetch into `Resource`
- fetch -> classify -> handler -> internal document -> text renderer
- third-party script discovered as a planned subresource and blocked before fetch
- CLI smoke path via `python -m neuzelaar <fixture>`

### 12.3 Guardrail tests

Guardrail tests verify architectural boundaries:

- no GUI toolkit imports in `core`, `document`, or `render`
- no html5lib/tinycss2/Pillow imports leaking into `core`, `document`, or `shell_api`
- no generated files are tracked

The shell script lives at `tools/check_guardrails.sh`; pytest should invoke it
so local test runs catch boundary regressions early.

### 12.4 Test naming

Use names that explain behavior, not implementation mechanics:

- `test_mime_text_plain_html_stays_text`
- `test_third_party_script_is_blocked_before_fetch`
- `test_cli_reports_blocked_subresource`

Avoid one giant "M1 works" test. The integration suite should prove the pipeline
while unit tests explain exactly which contract broke.

## 13. First week

If §2 resolves this week, concrete first commits:

1. Add `pyproject.toml` with the 3 runtime deps, Python 3.11+ unless a concrete 3.12-only feature is needed.
2. Create `neuzelaar/` skeleton per §5 — empty modules with docstrings stating their contract.
3. `shell_api/commands.py`, `events.py`, `frame.py`, and `surface.py` as dataclasses/protocols.
4. `core/bus.py` — simplest possible synchronous dispatch.
5. `core/origin.py` — URL normalization and origin classification tests.
6. `core/fetch/resource.py` + `client.py` — urllib GET, no policy yet.
7. First test: fetch a local `file://` fixture, assert `Resource` populated.

That's enough scaffolding to start filling in §8 the week after.

## 14. Multi-agent workload plan

Multiple agents should work in parallel, but with explicit ownership. The goal is
speed plus cross-checking: each agent should know what the others changed, avoid
file collisions, and review at least one other agent's important work before it
is treated as stable.

### 14.1 Coordination rules

- Every agent starts by reading `PLAN.md`, `concept_pub_talk.md`, `git status --short`, and the latest commits.
- Every agent works on a named branch or worktree when possible: `agent/<name>-<task>`.
- Every important change gets a small commit with a clear message. Avoid huge mixed commits.
- Before committing, run the relevant tests for the touched area. If tests cannot run, mention why in the commit message or handoff note.
- Do not edit files outside the assigned ownership area without announcing it in the handoff note.
- Do not revert another agent's work. If it conflicts, adapt or raise it for review.
- After each commit, append a short handoff note to the shared coordination channel or issue tracker: files changed, tests run, follow-up risks.
- Cross-review is required before merging to `main`: at least one other agent reviews architectural changes; trivial docs/test fixture changes may be self-reviewed.
- CI and guardrail checks are the merge authority. If CI contradicts an agent's assumption, update the plan or code instead of bypassing the check.

### 14.2 Initial parallel assignments

| Agent | Ownership | First deliverable | Review partner |
|---|---|---|---|
| **Codex** | Core contracts: `shell_api/`, `core/bus.py`, `core/origin.py`, `core/fetch/resource.py` | Dataclass/protocol skeletons, origin tests, neutral `Frame` API | Claude |
| **Claude** | HTML/document pipeline: `document/dom.py`, `document/subresources.py`, `engines/html/html5lib_adapter.py`, `core/handlers/html_handler.py` | Fixture HTML parses into internal nodes; subresources emitted as planned requests | Codex |
| **Antigravity** | Fetch/policy integration: `core/fetch/client.py`, `core/policy/`, `core/mime/`, handler registry | Top-level fetch with byte/redirect/time caps; MIME decision object; policy blocks planned third-party script before fetch | Codex or Claude |
| **Gemini** | Trivial/scaffolding work: package skeleton, `README.md`, fixtures, smoke-test docs, grep guardrail script | `pyproject.toml`, empty modules with contract docstrings, initial offline fixtures, README run instructions | Any hard-task agent |

### 14.3 M1 merge order

1. Gemini lands project skeleton, `pyproject.toml`, README, and fixtures.
2. Codex lands shared contracts: commands/events/frame/surface, bus, origin, resource dataclasses.
3. Claude lands DOM adapter and subresource extraction against fixtures.
4. Antigravity lands fetch, MIME, policy, and handler registry integration.
5. Codex or Claude wires `__main__.py` and `shells/headless/shell.py`.
6. A different agent from the integrator runs and reviews the full M1 fixture suite before merge to `main`.

### 14.4 Review checklist

- Core does not import GUI toolkit modules.
- Core/document/shell API do not expose `PIL.Image`, html5lib nodes, tinycss2 tokens, or other third-party objects.
- Every fetch has a `FetchReason`, initiator, and policy decision.
- Subresource requests are planned before fetch and can be blocked before network access.
- Offline fixtures are sufficient for CI.
- New behavior has focused tests, not only manual output.
