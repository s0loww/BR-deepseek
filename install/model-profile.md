# Model profile — DeepSeek V4 in Kun

Companion to `model-map.yaml`. The map says *which* model a role gets; this
file says *how to talk to it*.

**Do not port a profile from another model family.** Guidance that fixes one
family's failure mode amplifies the opposite failure mode on another — a
delegation damper is the standing example: correct for a family that fans
out on reflex, actively harmful for one that serializes work it should have
split. The blocks below are therefore short and evidence-backed; everything
we have not measured sits in "Open questions" instead of being asserted.

## Where it goes

Kun has no per-agent profile rendering. The block below is appended to the
root `AGENTS.md` of the target project, which Kun injects into every turn
(Settings → "AGENTS.md instructions"). Keep it short for exactly that
reason: it is paid for on every turn, not once per session.

## Profile block

```
## Model profile: DeepSeek V4 (Kun)
- Use tools to inspect referenced files and current state before making
  claims about the codebase. Do not speculate about unopened code.
- Before progress or final claims, audit each claim against tool output from
  this session. State skipped, blocked, failing or unverified work plainly.
- Keep changes minimal and on task: no speculative features, no broad
  refactors, no test-only hacks. Clean up temporary files.
- The working context window is ~190k tokens, not the advertised 1M: Kun
  compacts at 192k (soft) / 217.6k (hard). Do not load files "for context";
  read what the task needs. Long reconnaissance goes to a subagent so its
  output does not land in this window.
- Effort is a setting, not an exhortation: `max` is for planning, hard bugs
  and release-gate review; `high` is the working default. Asking for "more
  thinking" in prose is not a substitute for the right step.
- Report rationale and evidence, not raw internal reasoning.
```

## Open questions — measure before writing more

These are the things a profile normally answers, and we do not have data for
this family in this harness yet. Each one is a measurement, not a guess:

1. **Delegation reflex.** Does it fan out subagents unprompted, or does it
   serialize work that should be split? The damper (or the push) goes in
   only after this is observed.
2. **Self-verification.** The upstream distribution *removed* "double-check
   your work" instructions because that family already re-checks and the
   instruction only burned tokens. Unverified here — if DeepSeek does not
   self-check, an explicit verification instruction earns its place back.
3. **Long-contract adherence.** Whether it holds a multi-stage contract
   (Handoff format, gate discipline) across a long session, or drifts after
   compaction.
4. **Instruction-vs-example weighting.** Whether it follows the prose rule or
   copies the example when the two diverge.
5. **Language.** Whether an English rule body with Russian trigger words
   routes as well as a fully Russian one.
