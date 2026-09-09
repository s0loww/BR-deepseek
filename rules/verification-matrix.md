---
description: "Verification matrix by change type and the closing full-cycle gate, including coverage reconciliation when many inputs must be covered by a set of rules, and the operational-memory bracket around the gates. Load when deciding which checks to run before declaring a change done. Триггеры: проверка, верификация, гейт сдачи, что проверить, сверка покрытия, все ли входы покрыты, что уже известно, записать находку в память."
alwaysApply: false
kind: process
---

# Verification matrix

Use the smallest set of checks that matches the real risk. If a check cannot
be performed — say why and name the residual risk. Concrete tool names come from the
root contract; below they are described as categories.

| Change type | Minimal checks | Add as risk grows |
| --- | --- | --- |
| Docs/rules/playbook only | loader/routing smoke if routing changed | — |
| Quick-fix in code | syntax check of the changed module | static logic analysis if logic changed |
| Code logic | syntax check + static analysis + affected automated tests (when a suite exists) | deeper review for shared modules, queries, transactions |
| Query / data access | local impact search + syntax + static analysis | review of query parameters, derived-view filters, callers |
| Metadata (XML) | schema/tool validation when available | load/open the object on a test environment when feasible |
| Form (XML/module) | markup/event inspection + form validation when available | UI smoke / opening the form |
| Integration / XML / JSON | check against schema/sample/reference payload | retry/error/security review; coverage reconciliation (gate E) when many input shapes map onto handling rules |
| Refactoring | caller/usage impact + syntax/analysis | wider impact search across dependents |
| Rules / routing changes | list and read the affected rules, check the Rule Index still resolves | re-run the routing check across every role that loads them |

## Escalation

- Shared module, transaction, data store, or query: add impact analysis.
- Metadata/forms: use metadata tools and validators when available.
- User scenario: add manual / UI smoke if tooling allows.
- Many varied inputs onto one set of handling rules: add gate E below.
- High-risk change: the closing gate below **is** the bar — tighten it
  (impact analysis, a deeper validator pass) rather than adding a reviewer.
  An independent `code-reviewer` runs on an explicit user request only
  (`delegation.md`, stage 4b).

## Closing gate — full-cycle change

The matrix above picks the right *set* of checks by change type. This section
adds the *order and stop criteria* for any non-trivial change before declaring
it "done". Hard gates run in order; each has an explicit pass/fail criterion
and a bounded retry budget.

### Hard gates

1. **Syntax** — every affected module through the project's syntax check
   tool. Pass: zero `error`-level items. Retry budget: 1 call by default, up
   to 3 only if the previous run returned a substantive defect. Style-only
   linter noise does not justify a retry.
2. **Logic and performance** — static analysis of every affected module,
   always *after* gate 1 passes. Pass: no `critical` / `error` items.
   In-scope `warning`s (introduced by your change) — fix; pre-existing ones
   outside the scope — leave (surgical edits). If results are
   non-deterministic on identical code — take the strictest set and stop, do
   not loop.
3. **Style and standards** — style/review analysis of every affected module
   after gate 2. Pass: no `error` items. Intentional warnings — suppress with
   a targeted linter marker and a one-line reason; blanket suppressions are
   forbidden.
4. **Impact analysis (only if the public surface changed)** — may be skipped
   only for fully internal changes (a private routine of a non-exported
   module; a form-module routine without export; a comment / linter-marker
   edit). Otherwise list callers and dependents. Use whatever call-graph and
   cross-search tooling the project has; then verify against the local
   source of truth. If no call graph is available, record in "Risks":
   *"Impact analysis degraded — call graph unavailable; dependents listed by
   source-of-truth search, not a recursive graph"*. For metadata changes
   include forms/modules/queries that touch the object. Silently breaking a
   dependent is a defect; skipping the gate without recording it is a defect.
5. **Metadata (XML) (only if XML was edited)** — validate every changed file
   with the metadata tools / project validation scripts (form validation,
   compile/load smoke where available). If a separate XSD schema validator is
   available in the session — run it too; otherwise state the fallback
   validation used. For a form file additionally confirm the form opens in
   the platform's native designer without warnings, when feasible.

### Soft gates — as applicable

