## 2026-04-23 21:40 CET — codex → codex — [FYI] [handover]

State at handoff:

- `P9` advanced materially:
  - same-origin stylesheet fetch/apply is in
  - descendant selectors are in
  - local image decode + software blit are in
  - basic margin/padding/font-size layout effects are in
  - passive asset budgets are in

- `P10` now has a real boundary instead of silent noops:
  - script tags become explicit execution requests
  - blocked script execution emits `PermissionRequested`
  - console shell exposes active-content requests via `permissions`
  - remembered grants live in `core/policy/permissions.py`

Key current shapes:

- `PageLoadResult.scripts` is `dict[NodeId, ScriptExecutionRecord]`
- `ScriptExecutionRecord` carries:
  - `url`
  - `origin`
  - `inline`
  - `source`
  - `result`

Important constraint:

- permission grants do **not** enable JS execution
- they only suppress repeated permission events
- JS still stays blocked by the noop engine

Recent commits from this run:

- `1634009` Emit permission events for blocked script execution
- `e641f41` Expose active content requests in console shell
- `33a4cba` Store granted active-content permissions
- `08f1e87` chat handoff notes for Claude and Gemini Flash

Best next engineering move:

1. Review the newer architecture commits already on top of this branch:
   - `b8aef91` subresource gateway extraction
   - `3a89d00` permission service with command-bus grants
   - `87d1f3d` Claude handoff

2. Then choose one direction cleanly:
   - `P10`: wire actual shell-facing grant/deny flow through the new permission
     service
   - `P9`: improve inheritance/cascade and layout fidelity

3. If touching `PageLoader` again, resist making it broader. The next cleanup is
   extraction, not another responsibility pile-on.

Verification baseline before further edits:

- `.venv/bin/pytest`
- `tools/check_guardrails.sh`

— c

## 2026-04-25 00:30 CET — codex → codex — [FYI] [handover]

JS-own class work is now materially complete on the public/private surface.

New commit chain on top of the earlier class work:

- `2118c7a` Add arrow functions to standalone JS interpreter
- `6c7e1c8` Add JS class core and fix DOM truncation cap
- `f1dbbd4` Add JS class inheritance and super support
- `daee577` Add JS class expressions and static methods
- `d390d61` Add JS instance fields
- `0c0801b` Add JS class getters and setters
- `b1f20e1` Add JS static fields
- `26f1608` Add JS computed class member names
- pending next commit in this session: private fields/methods/accessors

Private-member implementation notes:

- tokenizer now emits `PRIVATE_IDENTIFIER` for `#name`
- parser supports:
  - private fields
  - private methods
  - private accessors
  - `obj.#name` member access
- runtime model uses per-class brand storage:
  - instance private slots live on instance dicts under `__class_private_instance__`
  - static private slots live on `JavaScriptClass.private_static_slots`
- private access is lexically scoped through `__current_class__`
- brand checks are enforced:
  - base-class private access works on subclass instances when base branding ran
  - subclass code cannot directly access base private names
- static private members are in for the supported slice

Current verification baseline in this session:

- focused JS-own parser/interpreter/reference tests -> `154 passed`
- `.venv/bin/pytest -q` -> `379 passed`
- `tools/check_guardrails.sh` -> pass

Still intentionally deferred after this:

- private methods/fields in browser wiring
- async/promises/event loop
- broader syntax like template literals/modules

Worktree caveat remains:

- keep ignoring untracked `scratch/` unless user explicitly wants it handled

— c

## 2026-04-25 00:55 CET — codex → codex — [FYI] [handover]

Follow-up JS-own runtime-control slice landed after private members:

- template literals are now supported in the standalone interpreter
- minimal runtime config exists in `neuzelaar/engines/js_own/config.py`
- budget tracking exists in `neuzelaar/engines/js_own/execution.py`
- current budget knobs:
  - `max_steps`
  - `max_wall_ms`

Important scope boundary:

- this is still interpreter-local control, not scheduler/event-loop work
- no browser task queue or async runtime has been introduced yet
- `OwnJavaScriptEngine` can now receive a `ScriptRuntimeConfig`

Implementation note:

- budget checks currently tick at `evaluate_statement()` and `evaluate_expr()`
- this is good enough for coarse runaway-script protection
- later scheduler work should reuse the config model but likely move to a
  richer runtime/task object rather than more global state

Verification after this slice:

- focused JS-own tests -> `165 passed`
- full suite -> `386 passed`
- `tools/check_guardrails.sh` -> pass

Recommended next move:

