Yes — that is a very clean direction.

If the viewport is ultimately “just a surface,” then the GUI toolkit becomes mostly:

    window management

    event delivery

    clipboard/menu/dialog glue

    maybe IME/input glue later

and the page itself becomes a self-contained rendering target.

That is exactly the kind of separation you want.
Good long-term model

Think of the page viewport as something like:

    abstract drawing surface

    size in pixels

    input event stream

    invalidation/repaint requests

    optional accelerated backend later

So later that surface could be:

    software framebuffer

    OpenGL texture/canvas

    Vulkan/Metal/whatever one day

    offscreen buffer for tests

    web canvas in a browser-hosted frontend

That is strong architecture.
And yes: software renderer first

I think that is absolutely the right call.

Not because OpenGL is bad, but because right now hardware acceleration would mostly add:

    backend complexity

    state/debug difficulty

    text rendering annoyances

    more platform-specific weirdness

    more temptation to optimize before understanding

Whereas a software renderer gives you:

    deterministic behavior

    simple debugging

    easy screenshots/dumps

    easy dirty-rectangle logic

    easy fallback/headless support

    very clear ownership of rendering stages

For this project, that is gold.
In practice, this suggests a nice split
Layout engine outputs

Not toolkit widgets, but something like:

    boxes

    text runs

    borders/backgrounds

    images

    clipping regions

    z-order if needed later

    hit-test data

Renderer consumes that and emits

Either:

    paint commands

    or directly writes to a software pixel surface

GUI shell just presents the resulting bitmap/surface

And forwards:

    mouse

    keyboard

    scroll

    resize

    focus events

That is a much healthier architecture than letting GTK/Tk become the renderer.
A layered rendering path would fit nicely

You could structure it like:

Document tree -> Computed styles -> Layout tree -> Display list -> Rasterizer -> Surface

That gives you very clean upgrade paths.

For example:

    today: software rasterizer writes pixels

    later: OpenGL backend draws the same display list

    later still: retained GPU scene or texture caching

The key is that display list or equivalent intermediate representation.

That is the seam that lets software and GPU coexist later.
Why software first is extra wise here

Because the hard problem is not drawing pixels fast enough.

The hard problem is:

    deciding what to draw

    deciding where to draw it

    deciding what was clicked

    text flow

    scrolling

    clipping

    repaint invalidation

    selection/focus

    consistent behavior across backends

A GPU will not solve those. It only changes how the final paint happens.

So yes, do the intellectually central stuff first.
I would keep “surface” abstract from day one

Maybe the renderer only assumes something like:

    width/height

    set pixel span or blit rectangle

    upload image

    draw glyph mask

    clip

    clear/fill

Even if internally your first implementation is just a plain software image buffer.

Then later an OpenGL surface backend can implement the same conceptual contract, or you can switch one layer lower and consume the same display list differently.
2D first, 3D only as implementation detail

You mentioned 2D or 3D OpenGL surface, which makes sense.
But I would keep the browser’s own mental model firmly 2D.

Even if later OpenGL uses textured quads and transforms under the hood, the browser should think in:

    rectangles

    text baselines

    clipping

    stacking

    scroll offsets

Not 3D objects.

Otherwise you invite fancy nonsense before useful nonsense.
This also helps pluggable GUI a lot

Because if the shell only needs to host a bitmap/surface, then Tk, GTK, Qt, and others become much easier to support.

They do not need to understand your DOM or your layout model.
They only need to:

    allocate drawing area

    show the latest frame

    send input events back

    ask for redraw when told

That is much more portable.
Strong recommendation: define three abstractions

This would keep the render side sane.
1. Display list / paint tree

A backend-independent description of what should appear.
2. Raster target

A software-oriented API for painting into pixels.
3. Viewport host

A GUI/shell object that presents frames and forwards input.

Then:

    software renderer = display list -> raster target

    OpenGL later = display list -> GPU surface

    shell = frame presentation + event plumbing

That gives you long-term freedom without overbuilding now.
Text will be the first real rendering dragon

Not OpenGL.

The first dragon is text:

    font metrics

    shaping maybe later

    wrapping

    clipping

    selection

    cursor placement

    line height

    fallback fonts

