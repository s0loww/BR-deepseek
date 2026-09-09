---
description: "Feedback-loop debugging method: build a red-capable reproduction command before any hypothesis, instrument one variable at a time, close with a regression test. Load for any bug, runtime error, regression or performance regression. Триггеры: отладка, баг, ошибка, воспроизведение, регрессия."
alwaysApply: false
kind: process
---

# Debugging loop

Adapted from the `diagnosing-bugs` skill of
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT). A stack
overlay may ship a platform adaptation of this method with concrete
debugger, log and query tooling — its phase structure may differ. On tasks
inside the overlay's stack the adaptation takes precedence; this rule
governs everything else (scripts, tooling, cross-stack code). The shared
core principle either way: reproduce first, hypothesize second, change code
last. Concrete tool names come from the root contract.

## Core principle

> **No red-capable command — no hypotheses.**

Until one command exists that reproduces the bug and fails on it, do not
theorize about the cause. Every "should be fixed now" without a reproduction
signal is a regression waiting to happen.

## Scope and scale

- **Quick-fix path** (root contract, "Work cycle" boundary): a syntax error
  or a one-line fix whose cause is evident from the failure itself does not
  require phases 1–3 — fix directly; soft gate A of the closing gate still
  applies when a reproduction existed.
- **Emergency fix** (`collaboration-modes.md`): restore the broken path
  first with the minimal change; build the loop only when the cause is not
  evident. If the root cause remains unconfirmed after restoration, a full
  loop pass runs as follow-up work — restoration closes the outage, not the
  investigation.
- **Everything else with a non-obvious cause:** the full loop below.

## Phase 1 — Build a feedback loop

This phase **is** the method; everything after it is mechanical. The goal is
a single agent-runnable command that is *red* on this specific bug. Spend
disproportionate effort here.

Ways to build the loop, in order of preference:

1. A failing automated test.
2. An HTTP / CLI script against a fixed input.
3. A run whose output is diffed against a known-good snapshot.
4. A headless UI driver scenario.
5. A replay of a captured trace, log or job.
6. A throwaway harness around the single suspect routine.
7. A property / fuzz loop over generated inputs.
8. A bisection harness ("load state X, check, repeat") so the VCS can
   bisect automatically.
9. A differential run: old version vs new version, outputs diffed.
10. Last resort — a human-in-the-loop script: the script drives the user
    step by step and the captured output comes back to the agent.

Tighten the loop like a product: make it **faster** (cache setup, narrow the
scope), **sharper** (assert the specific symptom, not "does not crash") and
**more deterministic** (pin time, seed randomness, isolate the file system,
freeze network responses). For non-deterministic bugs the goal is a *higher
reproduction frequency*, not purity — a 50% flake is debuggable, a 1% flake
is not.

If a loop genuinely cannot be built: **stop and say so explicitly.** List
what was tried and ask the user for environment access, a captured artifact
(log dump, trace, recording, data snapshot) or permission for temporary
instrumentation. Do not slide into hypotheses without a loop.

**Phase gate.** The loop is done when the command is: red on the bug,
deterministic (or high-frequency), fast, runnable by the agent — and has
been executed at least once, with the invocation and its output recorded.
Reading code to build a theory before this command exists is the exact
failure this rule prevents.

## Phase 2 — Reproduce and minimise

- Confirm the loop shows the failure mode **the user reported** — wrong bug,
  wrong fix.
- Minimise one element at a time (inputs, configuration, data, steps),
  re-running the loop after each cut. Done when every remaining element is
  load-bearing: removing any of them turns the loop green.
- The minimal reproduction shrinks the hypothesis space in phase 3 and
  becomes the regression test in phase 5.

## Phase 3 — Hypothesise

- Produce **3–5 ranked, falsifiable hypotheses before testing any of them.**
  A single hypothesis is anchoring bias.
- Format each as: *"If \<X\> is the cause, then \<changing Y\> makes the bug
  disappear / \<changing Z\> makes it worse."* No prediction — not a
  hypothesis; drop it or sharpen it.
- Show the ranked list to the user before testing: domain knowledge re-ranks
  it cheaply ("we deployed a change to #3 yesterday"). If the user does not
  reply, proceed with your own ranking — do not block.

## Phase 4 — Instrument

- Every probe maps to a specific prediction from phase 3. Change **one
  variable at a time**.
- Instrument in order of preference: debugger / interactive evaluation at
  the suspect line → targeted log lines at the boundaries that *separate*
  hypotheses → never "log everything and search".
- Tag every temporary log line with one unique per-session marker, e.g.
  `[DEBUG-a4f2]` — cleanup becomes a single search. Untagged debug output
  survives into commits; tagged output dies.
- Performance regressions: logs are usually the wrong tool. Measure a
  baseline first (timing harness, profiler, execution plan), then bisect.
  Measure first, fix second.

## Phase 5 — Fix and regression test

- Write the regression test **before** the fix, at a correct seam — one
  where the test exercises the real bug pattern as it occurs at the call
  site. A seam that is too shallow (a unit probe on one caller when the bug
  needs several) gives false confidence.
- **If no correct seam exists, that is itself a finding**: the code
  structure prevents pinning the bug. Record it in Risks and hand it over —
  do not fake coverage.
- Then: turn the minimised reproduction into a failing test → watch it fail
  → apply the fix → watch it pass → re-run the phase-1 loop on the
  **original, unminimised** scenario.
- The fix touches only the code paths of the **confirmed** hypothesis. If it
  requires architectural rework — escalate per `delegation.md`
  instead of growing the bug fix.

## Phase 6 — Cleanup and post-mortem

Closing checklist:

- the original reproduction no longer triggers the symptom;
- the regression test is in place, or the seam absence is recorded;
- a search for the debug tag returns zero hits; throwaway harnesses are
  removed;
- the confirmed hypothesis is named in the commit / change description — so
  the next debugger learns from it.

Then ask once: **"what would have prevented this bug?"** — after the fix,
not before; you know more now. A structural answer goes to the refactoring /
architecture backlog (`/techdebt-capture` where installed), not into this
change.

## Companion rules

- `verification-matrix.md` — soft gate A re-runs the phase-1 loop as part of
  the closing gate.
- `test-discipline.md` — what a regression test worth keeping looks like.
- `delegation.md` — `error-fixer` runs this loop inside stage 3;
  escalation rules for architectural rework.
