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