So software-first is even more sensible, because you can inspect every text run and every box without GPU fog.
Nice side effect: deterministic debug tools

With a software renderer you can easily support:

    dump frame to PNG

    dump dirty rectangles

    debug-box overlay

    show layout bounds

    show hit-test regions

    compare render output in tests

That will be immensely useful.
So the likely philosophy becomes

    Core is toolkit-agnostic.

    Viewport is surface-oriented.

    Rendering starts in software.

    Display representation is backend-neutral.

    GPU acceleration is a later backend, not a foundational assumption.

That is a very solid path.

You’ve now got the bones of a browser architecture that is weird in the right way, which is usually the sign of a good project.

ok. so the only thing i intentionally left out is multimedia. (like screen refresh syncing, layering hardware accelerated video over webpages or random 2d/3d content etc, which is where indeed modern browsers shine). which is mostly about defining viewports and how they get (alpha) overlayed. and webasm. although webasm should be trivial to interpret, albeit slow. 

Yes. And leaving multimedia out on purpose is not a weakness here, it is a scope weapon.

That omission is doing a lot of good work for you.

Because once you fully admit:

    no serious media pipeline yet

    no hardware video overlays yet

    no full game-class rendering yet

    no WebGL/WebGPU circus yet

    no “browser as universal OS” ambitions yet

then the project becomes much more tractable.
Multimedia is really a separate subsystem family

It is not just “some extra tags.”

Proper browser multimedia drags in:

    timing and A/V sync

    buffering and streaming

    codecs

    frame scheduling

    power/performance tradeoffs

    compositing

    alpha blending

    overlays

    fullscreen handling

    DRM nonsense if one goes fully cursed

    input routing for embedded media

    cross-thread coordination

    GPU uploads and texture churn

That is a whole other kingdom.

So I think your instinct is right: define the place where it would plug in, but do not build the empire now.
The correct current move is to define viewport embedding, not multimedia itself

That is the architectural gold.

In the page model, certain elements can eventually resolve to “embedded surfaces” or “active subviewports.”

For now, they can degrade to placeholders.

Later they may become:

    image viewport

    video viewport

    canvas viewport

    2D accelerated region

    3D region

    PDF subviewer

    remote/embed experimental thing

So instead of implementing multimedia, define something like:

    this page box may host a child viewport

    child viewport has bounds, z-order, clip, alpha rules

    child viewport receives repaint/input lifecycle hooks

    parent renderer composites it in a defined way

That is the right level of abstraction.
In other words: define a “surface node” concept

Your layout/render tree could eventually contain ordinary boxes like:

    text box

    image box

    block box

    inline box

    form control box

and also:

    surface box / embedded viewport box

The embedded viewport box would describe:

    rectangle

    clipping region

    stacking order

    transparency model

    focusability

    event routing behavior

    repaint ownership

    fallback representation

For now, fallback could be:

    [Embedded surface not supported]

or perhaps a static preview if available.

That is enough for the architecture.
This is also how you avoid rendering lock-in

If the main renderer knows how to reserve and composite generic surfaces, then later you can support:

    software-only sub-surfaces

    GPU-backed sub-surfaces

    media decoders

    plugin-ish experiments

    canvas-like script surfaces

without rewriting the main layout model.

That is exactly the kind of future-proofing that matters.
On WebAssembly: conceptually yes, practically “trivial” only at one level

You are right in one sense:

    WASM is specified

    stack/memory/machine semantics are much cleaner than JS chaos

    interpreting it is conceptually much more straightforward than implementing full browser JS ecosystems

So at the virtual-machine level, yes, it is much more tractable.

But the catch is that in a browser context WASM is rarely meaningful by itself.

What makes it hard in practice is usually not:

    decoding opcodes

    stepping instructions

but:

    host bindings

    memory/resource limits

    imported functions

    DOM/canvas/network integration

    async/event interaction

    threading/shared memory if ever allowed

    how it talks to JS, if JS exists

    what syscalls-equivalent it gets

So I would phrase it like this:
WASM VM

Reasonably implementable, even interpretable.
WASM browser integration

Not trivial, and should be capability-gated like any other active content.

That fits your philosophy anyway.
A very elegant future model would be: WASM as just another engine

