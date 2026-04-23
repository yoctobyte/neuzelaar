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
