# Agent contract — {{PROJECT_NAME}}

> Root contract: "how to work". Project facts ("what we work with") are in
> the Project section below. Kun injects this file into every turn — keep it
> to the contract and the rule index; rule bodies stay in `rules/`.
> Reply language: {{LANGUAGE}}. The contract is written in English; that does
> not dictate the reply language.

## Project

- Stack: `{{STACK}}`
- Source of truth: `{{SOURCE_OF_TRUTH}}` — finally authoritative; indexes and
  search are navigation only, confirm facts against the source of truth.
- Source root: `{{PRIMARY_CODE_DIR}}`
- Test command: `{{TEST_COMMAND}}`

## 1C tooling

- Source layout: `{{ONEC_SOURCE_LAYOUT}}` — Designer XML dump (`Ext/…`
  modules) or v8unpack (`rules/v8unpack-source-structure.md`).
- Work target: `{{ONEC_TARGET}}` — the main configuration or an extension
  by name. For an extension every Designer load and database update carries
  `-Extension <name>`; without it the main configuration of the infobase is
  overwritten.
- RLM project: `{{RLM_PROJECT}}` — the name in the rlm-tools-bsl registry.
  1C source is navigated through RLM first; the protocol and the helper for
  each need are in `rules/tooling-playbooks.md` — read it before the first
  RLM call in a session.
- Test infobase and deploy: `tools/agent-1c` with its project profile
  (kept out of git); the order and the hard stops — skill
  `1c-deploy-and-test`.
- Static check: `{{STATIC_CHECK}}`.
- Code generation parameters (name prefix, modification comments):
  `.dev.env`.

Hard stops for 1C, on top of the base rules — ask first:

- anything against an infobase that is not the test one;
- `rlm_projects` add / remove / rename / update and `rlm_index` build /
  update / drop — they take the project password, which belongs to the user
  and never goes into a file, a command line or a report;
- printing or editing credentials from `.dev.env` and environment profiles.

## Base rules

- Verify references and current state before making claims about the repo.
- Changes are minimal, reversible, strictly on task. Do not rewrite others'
  changes and do not write outside the assigned scope.
- Do the task as asked, in the stated scope. Make routine calls yourself;
  ask only when different readings lead to materially different work. If the
  request looks wrong or a better approach exists — say so in one sentence
  and continue as asked. Do not narrow, widen or reshape the task silently.
- Stop before destructive, production, credential, paid-external and
  scope-expanding actions — do not run them without explicit approval.
- Report skipped, blocked, failing or unverified work plainly.
- Do not claim a check that was not performed.

## Work cycle

- **Quick-fix:** short plan → edit → local check → compact report.
- **Full-cycle:** clarify the goal → gather context → success criteria →
  minimal edit → verification → report.
- **Boundary:** a task is full-cycle when any of these holds — more than
  ~20 changed lines, more than one module, any data-structure/schema change,
  any architectural impact, any non-trivial bug. When in doubt, full-cycle
  wins.
- **Delegation is the exception, not the default.** Hand a subagent only
  large, genuinely independent work — a wide multi-file survey, a separate
  stream with its own write zone. Do not delegate what you would finish in a
  few tool calls. Do not use subagents to check your own work. Rules —
  `rules/delegation.md`.

## Rule Index (lazy loading)

Rule bodies live in `rules/` and are read **when they match the task**. Do
not preload them — not in bulk "for context", not as a list at session
start. The same goes for skills (read at invocation) and role definitions
(read only when delegating).

Genre says *when* a rule is needed: **invariant** — holds for every edit of
that kind, read it before writing the first line; **process** — how to run
the work itself.

| Rule | Genre | Load when |
| --- | --- | --- |
| `rules/collaboration-modes.md` | process | Choosing how deep to go: exploration, edit, review, emergency fix |
| `rules/context-packs.md` | process | Starting a recurring class of task and picking what to read |
| `rules/delegation.md` | process | Launching a subagent; passing work between subagents (Handoff) |
| `rules/verification-matrix.md` | process | Deciding which checks to run before declaring a change done |
| `rules/debugging-loop.md` | process | A bug: building a reproduction before hypothesising |
| `rules/session-handoff.md` | process | Handing work to a new session; context is filling up |
| `rules/test-discipline.md` | invariant | Writing or changing automated tests |
| `rules/script-contract.md` | invariant | Writing or changing an automation script |

