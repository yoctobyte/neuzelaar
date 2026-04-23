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
