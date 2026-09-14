<!--
1C fragment of the root contract. Not installed as is: `python ci/assemble.py`
merges it into the base `templates/AGENTS.md` and writes
`overlays/1c/templates/AGENTS.md`, which is what a 1C project copies.
Each block below starts with a marker:
  after: ## Heading    — inserted after that section of the base template
  replace: ## Heading  — replaces that section
-->

<!-- after: ## Project -->
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

<!-- after: ## Rule Index (lazy loading) -->
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

<!-- after: ## Routing mini-table -->
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

<!-- replace: ## Subagents -->
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
