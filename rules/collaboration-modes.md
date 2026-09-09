---
description: "Collaboration modes: exploration, edit, review, emergency fix. Load when choosing how deep to go on a task and which mode of work fits it. Триггеры: режим работы, разведка, правка, ревью, экстренный фикс"
alwaysApply: false
kind: process
---

# Collaboration modes

An explicit mode is chosen when the task can be solved cheaper or safer by
changing depth, tooling, or delegation. Modes are aligned with the
`quick-fix` / `full-cycle` triage from the root contract: exploration and
edit are the main full-cycle states, emergency fix is an accelerated
quick-fix.

The mode says *how deep to go*; what to load once you know is
`context-packs.md` — per task type, the pack of rule + skill + tool category
+ source of truth, so the loading decision is made once rather than re-derived
per task.

## Modes

### Exploration

Goal: understand the scope without making edits.

When: unclear requirements, impact analysis, codebase navigation, risk
discovery.

Output: a short map of objects/files, relevant rules and project-profile
tools, risks, recommended next step.

Subagents: the `explorer` role fits (read-only, tier low) — see
`delegation.md`.

### Edit

Goal: a minimal change that is safe for the production system.

When: bounded implementation after enough context has been gathered.

Output: changed files, checks performed, residual risk.

Subagents: a writing role (`developer`, pro tier) —
only with a non-overlapping write scope and an expected edit that is clear
in advance.

### Review

Goal: find real bugs, regressions, missed checks, and risky assumptions.

When: the user asks for a review. A risky implementation on its own does not
open this mode — the closing gate of `verification-matrix.md` covers it.

Output: findings first, ordered by severity with `file:line` references;
summary after the findings.

Subagents: an independent reviewer (`code-reviewer`, pro tier) — on the
user's request, for high-risk or wide changes.

### Emergency fix

Goal: restore a broken path with a minimal blast radius.

When: syntax / runtime errors, failing checks, urgent regressions.

Output: root cause, minimal fix, verification.

Subagents: avoid, except for a read-only side check that can run in
parallel.

Urgency overrides the non-trivial-bug escalation of the pipeline triage:
restore first with the minimal fix, then route the root-cause work through
normal triage (`debugging-loop.md`, "Scope and scale"). If the minimal fix
itself touches a stage-1 risk escalator (`delegation.md`), the
follow-up full-cycle pass is mandatory, not optional.

## Choosing a mode

- If the user only asks a question — start in `Exploration`.
- If they ask to implement or fix — start in `Edit` after minimal
  context.
- If they ask for a review — `Review`.
- If checks are failing or a production path is blocked — `Emergency fix`.
