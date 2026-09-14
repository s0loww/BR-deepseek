---
description: "Systematic 4-phase debugging methodology adapted for 1C (reproduce → hypothesize → experiment → fix): the 1C channels for each phase — debugger, event log, technological log, RLM navigation. Complements `debugging-loop`, which owns the loop itself; read both for a 1C bug. Триггеры: не воспроизводится, ищу причину бага, отладка, гипотеза не подтвердилась, где ломается."
alwaysApply: false
kind: process
---

# Systematic Debugging — 1C Adaptation

**When to load this file:** any task that involves diagnosing a bug, runtime error, regression, performance regression, or unexpected behavior — whether the parent agent is debugging directly or delegating to the `error-fixer` / `performance-optimizer` subagent.

**Goal:** replace ad-hoc trial-and-error with a structured root-cause loop. Skipping a phase is a defect, the same way as skipping the syntax check after editing code.

The methodology is adapted from the `systematic-debugging` skill of [obra/superpowers](https://github.com/obra/superpowers) and combined with 1C platform mechanics (debugger, `ЖурналРегистрации`, `ОтчетПоЖурналуРегистрации`, `ПоказатьЗначение`, `СообщитьПользователю`, `Replay` of background jobs, technological log).

> Code navigation below is RLM; the concrete helper per step is in `tooling-playbooks.md → Error Fixing`.

## Core principle

> **Reproduce first, hypothesize second, change code last.**

If you cannot reproduce the defect deterministically, you have no signal that any fix worked. Every "it should be fixed now" without a reproduction step is a regression waiting to happen.

## The four phases

You MUST complete all four phases in order. Do not jump to phase 4 ("write the fix") before phases 1–3 have produced verifiable artifacts.

### Phase 1 — Reproduce

Goal: a deterministic, minimal reproduction case in a controlled environment.

Prefer an **agent-runnable** reproduction (a query, a script, a re-posting
scenario the agent can trigger itself) over manual UI steps; when only a
manual reproduction exists, record the exact steps verbatim and minimize the
case — drop inputs and steps one at a time while the symptom survives —
before hypothesizing.

Required outputs of this phase:

- exact infobase (file or SQL — record the connection string), platform version, configuration / extension versions;
- exact user, role set, session parameters, locale;
- exact input data (document number / catalog reference / register record key) — copy or anonymize, do not paraphrase;
- exact reproduction steps (UI clicks, form, command, or API call);
- exact observed result (error message, stack trace, wrong value, slow timing);
- exact expected result.

Tools to use:

- **Live event-log reader** (a data/query MCP server, when one is exposed in the session) — pull the most recent error from `ЖурналРегистрации` of the live IB without leaving the agent: timestamp, event, affected metadata object, data presentation, full description. Run it immediately after the user's repro attempt to confirm an error landed in the log and on what object. Typical limitation: only the single most recent record with `УровеньЖурналаРегистрации.Ошибка` in the last 24 h. Wider filters / older records → fall back to the Configurator's `ОтчетПоЖурналуРегистрации` or to a custom `ВыгрузитьЖурналРегистрации` wrapper.
- **Configurator → Debug** (`Отладка → Подключиться`) to attach to the running session, capture the call stack, inspect locals.
- **`ЖурналРегистрации`** filter by date range / user / event / metadata to find the failing call. For high-volume errors prefer `ВыгрузитьЖурналРегистрации` to a `ТаблицаЗначений` for offline analysis.
- **Technological log** (`logcfg.xml`) for platform-level events (DBMS errors, deadlocks, lock conflicts, timeouts) when the application log is not enough.
- **`ОбработкаПроведения`** + the `Replay` mechanism for documents — re-post the failing document under the debugger.
- **Code navigation**: RLM — `find_module`, then `read_procedure` / `extract_procedures` — to locate the failing routine and inspect its surroundings.

If you cannot reproduce, **stop**. Ask the user for missing input data, screenshots, the exact step sequence, or a copy of the infobase. Do not guess.

### Phase 2 — Hypothesize

Goal: a small set of falsifiable hypotheses about the root cause, ranked by likelihood.

For each hypothesis state:

- **Statement** — exactly which code path / metadata / data state causes the symptom.
- **Falsifying experiment** — what would prove the hypothesis wrong (a log line that should appear but doesn't; a value that should be `Неопределено`; a query that should return an empty result; a lock that should not be acquired).
- **Cost of the experiment** — cheap (read-only query / `ПоказатьЗначение`) vs. expensive (rebuild infobase, reload data).

Tools to use:

- **Call-graph navigation** — RLM `find_callers_context`, `find_call_hierarchy` — to map all the call paths that reach the failing routine.
- **Reference / usage navigation** — RLM `find_references_to_object`, `find_code_usages`, `find_data_path` — to map which objects the failing routine depends on (registers it reads, common modules it calls, metadata it touches).
- **Exact text search** — RLM `safe_grep` / `git_search`, and `rg` over local `src/` — as a fallback when the call-graph answer looks incomplete or the index is stale.
- **Platform behaviour of a built-in function** — many bugs are platform-version-dependent (`ТекущаяДатаСеанса` vs `ТекущаяДата`, `НайтиПоНаименованию` collation, `ПолучитьСтруктуруХраненияБазыДанных` differences across versions). There is no documentation tool in this build: confirm in the syntax assistant or ITS, or turn the assumption into a falsifying experiment; an unconfirmed assumption is marked unverified.

Produce 3–5 ranked hypotheses (2 only when the space is genuinely binary).
A single hypothesis is anchoring bias — challenge it with a competing one
even if it feels obviously right.

### Phase 3 — Experiment

Goal: confirm or reject each hypothesis with concrete evidence, **without changing production code**.

Allowed experimental tools (read-only or scoped to a copy of the infobase):

- **debugger watches** (`Просмотр → Локальные`, `Выражение`) at the suspected line.
- **`ЗаписьЖурналаРегистрации("Debug.<Module>", УровеньЖурналаРегистрации.Информация, , , <Структура>)`** — temporary log lines, removed before the fix is committed.
- **`ПоказатьЗначение(Неопределено, <Объект>)`** for client-side diagnostics; **`СообщитьПользователю` / `Сообщение.Сообщить()`** for server-side.
- **read-only queries** in the configurator's `Console of queries` (`Консоль запросов`) against the failing data — never mutate.
- **Query validate → execute** on a data/query MCP server, when one is exposed — parse-check, then execute a falsifying query against the live IB without leaving the agent. Always read-only. Cheap evidence for a data-state hypothesis ("does this register really have a non-zero balance for this dimension set", "does this attribute really equal X for this reference").
- **Read-only BSL execution** on a data/query MCP server, when exposed — run a small **read-only** BSL fragment to verify a platform-version-specific or metadata-state hypothesis (type checks, `ЗначениеЗаполнено`, `Метаданные.НайтиПоПолномуИмени`, `ПолучитьФункциональнуюОпцию`). Default to read-only; **never** wrap `Записать()` / `Удалить()` / `НачалоТранзакции` / DML in a live-execution call without explicit user consent and a rollback plan — and only on a copy IB. Follow the data MCP server's own safety rules, when that server is exposed, for the full constraints.
- **`КопироватьИнформационнуюБазу`** or a SQL snapshot **before** any destructive experiment. The rule is: experiments either run on a copy or do not run at all.

Forbidden during experiments:

- Editing production code "to test a theory". Every code change must come from a confirmed hypothesis in phase 4.
- `Удалить()` / `Записать()` / `ЗаписатьИзменения()` / direct SQL DML against a live infobase.
- Disabling roles, profile or session parameter changes that affect other users.

After the experiment, write down the result:

> Hypothesis: `<...>` — **confirmed** by `<observed evidence>` / **rejected** by `<observed evidence>`.

If all hypotheses are rejected, return to phase 2 and produce new ones. Do not weaken the hypotheses to fit the data.

### Phase 4 — Fix

Goal: minimal code change that addresses the **confirmed** root cause, plus a regression guard.

Required:

- The fix touches only the code paths involved in the confirmed hypothesis (Surgical Changes principle from the root contract's Base rules, `AGENTS.md`).
- A regression guard exists: a query, a `ЖурналРегистрации` event, an `Утверждение`, or — at minimum — a documented manual reproduction step in the change description. When the project has an automated test suite, hold the core bar instead: a regression test written before the fix at a correct seam (`rules/test-discipline.md`).
- All temporary `ЗаписьЖурналаРегистрации("Debug.*"`, `ПоказатьЗначение`, hard-coded values, breakpoints, and TODO markers introduced in phase 3 are removed.
- Verification chain runs cleanly: static check (`tooling-playbooks.md → Channels`) → review → impact / call-graph analysis of the touched objects through RLM (see `verification-matrix.md`).
- The original reproduction case from phase 1 no longer triggers the symptom.

If the fix requires architectural rework (signature changes in shared common modules, metadata edits, a new register), escalate — call the `architect` or `developer` subagent rather than expanding the scope of the bug fix yourself.

## Anti-patterns

- **"Probably this `Если` should be `Иначе`"** without a reproduction or experiment — a guess.
- **Adding `Попытка / Исключение` to silence the error** without identifying the cause — hides the bug, does not fix it.
- **Re-posting / re-recording / `Записать(РежимЗаписиДокумента.Запись)`** as a fix instead of investigating why the data is wrong.
- **Restarting the user session** as a fix.
- **Reindexing / `Тестирование и исправление`** as a fix without documenting which specific structural inconsistency was repaired.
- **Disabling the failing test / removing the failing assertion** instead of fixing the code under test.
- **"Works on my machine"** when the user reports the bug — you do not have a reproduction yet, you have a hypothesis. Go back to phase 1.

## Process flow

```
Reproduce ──► Hypothesize ──► Experiment ──► Fix
   ▲              ▲                │            │
   │              │                ▼            │
   │              └── new hypotheses ◄── all hypotheses rejected
   │
   └── cannot reproduce ── ASK USER, do not proceed
```

## Companion rules

- `debugging-loop.md` (core) — the generic feedback-loop method. On
  1C-stack tasks **this adaptation takes precedence**; for non-stack code
  (PowerShell tooling, scripts) use the core loop. The shared core
  principle: reproduce first, hypothesize second, change code last.
- `verification-matrix.md` — the post-fix gate.
- `delegation.md` — when to delegate the bug to `error-fixer` vs. handle it directly.
- `tooling-playbooks.md → Error Fixing` — concrete MCP tool sequence for each phase.
- `anti-patterns.md` — to recognize anti-patterns that produce bugs in the first place.