Skills resolve to files: `.kun/skills/<skill-name>/SKILL.md` is the
dispatcher (`docs/` and `tools/` sit beside it). When a prompt or a role
definition names a skill, read it at that path; do not search for it with
shell commands.

## Rule Index — 1C

More genres: **recipe** — a technique for one concrete situation, read when
you are in it; **case** — symptom → proven fix, read when the symptom shows
up; **router** — read first, it names the companion rules to load.

| Rule | Genre | Load when |
| --- | --- | --- |
| `rules/access-rights-bsp.md` | recipe | Access-group profiles and rights from code: a profile lost its roles, extension roles missing, checking a right |
| `rules/anti-patterns.md` | invariant | Writing or reviewing queries and server-side code |
| `rules/async-methods.md` | invariant | Client-side asynchronous code: `Асинх` / `Ждать` / `Обещание` |
| `rules/clean-architecture-1c.md` | invariant | Deciding where code goes; dependencies between forms, common modules and integrations |
| `rules/com-powershell-1c.md` | recipe | Writing or running a COM script against an infobase from PowerShell |
| `rules/dcs-composition-recipes.md` | recipe | An existing DCS report eats memory, needs flat output, or must hide zero-total rows |
| `rules/dcs-design.md` | invariant | Deciding how a DCS report is built: data sets, computed fields vs resources, parameters |
| `rules/ddd-1c.md` | invariant | Modeling a domain area: bounded contexts, aggregates, carving a contour into an extension |
| `rules/dev-standards-architecture.md` | invariant | Placing code, platform standards, query rules, standard-library API stability, indexes |
| `rules/dev-standards-core.md` | invariant | Code style, naming, modification comments, editing a vendor configuration |
| `rules/dev-standards-forms.md` | invariant | Form-module structure templates; modifying a vendor form |
| `rules/extension-patterns.md` | invariant | Writing or reviewing extension (CFE) code: `&Перед` / `&После` / `&Вместо` |
| `rules/form-module.md` | invariant | Editing a form module: compilation directives, server round trips |
| `rules/form-reserved-names.md` | invariant | Server-side form-module code: local variable names vs form properties |
| `rules/forms.md` | router | Any managed-form task — read first, it picks the companions |
| `rules/forms-add.md` | recipe | Creating a form or adding elements, bindings, commands in `Form.xml` |
| `rules/forms-events-add.md` | recipe | Adding, renaming or removing a form event handler in the form XML |
| `rules/getconfigfiles.md` | recipe | The object to edit has no source in the working copy, or the sources look stale |
| `rules/integrations-add.md` | invariant | Integrating with another system: HTTP services, REST, queues, webhooks |
| `rules/kd2-exchange-rules.md` | invariant | Exchange rules of «Конвертация данных 2.x» (universal XML exchange) |
| `rules/kd31-exchange-rules.md` | invariant | Exchange rules of «Конвертация данных 3.1» (EnterpriseData) |
| `rules/locks-and-transactions.md` | invariant | Posting and multi-document operations, lock conflicts, deadlocks |
| `rules/logging-strategy.md` | invariant | What to write to the event log, severity levels, what never to log |
| `rules/metadata-xml-workarounds.md` | invariant | Authoring or fixing metadata XML / `Form.xml` by hand; handing over a built `.epf` |
| `rules/platform-solutions.md` | case | Strange platform behaviour: long operations, temporary storage, a hanging load, restructuring errors |
| `rules/refactor-add.md` | recipe | Planning or executing a 1C refactor |
| `rules/registers-design.md` | invariant | Creating or restructuring a register: dimensions, resources, balances vs turnovers |
| `rules/systematic-debugging.md` | process | A 1C bug: reproduce → hypothesise → experiment → fix (together with `debugging-loop.md`) |
| `rules/tooling-playbooks.md` | process | The first RLM call in a session; which tool and in what order for a task |
| `rules/unit-tests-1c.md` | recipe | Covering a routine with YaXUnit tests; unit test vs scenario |
| `rules/v8unpack-source-structure.md` | invariant | Editing sources unpacked by v8unpack (`*.obj.bsl`, `*.elem.json`) |

## Routing mini-table

A hint for "what to use for which task"; the rule is still loaded at the
moment it applies, never preloaded.