Same idea as JS.

Not special sacred magic. Just another executable content engine with a host capability bridge.

Meaning:

    page requests WASM module

    policy decides whether executable modules are allowed

    chosen engine may be none / interpreter / native runtime

    module receives only granted host capabilities

    resource/time/memory quotas enforced

    no implicit direct browser powers

That would be a much saner model than how the modern web often treats active content.
In your architecture, active content could be unified

This is a beautiful simplification.

Instead of treating JS, WASM, maybe future scripting, and certain embedded surfaces as fundamentally different religions, you can group them under:
Active content

Anything that can:

    compute

    mutate

    fetch

    redraw

    react to events

    consume CPU/memory over time

Then your policy model applies consistently:

    deny by default

    allow once

    allow for tab

    allow same-origin only

    allow with CPU/memory/network limits

    allow with specific host capabilities only

That is cleaner than having one special system for JS, another for WASM, another for media scripting.
Multimedia and WASM both suggest the same abstraction:
ownership of time

Your current browser core mostly lives in a calm world of:

    fetch

    parse

    layout

    draw

    input

    rerender when needed

But multimedia and active compute introduce:

    frame clocks

    continuous updates

    timers

    playback state

    ongoing redraw loops

    scheduling fairness

That means the browser eventually needs a scheduler or runtime coordinator.

Not necessarily now. But the placeholders should allow for it.

For example, a future embedded viewport could declare:

    static

    event-driven

    timer-driven

    frame-driven

For now you only support static and event-driven, perhaps.

That is enough of a design hook.
I would explicitly keep canvas out for a while too

Because once you have canvas, people expect:

    arbitrary drawing

    animation

    maybe game loops

    text measurement

    image decoding/upload

    lots of JS interaction

So unless you want a tiny, tightly constrained canvas later, I would initially treat canvas the same way as video:

    recognized

    represented

    not truly supported

    fallback placeholder

That keeps the project honest.
Your likely support strategy could be
Phase 1

    no multimedia engine

    no active embedded surfaces

    no canvas

    no video/audio playback

    no WASM

    placeholders only

Phase 2

    embedded surface abstraction exists

    static image-like embedded surfaces

    maybe audio download/open externally

    maybe simple animated image support if desired

Phase 3

    constrained active content engine

    JS with restricted host bridge

    perhaps very limited canvas or surface redraw permissions

Phase 4

    optional WASM interpreter backend

    same capability system as JS

    strong quotas

    likely still no high-performance expectation

Phase 5

    multimedia and accelerated surfaces if there is still appetite for pain

That seems sane.
One subtle design point: alpha overlays and compositing should exist in the display model before they are fast

You do not need fast compositing now, but you probably do want the render model to understand concepts like:

    stacking order

    clip regions

    opacity/alpha

    nested surfaces

    overlay layers

Even in software.

Because otherwise later multimedia integration becomes awkward.

So maybe the display list should already support:

    draw commands with alpha

    composited surface entries

    clipping stacks

    z-order groups

Even if the implementation is plain, slow, software blending.

That buys future flexibility cheaply.
My honest take on your WASM remark

I would soften it slightly from “trivial to interpret” to:

    tractable to interpret at the VM level, but only truly useful once host integration and capability control are defined.

That is probably the cleanest statement.

And actually that is good news, because your whole project is already about host integration and capability control.

So WASM is not philosophically awkward here. It fits nicely later.
Bottom line

You are making a very good choice by excluding multimedia as an implementation target while still reserving architectural space for embedded surfaces.

That gives you:

    clean scope

    future extensibility

    no premature media hell

    a natural place for later canvas/video/3D/WASM integration

    consistent policy handling for active content

So yes: define viewport/surface embedding and compositing semantics now, support them minimally, and let real multimedia remain a future citizen of that framework.

That is exactly the kind of restraint that keeps ambitious projects alive.

ok well canvas is likely the thing that sites will use the most. way above webasm which is likely more fore games or specialized tools. so ok.. let's go craft our functional design. also, list MVP but also go over the path for the future to a full-blown feature-rich browser

Policy Browser Functional Design
Policy-First Modular Browser
Functional Design
1. Purpose

