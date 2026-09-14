---
description: "Clean Architecture layering for 1C — layer map, dependency rule, module taxonomy as enforcement, use-case modules, thin adapters (forms, HTTP services), testability seams. Load when deciding where code goes, designing a module set, or reviewing dependencies between forms, common modules and integrations. Триггеры: чистая архитектура, слои, зависимости, куда положить код, тонкие формы."
alwaysApply: false
kind: invariant
---

# Clean Architecture Applied to 1C

The goal is not portability off the platform — 1C *is* the framework and stays. The goal is the **dependency rule**: business logic does not know about UI or transport, adapters stay thin, and the core is reachable without a form. Everything below is that rule translated into platform artifacts.

> **Scope.** This file owns layering and dependency direction. Domain modeling (aggregates, events, language) — `rules/ddd-1c.md`. Code placement basics and the Result-Structure pattern — `rules/dev-standards-architecture.md`. Form-module mechanics — `rules/form-module.md`. Integration mechanics — `rules/integrations-add.md`.

## 1. Layer Map

| Clean Architecture layer | 1C artifacts |
|---|---|
| **Entities** (enterprise rules) | Object modules, manager modules, перечисления, определяемые типы, domain common modules; pure functions in `*КлиентСервер` modules |
| **Use cases** (application rules) | Server common modules with a `ПрограммныйИнтерфейс` region; регламентные задания entry points; command processing |
| **Interface adapters** | Managed forms and commands; HTTP-сервисы / веб-сервисы; отчёты и обработки as UI shells; format mappers (ACL) |
| **Frameworks & drivers** | Platform, БСП, СКД, СУБД, COM, file system, network |

## 2. The Dependency Rule in 1C Terms

Source dependencies point inward — outer layers know inner ones, never the reverse:

- **Nothing server-side knows about forms.** No form references, no form-specific assumptions in common modules. Form data types (`ДанныеФормыСтруктура`, `ДанныеФормыКоллекция`) must not cross the form boundary — convert at the edge (`РеквизитФормыВЗначение`, or pass primitives/refs/plain structures). A use-case signature containing a form type is a layer violation.
- **Domain modules do not call adapters.** An object module or domain service must not perform HTTP calls, file I/O, or COM — that is infrastructure reached from a use case or a background job, never from entity code (see also the outbox rule in `rules/ddd-1c.md §5`).
- **Use cases may orchestrate adapters** through the adapter's `ПрограммныйИнтерфейс` — this is the pragmatic substitute for ports when the language has no interfaces. The compensating constraint: the adapter contains **no business decisions**, so swapping it never changes behavior.
- **Client code orchestrates UI only.** `*Клиент` modules open forms, show notifications, collect input; every decision that touches data goes through `*ВызовСервера` to the server.

Allowed call directions: `Форма/Клиент → ВызовСервера → use case → domain → платформа`, and `use case → adapter`. Everything pointing the other way is a defect.

## 3. Module Taxonomy as Enforcement

БСП suffix conventions are the mechanism that makes the dependency rule reviewable:

| Suffix / kind | Layer | Constraint |
|---|---|---|
| `*КлиентСервер` | innermost | Pure functions: no DB reads, no session state, no side effects. Unit-testable by construction |
| server common module (no suffix) | domain / use case | May read/write DB; never references forms or client context |
| `*ВызовСервера` | boundary | Thin pass-through the forms call; delegates immediately, no logic of its own |
| `*Клиент` | UI orchestration | No business branching; decisions come from the server as data |
| `*ПолныеПрава` | infrastructure | Privileged operations only, paired enable/disable (`rules/dev-standards-architecture.md §5`) |
| модуль менеджера | domain | Object-scoped queries and operations (`rules/ddd-1c.md §6`) |

A module whose suffix lies about its content (a `*КлиентСервер` module that queries the DB via a server call, a `*ВызовСервера` module with 200 lines of logic) breaks the reviewer's ability to check direction by name — fix the module, not the name.

## 4. Use-Case Modules

- The `ПрограммныйИнтерфейс` region is the context's public contract; everything else is non-export or `СлужебныйПрограммныйИнтерфейс`. One export procedure per business action, named as the action: `СформироватьПакетСобытий`, `ПринятьКвитанцию` — not `Обработать` / `Выполнить`.
- Signature discipline: refs, primitives, and plain structures in; **Result-Structure out** (`rules/dev-standards-architecture.md §1`) for expected failures; exceptions only for the unexpected. The caller must be able to render the result without parsing message strings.
- A use case invoked by a регламентное задание or retried integration must be **idempotent** — re-running it on the same input produces no duplicate movements or outbox records.
- If a form "needs just a small query" — that query still goes through a server module (manager module for object-scoped, use case for cross-object). Form modules issuing ad-hoc queries accumulate untestable copies of domain logic.

## 5. Adapters Stay Thin

- **A form module is a controller:** collect input, call a use case, render the result. Business branching in a form handler is the classic violation — and every write path that bypasses forms (exchanges, COM, background jobs — a production reality in most bases) silently skips it. Enforcement belongs to the object module (`rules/ddd-1c.md §4`).
- **An HTTP service module is a controller too:** parse and validate the request, map to a use-case call, serialize the response, map errors to status codes. Domain logic in an HTTP module is unreachable from any other entry point.
- **One adapter module per external technology/format** (`{PREFIX}ОбменВнешнейСистемой`), endpoints and credentials in settings storage — never hardcoded (`rules/dev-standards-architecture.md §5 → Security`). The external system's vocabulary stays inside the adapter (ACL — `rules/ddd-1c.md §8`).
- Substitutability without polymorphism: when several adapters implement one operation (two providers, two transports), dispatch in **one** place via `Перечисление` + `Выбор` or an event subscription. `Выполнить()` / `Вычислить()` as poor-man's DI is prohibited (security rule).

## 6. Testability Seams

- Push computation into pure `*КлиентСервер` functions — parameters in, value out, no DB. This is the layer where logic can be exercised without a base and reused on the client for free.
- For server logic, separate *fetching* from *deciding*: a thin function reads the DB and hands tables/structures to a pure function that decides. The decision logic becomes testable with hand-built tables; the fetch stays trivial.
- If a use case needs "now", take `ТекущаяДатаСеанса()` **once at the entry point** and pass it down — logic parameterized by date is testable and replayable; logic that samples the clock mid-flow is neither.

## 7. What NOT to Import from the Textbook

- **No repository/UoW wrappers** over platform managers — `Справочники.X` already is the repository; wrapping it adds a layer with no seam.
- **No DTO ceremony for internal calls.** Structures at boundaries where types genuinely change (forms, HTTP, ACL) — yes; mirroring every object into a "DTO" for module-to-module calls — no.
- **No framework-independence goal.** Depending on БСП, СКД, platform query language is correct and idiomatic; the rule protects direction, not purity.
- **No class-hierarchy emulation** via structures carrying "method names" or `Вычислить`-dispatch. The platform's own polymorphism points — subscriptions, общие модули per type, `Перечисление` dispatch — cover the real cases.

## 8. Review Checklist

- [ ] No form data types outside form modules; conversion at the boundary
- [ ] No business branching in form or HTTP-service modules
- [ ] Server/common modules never reference forms or client context
- [ ] Public entry points only in `ПрограммныйИнтерфейс` regions, named as business actions
- [ ] Domain/object modules free of HTTP, file, COM calls
- [ ] Adapters config-driven, one per external technology, no domain decisions inside
- [ ] Dispatch between alternative adapters centralized; no `Выполнить`/`Вычислить` indirection
- [ ] Pure logic extracted to `*КлиентСервер` where feasible; fetch separated from decide
