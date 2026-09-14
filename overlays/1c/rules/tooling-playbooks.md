---
description: "Which tool answers which question in a 1C project and in what order: the RLM (rlm-tools-bsl) session protocol, the helper for each need, what to do when the index is stale or silent, and the channels RLM does not cover (platform docs, syntax check, standard-library lookup). Per-task playbooks: writing code, review, refactoring, error fixing, performance (evidence first: a technical-journal log goes to the skill 1c-tj-analysis), forms, metadata XML, integrations, documentation. Триггеры: каким инструментом искать, с чего начать задачу, порядок вызовов MCP, RLM, поиск по коду проекта, кто вызывает, где используется."
alwaysApply: false
kind: process
---

# Tool usage in a 1C project — RLM first

Code and metadata navigation in this build goes through one MCP server —
**rlm-tools-bsl (RLM)**. The RLM project name for this repository is in the
`1C tooling` section of `AGENTS.md`. RLM keeps a SQLite index of the
configuration and returns only what your code prints, so a search costs a
few hundred tokens instead of a file read.

## Channels

| Need | Channel |
| --- | --- |
| Code, routines, call graph, metadata structure, forms, extensions, references | RLM: `rlm_start` → `rlm_execute` |
| Standard library (БСП) | RLM over the configuration itself — БСП is part of the dump: `search_methods`, `find_exports` on its common modules |
| Existing implementation to copy from | RLM: the nearest implementation in the configuration (`search`, `search_methods`, `read_procedure`) |
| Metadata XML mutation (objects, forms, DCS, roles, extensions) | skill `1c-metadata-manage` |
| Syntax / static check | `tools/agent-1c` analyze (BSL Language Server), if configured; otherwise a load check on the test infobase — skill `1c-deploy-and-test` |
| Platform documentation, ITS standards | **no tool.** A claim about platform behaviour or a built-in method without a source is marked *unverified* in the report |
| Non-indexed files (`.md`, `.json`, `.yaml`, logs, build output) | `grep` / `find` directly |

## RLM session protocol

1. **Open** with `rlm_start(query=…, project=…)`, the project name from
   `AGENTS.md`. Name unknown — `rlm_projects(action="list")`.
2. **Read the start response** before searching: `warnings`,
   `extension_context`, `detected_custom_prefixes`.
3. **Recipe first.** For anything beyond a single lookup call
   `rlm_help(topic=…)` before the first `rlm_execute` — the start response
   is condensed on purpose. Topics include «проведение», «печать», «права»,
   «обмен», «формы», «ссылки», «ввод на основании», «структура объекта»,
   «иерархия вызовов», «расширения», «путь данных»; `rlm_help()` lists all.
4. **Batch.** One `rlm_execute` does find → read the top hits → print a
   summary. One helper per call wastes rounds. Print only what the task
   needs; variables persist between calls.
5. **Never grep broad paths.** On a large configuration a grep over `.`
   times out. `find_module` first, then `safe_grep(pattern, name_hint)` or
   a read of the specific file.
6. **Effort.** `effort="low"` for one lookup, `medium` by default, `high`
   for a multi-aspect trace.
7. **Close** with `rlm_end(session_id)` when the task is done; reuse the
   session within the task.

### Index freshness

RLM has no scheduler: the index is as fresh as its last manual update.
A negative answer ("no callers", "not used", "no such routine") on code
that changed recently may come from a stale index.

- `rlm_index(action="info")` shows the index state; compare it with the
  date of the change you rely on.
- `build` / `update` / `drop` and every `rlm_projects` mutation require the
  project password. **Do not run them yourself and never write a password
  into a file, a command line or a report.** Tell the user the index is
  stale; the update is their call.
- Until then, confirm by a second route on the specific file: `git_search`
  (sources under git) or `grep` on the file RLM named.

### Negative results are claims

Before deleting, renaming or changing a signature on the strength of "no
usages", confirm with two routes: `find_code_usages` or
`find_callers_context` **and** `safe_grep` / `git_search` on the name.

### Data

Everything RLM prints enters the model context and goes to the model
provider, exactly like a file read. RLM's `llm_query` helpers call the LLM
provider configured on the RLM server, which is a second outbound channel —
do not use them unless the user confirmed the server has a provider and
allowed it.