This project aims to create a modular browser architecture focused on safety, explicit permissions, controlled resource loading, graceful degradation, and long-term replaceability of nearly every subsystem.

The browser is not initially intended to compete with mainstream browsers on compatibility, performance, multimedia support, or standards coverage. Instead, it is intended to:

    browse a meaningful subset of the web well

    render static and lightly interactive sites readably

    support forms, logins, comments, and basic workflows

    block unwanted or third-party content before fetch by default

    make script execution explicit and capability-based

    support alternative renderers and GUI shells

    support gradual replacement of third-party libraries with custom engines

    serve as both a practical tool and an educational browser platform

2. Product Vision

The system should function as a browser core plus pluggable shells, engines, and render backends.

The core governs:

    navigation

    sessions and tabs

    history

    resource fetching

    MIME classification and handling

    content policy decisions

    cookies and storage

    internal document model

    style and layout pipeline

    active-content permissions

    browser events and commands

Everything else should be replaceable:

    HTML parser

    CSS parser

    JS engine

    WASM engine later

    GUI shell

    page renderer

    image decoders

    media backends later

The browser must degrade safely when capabilities are absent.
3. Guiding Principles
3.1 Safety First

    Deny by default where reasonable.

    Never fetch unwanted third-party resources unless policy permits.

    Never execute active content implicitly if policy forbids it.

    Prefer safer MIME interpretations when ambiguous.

    Unknown or suspicious content should degrade to text, download, or explicit prompt.

3.2 Explicitness

    Every fetch has a reason.

    Every blocked action has an explanation.

    Every active content engine gets only granted capabilities.

    MIME interpretation must be inspectable.

    Permissions may be temporary, session-scoped, per-tab, or persistent.

3.3 Replaceability

    The system owns the internal representations.

    Third-party libraries must be adapted into internal contracts.

    No external library objects may leak across subsystem boundaries.

    Missing engines should degrade behavior, not collapse architecture.

3.4 Graceful Degradation

    No CSS engine: show semantic document.

    No JS engine: forms and links still work where possible.

    No image decoder: show placeholders and metadata.

    No visual shell: console output remains possible.

    Unsupported embedded content: show a placeholder surface.

3.5 Educational Value

    Intermediate structures should be inspectable.

    Debug modes should expose parse trees, layout boxes, display lists, and policy decisions.

    The design should permit gradual replacement by custom implementations.

4. Non-Goals for Initial Releases

The following are explicitly out of scope for MVP and early versions:

    full standards compliance

    Chromium/Firefox-level compatibility

    complete CSS coverage

    complex multimedia pipeline

    GPU-first rendering

    hardware video overlays

    full browser extension system

    WebGL/WebGPU

    service workers

    advanced accessibility parity with major browsers

    complete canvas implementation

    high-performance WASM execution

    highly optimized JavaScript execution

These may be added gradually if architecture supports them.
5. Target Use Cases
5.1 Primary Use Cases

    Read news, blogs, forums, documentation, and wikis.

    Log into traditional sites.

    Submit forms and comments.

    Browse with minimal third-party fetches.

    Browse in highly script-restricted mode.

    Inspect what a page attempts to load and do.

5.2 Example Initial Site Classes

    static content sites

    docs sites

    old-style forums

    comment pages

    wiki-like sites

    simple admin interfaces

    lightly dynamic sites with optional script support

5.3 Explicitly Deferred Site Classes

    SPA-heavy web apps

    media-rich portals

    browser games

    sites relying on modern browser APIs or heavy framework JS

6. System Architecture Overview

The browser is divided into several major layers.
6.1 Core Layer

Responsible for:

    commands and events

    session state

    tabs/pages

    navigation and history

    fetch planning

    policy evaluation

    MIME classification

    handler selection

    permission tracking

    cookies and storage

    active content orchestration

6.2 Parsing and Content Engines Layer

Adapters around:

    HTML parser

    CSS parser

    image decoders

    JS engine

    later WASM engine

    later media decoders

These engines must emit normalized internal representations.
6.3 Document and Layout Layer

Responsible for:

    internal DOM-like tree

    style rule storage

    cascade and computed styles

    layout tree

    embedded surface boxes

    hit-testing support

6.4 Rendering Layer

