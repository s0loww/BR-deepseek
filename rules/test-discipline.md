---
description: "What makes an automated test worth keeping: pre-agreed seams, vertical red-green slices, mocking only at system boundaries, anti-patterns with their tells. Load when writing or reviewing tests, adding a regression test, or deciding where to test. Триггеры: тесты, тестирование, регрессионный тест, TDD, моки."
alwaysApply: false
kind: invariant
---

# Test discipline

Adapted from the `tdd` skill of
[mattpocock/skills](https://github.com/mattpocock/skills) (MIT). Applies when
the project has — or is adding — an automated test suite; the concrete runner
comes from the root contract, Project section. Where no suite exists, the
`verification-matrix.md` gates remain the only bar and this rule is not a
reason to introduce one uninvited.

## What a good test is

A test verifies **behavior through a public interface**. The implementation
may change wholesale; the test should not. A good test reads like a
specification of what the code promises, not like a mirror of how it is
written today.

## Seams — where tests go

A **seam** is an interface where behavior can be exercised without editing
the code at that place. Tests live at seams; choosing them is a design
decision, not a by-product of writing tests.

- **Test only at pre-agreed seams.** In the full-cycle pipeline the seams
  are named in the stage-2 plan and approved together with it. Standalone —
  confirm before the first test: *"what is the public interface, and which
  seams do we test?"*
- Prefer existing seams over new ones; prefer the highest seam that still
  gives a deterministic signal; the fewer seams, the better.
- Rationale: everything cannot be tested. Pre-agreeing seams lands the
  effort on critical paths and hard logic instead of scattering it over
  every edge case.
- Wanting to test *behind* the interface is a signal the module has the
  wrong shape — raise it, do not tunnel through.

## The loop

- **Red before green.** Watch the test fail before making it pass; a test
  that never failed proves nothing.
- **Vertical slices.** One test → one piece of implementation → repeat. Each
  next test reacts to what the previous cycle taught.
- Refactoring is a separate pass after green, inside the plan's scope — not
  a step of the red-green loop and not an excuse to rewrite neighbors while
  the suite is passing.

## Anti-patterns — each with its tell

1. **Implementation-coupled test** — mocks internal collaborators, tests
   private routines, or verifies through a side channel (reads the data
   store directly instead of calling the interface). *Tell: the test breaks
   on a refactor that did not change behavior.*
2. **Tautological test** — the expected value is computed the same way the
   code computes it, so the test passes by construction and can never
   diverge from the code. *Expected values come from an independent source
   of truth: a known-good literal, a worked example, the spec.*
3. **Horizontal slicing** — writing the full test list first, then the whole
   implementation. The tests verify *imagined* behavior and freeze the test
   structure before the implementation is understood.

## Mocking

- Mock **only at system boundaries**: external services, clock and
  randomness, and stores for which the project has no test instance.
- Do not mock your own modules or internal collaborators — that couples the
  test to the implementation (anti-pattern 1).
- If a mock needs conditional logic inside, the interface is wrong: prefer
  one specific operation per entry point over a generic call-anything
  surface.

## Regression tests for bug fixes

The source of a regression test is the **minimised reproduction** from
`debugging-loop.md` (phase 5). The correct-seam requirement — and the rule
that the *absence* of a correct seam is itself a finding to record, not to
paper over — lives there.

## Companion rules

- `verification-matrix.md` — soft gate D runs the affected tests as part of
  the closing gate.
- `debugging-loop.md` — where the reproduction that seeds a regression test
  comes from.
- `delegation.md` — the stage-2 plan is where seams get named and
  approved.