## MCP-first search — quick first-pick

All helpers below run inside `rlm_execute`.

| Need | First call | If empty — next |
| --- | --- | --- |
| Object by business name (Russian synonym) | `search_objects('…')` | `search('…')` |
| Anything, first broad pass | `search('…')` | the precise helper for the hit type |
| Module file of an object | `find_module(name, module_type, category)` | `find_by_type(category, name)` |
| Routine by name | `search_methods('…')` | `safe_grep(pattern, name_hint)` |
| Routine body | `read_procedure(path, name)` | `None` → `extract_procedures(path)` for the exact name |
| Module structure / exported API | `extract_procedures(path)` / `find_exports(path)` | — |
| Object passport: attributes, tabular sections, forms, predefined | `get_object_full_structure(name)` | `parse_object_xml(path)` (live XML, not the index) |
| Attribute type / defined type / enum values | `find_attributes` / `find_defined_types` / `find_enum_values` | `parse_object_xml` |
| Who calls a routine | `find_callers_context(proc, module_hint)` | `find_call_hierarchy(name, depth=2)` for transitive callers |
| Does A reach B | `find_path(from, to)` | — |
| References in metadata ("Найти ссылки → В свойствах") | `find_references_to_object('Справочник.X')` | `include_code=True` |
| Usages in code | `find_code_usages('Справочник.X')` | `safe_grep` on the name |
| How two objects are linked through data | `find_data_path(from, to)` | — |
| Posting, register movements | `analyze_document_flow(doc)` / `find_register_movements(doc)` | `find_register_writers(reg)` |
| What fires on write / post; scheduled jobs | `find_event_subscriptions(obj)` / `find_scheduled_jobs()` | — |
| Rights and functional options | `find_roles(obj)` / `find_functional_options(obj)` | — |
| Form handlers, commands, attributes | `parse_form(object, form)` | — |
| Extension interceptors | `get_overrides(object, method)` | `read_procedure(…, include_overrides=True)` |
| Non-standard code by prefix | `find_custom_modifications(obj)` | — |
| HTTP / web services, XDTO, exchange plans | `find_http_services` / `find_web_services` / `find_xdto_packages` / `find_exchange_plan_content` | — |
| Raw text in XML, queries, forms | `git_search(pattern)` (sources under git) | `grep` on the specific file |

**Response gate.** When a result relied on `grep` / `find` over 1C source,
add one short line naming the RLM attempts that fell short, e.g. *"Tried
`search_methods` and `safe_grep` with a name hint, both empty; fell back to
`grep` for the literal `<…>`."* `grep` / `find` are a legitimate first pick
only for non-indexed targets or a file already read this session.

## Writing New Code

0. **No source for the object in the working copy?** Export it from the
   infobase first — `getconfigfiles.md`. Editing against a stale or absent
   source is how a change silently lands on top of someone else's.
1. `get_object_full_structure` — the target object: attributes and types,
   tabular sections, forms.
2. `search` / `search_methods` — an existing implementation of the same
   thing, including БСП; reuse before writing.
3. `extract_procedures` on the module you will edit — its structure and
   regions.
4. `find_attributes` / `find_defined_types` — every attribute the new code
   touches, before writing a query.
5. Write the code by `dev-standards-core.md` and `dev-standards-architecture.md`.
6. Static check (see Channels), then the gates of `verification-matrix.md`.

## Code Review

1. `read_procedure` on every changed routine — review the code, not the
   diff alone.
2. `find_callers_context` / `find_call_hierarchy` — who is affected by a
   changed signature or behaviour.
3. `find_code_usages` / `find_references_to_object` — correct use of the
   objects the change touches.
4. `get_object_full_structure` — names and types used by the change exist.
5. Cross-check against `anti-patterns.md`; static check if configured.

## Architecture Design

1. `analyze_subsystem` — composition of the affected area, custom vs
   standard objects.
2. `get_object_full_structure` on the key objects.
3. `find_references_to_object` + `find_data_path` — how the objects are
   linked through metadata.
