# Deferred Details

This file is for real details that matter later, but should not slow down the
current package being implemented.

The rule is simple: if a detail does not change today's code boundary, it goes
here instead of bloating `TODO.md`.

## GUI Verification

- Run Tk shell on a machine with a real display.
- Verify a simple page renders visibly.
- Verify scrolling works for a tall page.
- Verify text does not overlap in the basic fixtures.
- Capture short notes in `workdone-gemini-flash.md`.

## Forms

- richer input types
- submit button semantics
- keyboard focus model
- text editing behavior
- form validation policy

## Cookies And Storage

- persistent cookie jar
- cookie expiration
- storage policy modes
- per-site persistence settings

## CSS

- external stylesheet fetch/apply
- inheritance rules
- class/id/descendant coverage review
- margin/padding effect on layout
- text alignment and font-size effect on layout metrics

## Rendering

- display list expansion for borders/clips
- richer image rendering than placeholders
- debug overlays
- font choices and metrics beyond default font

## Active Content

- inline script planning
- external script execution requests
- permission prompts
- capability budget enforcement

## Browser State

- multi-tab model
- per-tab isolation
- reload/stop
- richer history model

## Tooling

- release checklist
- fixture naming conventions as the fixture set grows
- optional CI script that wraps pytest + guardrails