Responsible for:

    display list generation

    software rasterization

    later GPU rendering backend

    optional text-only or debug rendering

6.5 Shell Layer

Responsible for:

    windows

    tabs UI

    address bar

    menus

    dialogs

    page viewport host

    user input delivery

Shells may include:

    headless

    console

    Tk

    GTK

    Qt later

    web-hosted frontend later

7. Core Data Flow

    User issues command (open URL, click link, submit form, etc.)

    Core creates a navigation or action request.

    Policy decides whether the request is permitted.

    Fetch subsystem retrieves the resource if allowed.

    MIME subsystem classifies claimed and detected content type.

    Handler registry selects a safe handler.

    Handler parses resource into normalized representation.

    Representation is adapted into internal document or content model.

    Style and layout pipeline computes visual structure.

    Render pipeline produces display list.

    Software renderer paints to viewport surface.

    Shell presents the surface and routes future input back to core.

8. Core Internal Models
8.1 Resource Object

Represents any fetched or locally supplied resource.

Suggested fields:

    resource ID

    URL

    final URL after redirects

    initiator reason

    request context

    origin and site info

    headers

    status code

    raw bytes

    encoding

    claimed MIME type

    detected MIME type

    MIME confidence

    trust decision

    chosen handler

    cache metadata

    content hash

8.2 Document Tree

Internal DOM-like structure owned by the browser.

Node categories:

    document node

    element node

    text node

    comment node optional

    special embedded surface node later

Element data:

    tag name

    normalized attributes

    children

    parent reference

    source location optional

    computed style reference

    layout box reference

    event hooks if needed

8.3 Style Model

    parsed selectors and declarations

    specified styles

    computed styles

    inherited values

    defaults and fallback values

8.4 Layout Model

    block boxes

    inline boxes

    text runs

    table boxes or simplified table layout nodes

    replaced boxes for images

    embedded surface boxes for future canvas/video/etc.

    clipping and stacking metadata

    hit-test geometry

8.5 Display List

Backend-neutral paint operations such as:

    fill rect

    draw border

    draw text run

    draw image

    push clip

    pop clip

    composite surface

    placeholder draw

8.6 Capability/Permission Model

Permissions associated with:

    page

    origin

    tab

    session

    user action

    engine instance

Capability examples:

    execute inline JS

    execute same-origin JS

    execute third-party JS

    perform network fetch from script

    create timers

    mutate DOM

    submit forms

    set cookies

    persistent storage

    use canvas later

    load WASM later

9. Command and Event Architecture

The system should be command-driven and event-driven to support pluggable GUIs.
9.1 Commands Into Core

Examples:

    open_url

    reload

    stop_load

    back

    forward

    click_at

    hover_at

    scroll_by

    key_press

    text_input

    submit_form

    allow_capability_once

    set_site_policy

    close_tab

    duplicate_tab

9.2 Events Out of Core

Examples:

    page_load_started

    page_load_progress

    page_load_finished

    page_failed

    title_changed

    url_changed

    history_changed

    render_invalidated

    permission_requested

    resource_blocked

    script_blocked

    status_message

    console_log

    handler_warning

This interface must remain independent of GUI toolkit specifics.
10. MIME Handling Design

MIME interpretation is a first-class policy concern.
10.1 Inputs

    claimed MIME type from headers

    file extension hints

    content sniffing result

    context of request

    user/site policy

10.2 Output Decision

Possible decisions:

    handle as HTML

    handle as CSS

    handle as plain text

    handle as image

    handle as script

    handle as JSON

    treat as download

    prompt user

    reject

10.3 Policy Modes
Strict Mode

    no dangerous upward sniffing

    do not reinterpret plain text as HTML automatically

    unknown active content denied

    safer handler preferred when content disagrees with headers

Balanced Mode

    permit conservative recovery for common broken servers

    still deny suspicious active upgrades

Compatibility Mode

    more browser-like behavior for mislabeled but common content

10.4 Examples

    text/plain containing HTML: display as text unless user explicitly chooses HTML handling.

    unknown binary: offer download, do not execute.

    SVG: may be rendered as image-only with script disabled by default.

    XML: display as text or structured XML viewer, not implicitly as HTML.

