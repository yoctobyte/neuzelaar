# Project Packages

This file organizes Neuzelaar 2 into complete deliverable packages.

Use this for execution order. Use `TODO.md` for current status. Use
`docs/deferred_details.md` for ideas that are real but intentionally postponed.

## P1. Headless Core

Goal:

- load a page
- classify it safely
- parse it into internal nodes
- render semantic text
- evaluate planned subresources before fetch

Status:

- complete

Delivered:

- `PageLoader`
- `HeadlessShell`
- strict planned-resource blocking
- M1 test suite

## P2. Minimal Browser State

Goal:

- keep browsing state over time instead of one-shot page loads

Status:

- complete

Delivered:

- `BrowserSession`
- in-memory history
- link following
- session cookie jar
- console shell commands
- page load/resource-blocked events

## P3. Visual Foundation

Goal:

- produce actual frames from document content through replaceable rendering layers

Status:

- complete for MVP baseline

Delivered:

- minimal layout
- display list
- software rasterizer
- neutral `Frame`
- Tk shell frame path
- scroll support

Open verification:

- manual GUI smoke check on a machine with a display

## P4. Traditional Web Workflows

Goal:

- support the basic non-JS workflows users expect from classic sites

Status:

- complete for MVP baseline

Delivered:

- form extraction
- GET submission
- POST submission
- fixture-server form flow

Still deferred:

- text editing polish
- richer form controls
- login persistence beyond session cookies

## P5. Tiny Styling Layer

Goal:

- support enough styling that rendered pages stop feeling purely diagnostic

Status:

- complete for MVP baseline

Delivered:

- inline styles
- `<style>` blocks
- tinycss2 adapter
- root color/background application
- descendant selector matching

Still deferred:

- broader selector support beyond simple descendant chains
- full cascade/inheritance behavior

## P6. Active Content Boundary

Goal:

- define how active content is represented and blocked before real execution exists

Status:

- complete for MVP baseline

Delivered:

- capability contracts
- JS noop engine
- WASM noop engine

Still deferred:

- inline script planning as active-execution requests
- permissions UI
- restricted execution engine

## P7. MVP Hardening

Goal:

- make the current MVP trustworthy to extend

Status:

- in progress

Remaining:

- manual GUI verification
- small doc pass after GUI verification
- one concise release-style note for the MVP checkpoint

## P8. Post-MVP Browser State

Goal:

- become a practical browser rather than a single-session demo

Status:

- complete for current package scope

Delivered:

- persistent cookie jar
- multi-tab model
- per-tab history isolation
- console shell tab commands

Still deferred:

- multi-tab visual UI
- persistent history

## P9. Post-MVP Styling And Compatibility

Goal:

- improve readability and compatibility without breaking the policy-first model

Status:

- in progress

Delivered:

- same-origin external stylesheet fetch/apply under policy
- local image decode and software blit path
- descendant selector support for the tiny CSS slice
- basic margin/padding/font-size effect on layout
- image `width`/`height` attribute sizing
- per-page passive asset budgets for stylesheets/images

Remaining:

- broader CSS subset
- better layout and image sizing
- richer resource budget controls

## P10. Post-MVP Active Content

Goal:

- add explicit, inspectable active content behavior

Status:

- in progress

Scope:

- explicit inline/external script execution requests
- blocked script permission events with capability/origin metadata
- console diagnostics for active-content requests
- permission store for remembered grants
- permission events/prompts
- restricted JS execution
- capability bridge
- later canvas and WASM integration
