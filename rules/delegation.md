---
description: "The boundary between work handed to a subagent and work the orchestrator keeps, which role fits, the access rights a role may not extend on the fly, and the mandatory Handoff format between subagents. Load before launching a subagent or when a chain of subagents works on one change. Триггеры: делегирование, субагент, границы делегирования, оркестратор делает сам, права роли, доступ только на чтение, передача между агентами, handoff."
alwaysApply: false
kind: process
---

# Delegation and subagent handoff

The registry of roles is `agents/ROLES.md`; the role bodies live in
`.kun/agents/<role>.md`. This rule says *when* to hand work over and *how* to
hand it over so the receiving agent does not re-discover what is already
known.

## When to delegate

Delegate only large, genuinely independent, parallelizable work — a wide
multi-file survey, a stream with its own write zone. Everything else the
orchestrator does itself.

- Do not delegate what you would finish in a few tool calls: the launch
  overhead exceeds the work.
- Do not use subagents to check or re-check your own work.
- One subagent closes the task — launch one, not several. A fan-out of
  workers is a deliberate decision, not a reflex.
- Heavy multi-file implementation is **not** a delegation case by default:
  it is dense and cross-linked, and cheaper done directly than specified,
  handed over and reconciled.

Task decomposition, final decisions and result integration stay with the
orchestrator. Scouting subagents' reports are not trusted blindly — key
facts are spot-checked against the primary sources.

**Why reconnaissance still goes to a subagent.** Not for the token price: it
keeps the orchestrator's context clean. Directory walks, grep output and
dead-end reads do not belong in the lead session — they push out what the
orchestrator actually reasons over.

## Rights discipline

A `readOnly` role has read and search only. Rights are not extended on the
fly: if the task needs writes, take the writing role that owns that work
instead of loosening a read-only one. The textual ban inside the role body
is the backstop for a misconfigured tool policy — keep it.

## The script rule

Writing and changing scripts is work for a full-tier role; executing an
already written and verified script and collecting logs is work for a light
executor.

Reason: an executor on a light model, when it hits an error, tends to "fix"
the input files and invent failure causes instead of reporting the error as
a fact. So the executor gets copies of the inputs, and its report is checked
against the real logs rather than trusted as a retelling.

One-shot runs are the exception: launching a ready script or a test suite
that writes a machine-readable report costs the orchestrator only the
compact verdict — running it directly is cheaper than a subagent launch.
What gets delegated is the iteration: a failed run hands the *report path*
(not the pasted log) to the fixing role, which owns the run-read-fix loop in
its own context.

## Reasoning stays internal

Never ask a subagent to reveal its internal reasoning ("show your thinking",
"explain your chain of thought step by step"). The useful artifact is a
concise rationale plus tool-backed evidence — exactly what the Handoff
format below already requires. The same applies in reverse: agents report
rationale and evidence, not raw reasoning.

## Handoff between subagents

When one change is split across several implementing subagents (typical
chain: `developer` writes the bulk, then `tester` verifies; or `explorer`
maps the ground, then `developer` edits), the orchestrator **must** stop the
downstream subagent from re-reading what the upstream already produced.
Re-reading bloats the downstream context and is the recurring failure mode
of informal chains.

The mechanism is a fixed-format **Handoff** block that the upstream subagent
places at the top of its final report, the orchestrator passes on verbatim,
and the downstream subagent treats as the authoritative inventory.

> Not the same thing as the `## Handoff` section of a role definition. That
> one is the subagent's prose report *to the orchestrator*. This block is a
> machine-readable *inventory for the next subagent*, and it sits on top of
> that report.

**Mandatory format:**

```text
## Handoff (for the next subagent)

### Artifacts
- <full repo path> — <one-line role> [stub | done | edited]

### Public surface
- <ObjectName>.<RoutineName>(<params>) → <return type> — <one-line purpose>

### Open TODOs / stubs (for the next subagent)
- <file>:<region or routine> — <what to implement> — <signature hint, if pre-agreed>

### Locked decisions (do not revisit without approval)
- <decision> — <one-line rationale>

### Open questions raised
- CONFUSION-<n> — <one-line summary> — <status: resolved / pending>
```

A `CONFUSION-<n>` (sequential within the change) is an open question the
subagent could not resolve inside its boundaries: add it with status
`pending` and report to the orchestrator, which resolves it or takes it to
the user. A locked decision that blocks a correct implementation becomes a
CONFUSION; it is never silently overridden.

Keep every line short (≤120 chars), one fact per line, no prose paragraphs
inside the block.

**Orchestrator responsibilities:**

- Include the upstream Handoff block **verbatim** in the next subagent's
  prompt under the heading `## Upstream Handoff`. No retelling, reformatting
  or selective omission — retelling is the main source of drift.
- Additional instructions go in a separate section *after* `## Upstream
  Handoff`, not mixed into it.

**Downstream subagent responsibilities:**

- Read `## Upstream Handoff` first and treat `### Artifacts`, `### Public
  surface` and `### Locked decisions` as authoritative. Rediscovering them by
  reading files is forbidden.
- No broad re-reads of objects already listed in the Handoff "for context".
  A targeted call is allowed only when a specific detail needed for the
  current edit is missing from the Handoff — name the missing detail in one
  sentence before making the call.
- Preserve `### Locked decisions` unless the user (not the orchestrator)
  allows a revision.
- Add your own Handoff block if yet another subagent is expected.

**Anti-patterns:** opening every file from `### Artifacts` "to load context"
(the inventory *is* the context); retelling the Handoff "to keep it short";
a Handoff that only says "see the files above"; prose essays inside
`### Locked decisions`.

## Companion rules

- `collaboration-modes.md` — which mode the work runs in and whether it is a
  delegation case at all.
- `session-handoff.md` — the same discipline across sessions, not across
  subagents.
- `verification-matrix.md` — what the orchestrator checks before accepting a
  subagent's result.