- **A. Reproduction case (debugging tasks)** — re-run the phase-1 feedback
  loop from `debugging-loop.md` on the original, unminimised scenario after
  the fix; the symptom is gone. Document it in the summary. Remove all
  temporary debug log writes, value dumps, breakpoints, hardcoded test
  values (search by the debug tag — `debugging-loop.md`, phase 4).
- **B. Plan conformance (any written or chat-approved plan)** — every step
  done, none silently skipped; diff reconciled per file
  (`git diff --name-only`); no file outside the plan edited without
  justification; the plan's own checklist matches reality.
- **C. Explicit user code review (only when the user asks)** — call the
  `code-reviewer` role; close critical/major before handover. Do **not**
  trigger the reviewer automatically — gates 2-3 already cover the routine
  bar. Findings come back with **severity and confidence as separate axes**
  and nothing dropped for uncertainty — the reviewer roles own that reporting
  contract; do not restate or narrow it here.
- **D. Automated tests (only when the project has a test suite)** — the
  tests affected by the change pass. A bug fix additionally carries a
  regression test at a correct seam, built from the minimised reproduction —
  or the absence of a correct seam is recorded in "Risks"
  (`debugging-loop.md`, phase 5). New tests follow `test-discipline.md`: no
  tautological or implementation-coupled tests, seams pre-agreed in the
  plan. Do not introduce a test suite into a project that has none as a side
  effect of a change.
- **E. Coverage reconciliation (a set of inputs must be fully covered by a set
  of rules)** — applies when the change maps many varied inputs onto branches,
  profiles or mapping rules: file shapes onto parsers, source fields onto
  target fields, message types onto handlers, incoming documents onto
  processing rules. Run it as a **separate pass after the code is written**,
  never inside the same pass that writes it — an author checking their own
  mapping reproduces the same blind spot that produced it.
  1. Fix the registry of inputs explicitly — the full list, never a sample.
  2. For each input, name the rule / branch / profile that handles it.
  3. Build the input → rule table; mark **uncovered** inputs and **conflicts**
     (one input matching more than one rule).
  4. Fix the code or the rules, then repeat from step 2.

  Pass: an explicit count — `N/N covered, 0 conflicts`. "Seems to work" is not
  a pass, and neither is a spot check of a few inputs. Classify each input by
  its **actual content**, not by its name or label — names lie, and a wrong
  classification hides an uncovered input behind a plausible one. The first
  round almost always finds discrepancies; they converge over a few rounds.
  This gate prepares acceptance, it does not replace it — final acceptance on
  real data stays with the user.

- **F. Operational memory (only when the project wires a memory server)** —
  verification is worthless if it re-derives what a previous session already
  established, and worse if it re-walks a dead end already documented. This
  gate brackets the others.

  *Before the first gate*, on any recurring class of task, query the memory
  server for what is already known about it: prior findings, dead ends,
  decisions that constrain the change, checks previously found useless here.
  What comes back is prior observation, not proof — it can be stale. Treat it
  as a lead to confirm against the source of truth, never as a substitute for
  a gate. A documented dead end is the one exception: it is a reason not to
  repeat an attempt, and repeating it anyway needs a stated reason.

  *After the gates pass*, write back only what this session **established**
  and what is **not derivable** from the code or git history: a fact, why it
  is true, and how to apply it next time. A degraded gate (4) and its residual
  risk belong here too — that is exactly the knowledge the next session cannot
  reconstruct. Do not write the diff, the changed-file list, or a narrative of
  the session: the repository already carries those, and duplicating them
  turns the memory into a second, staler log.

  Respect the layer boundary (`AGENTS.md`): rules, agreements, topology and
  paths stay in markdown under git; sessions, incidents and findings go to the
  memory server. A rule written into the memory server is invisible to review
  and to diff.

  No memory server in the project — the gate does not apply, and its absence
  is not a defect.

### Handover summary — what the user sees

After the gates pass the report contains: (1) **What was done** — 1-3 lines,
no preamble; (2) **Changed files** — each path in backticks, one line;
(3) **Context sources** — for non-trivial code/metadata changes the sources
actually used (templates, project code, metadata, platform/standards docs);
(4) **Risks** — real ones only, including the gate-4 degradation record
verbatim; (5) **Leftovers** — noticed but unfixed defects. Omit empty
sections. Do not restate the request, do not list invoked tools, do not add
empty "structural" sections.