11. Resource Fetch and Policy Engine

Each fetch must have an explicit reason.
11.1 Fetch Reasons

    top-level navigation

    stylesheet request

    image request

    script request

    form submission

    iframe request later

    media request later

    script-initiated request

11.2 Policy Questions

    same-origin or third-party?

    active or passive resource?

    allowed by global policy?

    allowed by site policy?

    allowed by tab/session permissions?

    matches block rules or ad/tracker rules?

    exceeds resource budget?

11.3 Resource Budgets

Optional and desirable even early:

    max requests per page

    max total bytes per page

    max DOM nodes

    max scripts

    max timer count later

    max active surface count later

11.4 Unwanted Content Blocking

The browser should block unwanted content before fetch where possible.

Examples:

    third-party scripts

    tracking pixels

    known ad hosts

    known analytics requests

    third-party iframes later

    autoplay media later

12. Cookie, Storage, and Session Handling
12.1 Cookies

Core owns cookie jar logic. Capabilities and policy should support:

    allow session cookies only

    allow persistent cookies per site

    block third-party cookies by default

    inspect cookie changes

    clear on tab close or browser exit optionally

12.2 Storage

Early storage may be minimal. Possible modes:

    none

    memory-only

    per-session

    persistent per site

Initially defer complex web storage APIs until script model matures.
13. HTML Support Plan
13.1 MVP HTML Coverage

    html, head, body

    title

    headings

    p, div, span

    strong, em, b, i

    a

    ul, ol, li

    img

    table, tr, td, th with simplified rules

    pre, code

    form

    input

    textarea

    button

    select, option if practical

    hr, br

13.2 Deferred HTML Features

    iframe full support

    shadow DOM

    custom elements semantics

    multimedia tags with full playback

    advanced form features beyond basics

14. CSS Support Plan
14.1 MVP CSS Coverage

Selectors:

    element

    class

    id

    simple descendants

Properties:

    color

    background-color

    font-size

    font-weight

    font-style

    text-decoration limited

    margin

    padding

    border

    width and height basic

    display block/inline/none

    white-space basic

    text-align

    overflow limited

14.2 Layout Behavior Initially Supported

    block flow

    inline text flow

    simple replaced element sizing

    simplified tables

    clipping basics

    scrolling

14.3 Deferred CSS

    grid

    full flexbox

    transforms

    animations

    sticky positioning

    complex pseudo-elements and pseudo-classes

    sophisticated media queries

15. JavaScript Execution Model

JavaScript should be capability-based and explicitly controlled.
15.1 Initial Policy Levels
Level 0: No JS

    page remains static

    links and basic forms still work

Level 1: Run Once / User-Triggered

    script allowed only for specific user action

    no timers

    no background network

    no persistent storage

    minimal DOM mutation

Level 2: Same-Origin Restricted

    same-origin scripts may run

    capability-limited DOM and event access

    optional temporary storage

    no or restricted script-initiated network

Level 3: Compatibility Mode

    broader browser-like behavior for selected sites later

15.2 JS Engine Requirements

    replaceable backend

    capability bridge owned by browser core

    time and step budgeting

    memory budgeting where practical

    logging of denied actions

15.3 JS MVP Strategy

For MVP, JS support may be absent or extremely limited. The architecture must support later addition.
16. Canvas and Active Surface Strategy

Canvas is likely more important than WASM in real-world compatibility.
16.1 MVP

    recognize canvas elements

    reserve layout space

    display placeholder or fallback text

    no true canvas drawing yet

16.2 Later Support

Canvas should integrate via embedded surface abstraction. Possible modes:

    disabled placeholder

    simple software canvas with limited API

    capability-gated canvas

    accelerated canvas later via GPU-backed surface

Canvas access should count as active content and be policy-controlled.
17. WASM Strategy
17.1 MVP

    recognize but do not execute

    display diagnostic or block message when relevant

17.2 Later

    optional interpreted WASM backend

    capability-gated host bridge

    strict resource quotas

    no implicit privileged browser access

WASM is treated as active content, not as a trusted special case.
18. Embedded Surface / Viewport Abstraction

To support future canvas, video, or accelerated content, layout must understand embedded surfaces.