4. `find_call_hierarchy` — code coupling around the entry points.
5. `analyze_document_flow` for documents — subscriptions, movements,
   scheduled jobs.
6. `search` — existing architectural patterns in the configuration;
   layering by `clean-architecture-1c.md`.

## Error Fixing

Follow the four-phase loop in `systematic-debugging.md`; this is the tool
sequence per phase.

1. **Locate:** the error text names a module and a line → `find_module`,
   then `read_procedure` around the line.
2. **Context:** `extract_procedures` — the surrounding module;
   `get_object_full_structure` — the attributes involved.
3. **Propagation:** `find_callers_context` — how the failing routine is
   reached; `find_event_subscriptions` if it fires on write or post.
4. **Extensions:** `get_overrides` — whether an interceptor changes the
   behaviour you are looking at.
5. **Verify** with a static check and a reproduction, not by reading.

## Performance Optimization

1. **Evidence first.** A slow operation is located by measurement — the
   technical journal (ТЖ), a performance measurement or a timed
   reproduction — not by reading code. A ТЖ is analysed with the skill
   `1c-tj-analysis`: its script aggregates the log locally, starting with
   what the log recorded at all, and never pulls raw log text into the
   context — the ТЖ holds SQL texts with parameters and user names. A ТЖ
   event's `Context` names the module and line of the call: map it with
   `find_module` + `read_procedure`.
2. `read_procedure` on the hot routine; check it against
   `anti-patterns.md` (query in a loop, dot dereference, subquery joins).
3. `find_call_hierarchy` — how often and from where the hot path is reached.
4. `get_object_full_structure` / `parse_object_xml` — indexes and register
   structure behind the query (`registers-design.md`).
5. Lock contention → `locks-and-transactions.md`.

## Refactoring

1. `get_object_full_structure` — the object being refactored.
2. `find_callers_context` with `find_call_hierarchy` — every caller before
   a signature or export change.
3. `find_code_usages` + `find_references_to_object` — every reference
   before renaming or removing; confirm negatives by a second route.
4. `find_custom_modifications` — non-standard code that may depend on it.
5. After the change: the same searches again — no old references remain;
   static check. Flow — `refactor-add.md`.

## Generating / Modifying Metadata XML

1. Use the `1c-metadata-manage` skill or the `metadata-manager` subagent
   for XML mutations whenever feasible.
2. `find_by_type` / `parse_object_xml` — a similar existing object as the
   example.
3. Write / modify XML from the example; generate unique UUIDs and update
   `Configuration.xml` / child ordering when required.
4. Validate with the skill's validation scripts (compile / load smoke) and
   report which validation ran.
5. See `metadata-xml-workarounds.md` for the recurring XML traps.

## Form Analysis and Generation

1. `parse_form(object)` — handlers, commands and attributes of existing
   forms of the object; a similar form elsewhere by `search`.
2. `get_object_full_structure` — the metadata the form binds to.
3. Generate or edit `Form.xml` from the example with the
   `1c-metadata-manage` skill (form-manage section); it compiles and
   validates.

Domain rules: `forms.md` (router) → `forms-add.md`, `forms-events-add.md`,
`form-module.md`, `form-reserved-names.md`.

## Integrations

Use this playbook when writing HTTP services / clients, REST integrations,
file or message-queue exchanges, webhooks. Domain rules —
`integrations-add.md`.

1. `rlm_help(topic="интеграция")` — the recipe for the configuration's
   exchange mechanics.
2. `find_http_services` / `find_web_services` / `find_xdto_packages` /
   `find_exchange_plan_content` — what already exists.
3. `search('HTTPСоединение')`, `search_methods` — existing integration
   code and the БСП subsystems it uses («Получение файлов из Интернета»,
   «Обмен данными»); reuse before writing.
4. `extract_procedures` on the integration common module you will extend.
5. After implementation: static check, then `verification-matrix.md`.

## Documentation

1. `analyze_object` / `get_object_full_structure` — what the object is
   made of.
2. `extract_procedures` / `find_exports` — the module's API.
3. `analyze_document_flow` — for documents: movements, subscriptions, print
   forms.
4. Anything about platform behaviour without a source — marked unverified.