| Trigger (words) | Rule | Role |
| --- | --- | --- |
| script, automation, DryRun/Apply / скрипт, автоматизация | `script-contract` | developer |
| delegation, subagent, handoff / делегирование, субагент | `delegation` | (orchestrator) |
| check, review, verification / проверка, ревью | `verification-matrix` | code-reviewer |
| tests, regression, mocking / тесты, регрессия, моки | `test-discipline` | developer / tester |
| work mode, scouting vs edit, urgent fix / режим работы, разведка | `collaboration-modes` | (orchestrator) |
| debugging, bug, reproduction / отладка, баг, воспроизведение | `debugging-loop` | error-fixer |
| session handoff, context limit / передача сессии, лимит контекста | `session-handoff` | (orchestrator) |
| where is X, how does Y work / где находится, как работает | `context-packs` | explorer |
| guide, how-to, reference, docs / документация, инструкция, руководство | — | doc-writer |

## Routing — 1C

| Trigger (words) | Rule | Role |
| --- | --- | --- |
| where is X, who calls, where used / где находится, кто вызывает, где используется | `tooling-playbooks` | explorer |
| query, server code / запрос, серверный код | `anti-patterns` | developer |
| performance, technical journal, long calls / производительность, ТЖ, долгие вызовы | skill `1c-tj-analysis` + `tooling-playbooks` + `anti-patterns` | performance-optimizer |
| refactoring, duplicates, dead code / рефакторинг, дубли, мёртвый код | `refactor-add` | refactoring |
| layers, dependencies, bounded contexts, DDD / слои, зависимости, границы контекстов | `clean-architecture-1c` + `ddd-1c` | architect |
| debugging, bug / отладка, баг | `systematic-debugging` + `debugging-loop` | error-fixer |
| forms, metadata, DCS, layouts / формы, метаданные, СКД, макеты | `forms` + skill `1c-metadata-manage` | metadata-manager |
| extension, interceptor / расширение, перехват | `extension-patterns` | developer |
| locks, transactions / блокировки, транзакции | `locks-and-transactions` | developer |
| unpacked sources, `*.obj.bsl` / распакованные исходники | `v8unpack-source-structure` | developer |
| exchange rules, data conversion / правила обмена, конвертация данных | `kd2-exchange-rules` or `kd31-exchange-rules` | developer |
| deploy, test infobase / деплой, тестовая база | skill `1c-deploy-and-test` | tester |
| requirements, specification / требования, ТЗ, спецификация | — | analytic |

## Subagents

Roles live in `.kun/agents/<role>.md`. In a 1C project the seven base roles
are their 1C versions (same ids) and six more are added. Kun runs a subagent
on the **session model** unless a per-agent override is set in Settings →
Agents — the model column below is a configuration recommendation, not a
file-enforced fact.

Kun's `readOnly` tool policy strips MCP and skills, so a 1C role that must
not edit is `inherit` with the write tools blocked — it keeps RLM.

| Role | Model | Effort | Blocked tools |
| --- | --- | --- | --- |
| explorer | flash | high | edit, write, bash |
| planner | pro | max | — |
| developer | pro | high | — |
| error-fixer | flash | high | — |
| tester | flash | high | — |
| code-reviewer | pro | high | edit, write, bash |
| doc-writer | pro | high | — |
| analytic | pro | high | — |
| architect | pro | max | — |
| arch-reviewer | pro | high | edit, write, bash |
| refactoring | pro | high | — |
| metadata-manager | pro | high | — |
| performance-optimizer | pro | max | edit, write |

- Delegate bounded independent work (scouting, a separate edit, review);
  decomposition, final decisions and result integration stay with the
  orchestrator.
- Do not trust scouting subagents' reports blindly — spot-check key facts
  against the source of truth.

## Output

Result first. List changed files and checks performed. Give a compact
conclusion, evidence, next step — not raw internal reasoning.

## Output discipline

Effort controls how much the agent deliberates, not how much it writes —
length is set here, not by the effort step.

- Keep answers focused and short. Caveats stay brief; the bulk goes to the
  answer itself. Asked to explain — give the top-level view unless a
  detailed walkthrough was requested.
- Before the first tool call, say in one sentence what you are about to do.
  While working, post a short update only on a real finding or a change of
  direction. On completion lead with the result.
- Match the size of a written document to the task: no filler, no duplicate
  summaries, no boilerplate.
- Correct an earlier statement only when the error changes code, conclusions
  or the user's decisions.

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
