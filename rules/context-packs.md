---
description: "Context packs: per task type a pack is loaded = rule + skill + tool category + source of truth. Load when starting a recurring class of task and picking what to read up front. Триггеры: контекст-пак, класс задач, источник истины, что читать"
alwaysApply: false
kind: process
---

# Context packs

A context pack is a small starting map for a recurring class of tasks. It
avoids re-discovering the same things over and over and keeps the heavy
model's context focused.

A pack is an expanded row of the routing mini-table from the root contract
(root `AGENTS.md`): where the mini-table gives a "trigger → rule →
role" pair, the pack expands it into the full loading set. Rules are still
loaded lazily via the Rule Index at the moment of application — the pack
only names what to plug in, it does not preload.

Each pack names:

- the goal and when to apply it;
- rules/skills to read (via the Rule Index);
- a project-profile tool category for navigation;
- source-of-truth files/directories;
- the usual verification (per `verification-matrix.md`);
- known traps and forbidden sources.

## Generic packs

### Code change

Read: the project's development standards rules + `verification-matrix`.

Use: the project's local source of truth; profile code search / RAG — for
navigation only; templates/documentation — as needed.

Verify: syntax; static logic analysis and style review — by risk
(see `verification-matrix.md`).

## Domain packs

The generic layer contains no domain or project packs — they are added by a
stack overlay or the project layer. Such a pack lives in the target
repository's rules/commands/prompts and overrides the generic map above: it
names the domain rule, the project's concrete source of truth, the profile
navigation tools, and the specific traps. The format is the same — an
expanded routing mini-table row, extended with the domain rows that the
overlay writes in place of the domain-routing placeholders.