Each embedded surface box may specify:

    rectangle

    clipping region

    z-order

    alpha/opacity

    repaint ownership

    focusability

    event routing behavior

    fallback placeholder behavior

MVP implementation may only display placeholders.
19. Rendering Architecture
19.1 Software Renderer First

The initial browser should use software rendering. Reasons:

    deterministic behavior

    easier debugging

    simpler testability

    less dependency complexity

    easier screenshots and regression testing

19.2 Rendering Pipeline

    internal document model

    computed style tree

    layout tree

    display list

    software rasterizer

    framebuffer/surface

    shell viewport presentation

19.3 Future GPU Path

Later, the same display list or scene tree may be consumed by:

    OpenGL backend

    other accelerated backend

The browser’s conceptual model remains 2D.
20. GUI / Shell Architecture

The GUI must be pluggable.
20.1 Shell Responsibilities

    windows

    tabs

    address bar

    navigation buttons

    menus

    permission prompts

    downloads UI later

    viewport hosting

    focus management integration

20.2 Shell Types

    headless shell

    console shell

    Tk shell

    GTK shell

    Qt shell later

    web frontend later

20.3 Viewport Host Responsibilities

    allocate and resize drawing area

    present current rendered surface

    forward input events

    report focus changes

    request redraws

20.4 Rule

Browser core must not depend on any toolkit-specific widget classes.
21. Plugin and Engine Registry

The browser should support registries for:

    shells

    renderers

    HTML parsers

    CSS parsers

    JS engines

    image handlers

    MIME handlers

    policy profiles

Configuration should permit combinations such as:

    shell = gtk, renderer = software, js = none

    shell = console, renderer = text_only, js = none

    shell = tk, renderer = software, js = restricted

22. Degradation Contracts

Each subsystem should specify behavior if unavailable.
22.1 No CSS Engine

    render semantic HTML with defaults

22.2 No Image Decoder

    show placeholder, alt text, dimensions if known

22.3 No JS Engine

    static mode only

22.4 No Visual Shell

    console/headless mode

22.5 Unsupported Embedded Surface

    reserved rectangle and placeholder

22.6 MIME Unhandled

    prompt, safe download, or plain text fallback

23. Debugging and Inspection Features

Strong debug support is part of the design.

Desired tools:

    resource/fetch graph

    blocked resource log

    MIME classification report

    document tree dump

    computed style dump

    layout box overlay

    display list dump

    render invalidation tracing

    capability/permission log

    console-only page summary

24. Project Structure Proposal
browser/
  core/
    commands/
    events/
    session/
    tabs/
    history/
    policy/
    mime/
    fetch/
    handlers/
    cookies/
    storage/
  document/
    dom/
    styles/
    layout/
    surfaces/
  render/
    display_list/
    software/
    text_only/
    debug/
  engines/
    html/
    css/
    js/
    wasm/
    image/
  shell_api/
  shells/
    headless/
    console/
    tk/
    gtk/
  plugins/
  tests/
  tools/
25. MVP Definition

The MVP must be intentionally small but coherent.
25.1 MVP Goals

    open a URL

    fetch top-level HTML

    parse HTML into internal document tree

    render text, links, headings, paragraphs, lists, images placeholders, and simple forms

    support basic CSS subset

    support navigation and history

    support GET/POST form submission

    handle cookies at least minimally

    block third-party scripts/resources by default

    provide headless or console diagnostic mode

    provide one visual shell

    provide software rendering

    explain blocked resources

25.2 MVP JS

One of two valid MVP positions:

    no JS at all, but architecture ready

    very limited run-once/script-disabled-by-default framework without broad DOM APIs

25.3 MVP Canvas/WASM/Media

    recognized only

    no execution/rendering beyond placeholders

25.4 MVP Benchmark Tasks

    read a simple blog page

    browse a documentation page

    load and submit a login form on a simple site

    read a forum thread

    submit a plain comment form on a compatible site

    display blocked resource list for a page

26. Milestone Roadmap
Milestone 1: Core Skeleton

    command/event bus

    shell API

    headless shell

    fetch subsystem

    resource object

    MIME classifier skeleton

    handler registry

