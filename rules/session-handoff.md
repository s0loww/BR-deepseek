---
description: "Handing work over between agent sessions: when to fork a fresh session vs compact the current one, what goes into the handoff document and where it lives. Load when a task outgrows one context window or the user asks to continue elsewhere. Триггеры: передача сессии, хэндофф, новая сессия, контекст переполняется, компакт."
alwaysApply: false
kind: process
---

# Session handoff

Adapted from the `handoff` skill of
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT). This rule
covers handover **between sessions**; the Handoff block **between
implementing subagents** inside one change is defined in
`delegation.md` — same discipline (inventory, not retelling),
different scope.

## Fork vs continue

- **Handoff forks.** A handoff document seeds a *fresh* session with a clean
  window. Use it at a phase boundary, or when the current window has
  degraded past useful work.
- **Compaction continues.** Summarizing the current context keeps the same
  session going. Acceptable between phases; **do not compact mid-phase** —
  finish the phase or hand off at its boundary. A compaction loses exactly
  the fine-grained state a phase in flight depends on.
- Quality drops long before the hard context limit: past roughly the first
  half of the window ("smart zone", on the order of 100–150k tokens on
  current large models) reasoning gets dull. Plan the handoff *before* the
  edge — a handoff written by a degraded session inherits the degradation.

## What goes into the handoff document

1. **Focus** — what the next session is for, one or two lines. If the user
   named it, use their wording.
2. **State of work** — done / in progress / not started, by plan step if a
   plan exists.
3. **Artifacts by reference** — paths, change ids, commit hashes. **Do not
   duplicate content that already lives in artifacts** (specs, plans,
   workspace documents, commits, diffs): the handoff points, it does not
   retell. Duplicated content drifts from its source and the next session
   trusts the stale copy.
4. **Locked decisions** — one line each, with the reason; the next session
   does not reopen them without the user.
5. **Open questions** — unresolved items, each with what is blocking it.
6. **Suggested loads** — which rules from the Rule Index, which roles and
   which project-profile tools the next session will most likely need.

## Where it lives

- Write to the project's temporary directory (`var/tmp/` by convention) —
  **not** into the repository tree. A handoff is transport, not an artifact:
  committed handoffs rot into a second, stale source of truth.
- Redact secrets and personal data before writing: the file may outlive the
  session and be read outside the original context.
- If the work state belongs in a durable artifact (a plan step done, a
  decision made) — record it there first, then reference it from the
  handoff. The handoff must never be the only carrier of a durable fact.

## Companion rules

- `delegation.md` — the in-change Handoff block between subagents;
  its anti-patterns (retelling, "see the files above") apply here verbatim.