1. define a small script-task/scheduler model
2. make the runtime config keys line up with the future settings namespace
3. only then start promise work

— c

## 2026-04-25 01:10 CET — codex → codex — [FYI] [handover]

Scheduler-debug groundwork landed after runtime budgets.

What exists now:

- `neuzelaar/engines/js_own/scheduler.py`
  - `ScriptTaskState`
  - `ScriptTask`
  - `ScriptTaskSnapshot`
  - `ScriptScheduler`
- `ScriptRuntimeConfig` now also carries:
  - `debug_track_tasks`
  - `debug_keep_history`
  - `debug_max_history`

Current integration scope:

- host timer stubs can register `setTimeout` work as background scheduler tasks
- `clearTimeout` cancels the corresponding queued task
- scenario fixtures can opt into scheduler debug with `scheduler_debug=True`
- this is visible to tests through `BrowserHostStubs.scheduler`

Important boundary:

- this still does not execute queued timer callbacks
- there is still no microtask queue, promise scheduler, or async runtime
- treat this as observability/control-plane groundwork only

Verification after this slice:

- host/practical fixture tests -> `18 passed`
- full suite -> `389 passed`
- `tools/check_guardrails.sh` -> pass

Recommended next move:

1. line up scheduler/runtime config naming with future settings keys
2. decide the foreground/background task kinds and priorities explicitly
3. then start promise core on top of this model

— c

## 2026-04-25 01:25 CET — codex → codex — [FYI] [handover]

The scheduler/config cleanup needed before promise work is now in.

What changed:

- `ScriptRuntimeConfig` now has stable settings-style keys and helpers:
  - `from_settings(...)`
  - `to_settings()`
- current key set:
  - `script-budget-max_steps`
  - `script-budget-max_ms`
  - `script-debug-track_tasks`
  - `script-debug-keep_history`
  - `script-debug-max_history`
- scheduler task taxonomy is now explicit:
  - `ScriptTaskKind`
    - `foreground-script`
    - `click-handler`
    - `timer`
    - `microtask`
    - `background-script`
  - `ScriptTaskPriority`
    - `user-blocking`
    - `foreground`
    - `normal`
    - `background`

Why this matters:

- future UI/storage can hand the runtime one abstract settings snapshot
- future promise/microtask work can target explicit task kinds instead of raw
  strings
- scheduler debug output is now less likely to drift semantically

Verification after this slice:

- host-focused tests -> `17 passed`
- full suite -> `391 passed`
- `tools/check_guardrails.sh` -> pass

At this point the next real JS runtime step is promise core.

— c

## 2026-04-25 00:00 CET — codex → codex — [FYI] [handover]

Standalone JS interpreter status now:

- public class surface is largely in:
  - class declarations
  - class expressions
  - `extends`
  - `super(...)`
  - `super.method(...)`
  - static methods
  - instance fields
  - getters/setters
  - static fields
  - computed method/field/accessor names

Recent JS-own commits in order:

- `6c7e1c8` Add JS class core and fix DOM truncation cap
- `f1dbbd4` Add JS class inheritance and super support
- `daee577` Add JS class expressions and static methods
- `d390d61` Add JS instance fields
- `0c0801b` Add JS class getters and setters
- `b1f20e1` Add JS static fields
- `26f1608` Add JS computed class member names

Current repo verification baseline after `26f1608`:

- `.venv/bin/pytest -q` -> `355 passed`
- `tools/check_guardrails.sh` -> pass

Important class/runtime notes:

- static field initializers run at class-definition time
- class binding is still in its initialization window during static field
  evaluation, so tests should use `this`, not the class name, there
- descriptor-backed accessors are in for:
  - instance getters/setters
  - static getters/setters
  - inherited accessors
  - `super.value` reads/writes
- computed accessors required explicit parser handling for:
  - `get [expr]() {}`
  - `set [expr](x) {}`

Next highest-value JS-own work:

1. Private fields/methods
   - this is the next real architecture jump
   - needs private-name scoping and brand checks
   - do not treat it like normal property syntax sugar

2. After that, likely:
   - maybe static private fields
   - maybe class conformance cleanup / larger practical fixture set

3. Keep async/promises/event loop deferred until the class/object model feels
   stable enough.

Worktree caveat at handoff:

- there are unrelated dirty changes in:
  - `neuzelaar/document/bfc.py`
  - `neuzelaar/document/layout.py`
  - `neuzelaar/document/styles.py`
- plus untracked `scratch/`
- do not roll those into JS commits unless intentionally coordinating with the
  CSS/layout line

— c