Milestone 2: Minimal Document Browser

    HTML parsing adapter

    internal document tree

    semantic text-only rendering

    links and navigation

    console output mode

Milestone 3: Basic Visual Browser

    one GUI shell

    software surface

    layout tree

    display list

    basic rasterizer

    headings/paragraphs/lists/links/images placeholders

    scroll support

Milestone 4: Interaction and Forms

    forms

    inputs

    buttons

    text entry

    cookies

    history

    POST handling

Milestone 5: Styling and Policy Maturity

    CSS subset

    third-party blocking rules

    MIME policy modes

    blocked-resource explanations

    resource budgeting

Milestone 6: Active Content Framework

    JS engine interface

    capability bridge

    permissions UI

    no-op engine and restricted engine placeholder

Milestone 7: Canvas and Embedded Surface Foundation

    embedded surface boxes

    placeholders

    future canvas API boundaries

Milestone 8: Restricted JS / Limited Canvas

    optional run-once scripts

    limited DOM bridge

    limited canvas if pursued

Milestone 9+: Compatibility Expansion

    better CSS

    better forms

    same-origin script mode

    improved image/rendering support

    optional WASM interpreter

    accelerated rendering backend

    richer GUI shells

27. Path Toward a Full-Blown Feature-Rich Browser

This section describes the growth path, not a short-term commitment.
Stage A: Practical Safe Browser

    static and lightly interactive pages

    strong policy controls

    excellent diagnostics

    reliable forms and cookies

Stage B: Modernized Reader Browser

    better CSS coverage

    better fonts and text handling

    better images

    partial JS support

    canvas placeholders or limited support

Stage C: Constrained Interactive Browser

    controlled same-origin JS

    limited canvas

    improved DOM APIs

    better event model

    stronger site compatibility

Stage D: Rich Surface Browser

    embedded active surfaces

    multimedia subsystem beginnings

    better compositing

    optional accelerated rendering

Stage E: Advanced Browser Platform

    fuller CSS

    stronger JS compatibility

    optional interpreted or hybrid WASM

    broader HTML feature coverage

    richer plugin ecosystem

    advanced dev/debug tools

Stage F: Feature-Rich Browser

Potential eventual features:

    richer multimedia

    more advanced CSS/layout

    broader DOM APIs

    canvas maturity

    WASM execution options

    accelerated compositing

    high-end GUI polish

This stage should only be pursued if earlier stages remain architecturally healthy.
28. Key Risks

    scope explosion

    CSS/layout rabbit hole

    GUI leakage into core

    library objects leaking across boundaries

    overcommitting to JS too early

    overcommitting to compatibility too early

    accidental monolith through convenience shortcuts

29. Key Success Criteria

The project is successful if it achieves the following:

    architecture remains modular and inspectable

    headless or console mode remains viable

    one can browse a meaningful subset of the web safely

    forms and simple login/comment flows work on compatible sites

    blocked resources are prevented before fetch where possible

    replacing engines remains feasible

    future multimedia/canvas/WASM additions have a defined architectural home

30. Immediate Implementation Recommendation

Start with:

    Python

    software rendering

    headless shell first or alongside the first GUI shell

    one GUI shell only for initial implementation

    no JS or near-zero JS in MVP

    strong internal models and adapters

    strict avoidance of toolkit/library leakage into core

The first success should be a readable, navigable, diagnosable browser that is architecturally clean rather than visually complete.

I drafted the functional design in the canvas: Policy Browser Functional Design.

Highlights:

    clear MVP scope

    modular core / engines / render / shell split

    MIME policy as a first-class system

    canvas positioned as a future embedded-surface feature, with placeholders first

    GUI-pluggable architecture

    software renderer first, GPU later

    roadmap from safe minimal browser to feature-rich browser

A few decisions in the draft are intentionally firm:

    Python-first

    one real GUI shell at first, plus headless/console thinking

    no serious JS in MVP, but full framework for later

    multimedia deferred, but architectural hooks included

    strong degradation contracts everywhere

The next useful step is probably to refine it into a more implementation-ready spec with:

    exact module interfaces

    concrete internal dataclasses

    startup/plugin config format

    first milestone file tree

    benchmark target sites/tasks

I can do that next and turn it into a sister-AI-ready engineering spec.


