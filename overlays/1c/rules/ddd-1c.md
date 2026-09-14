---
description: "Domain-Driven Design applied to 1C — ubiquitous language, bounded contexts, aggregates and consistency boundaries, invariants, domain events, anti-corruption layer. Load when modeling a new domain area, carving a contour into an extension, or reviewing a design against domain boundaries. Триггеры: DDD, доменная модель, агрегаты, границы контекстов, инварианты, доменные события."
alwaysApply: false
kind: invariant
---

# DDD Applied to 1C

The platform already ships most *tactical* DDD machinery: reference objects are entities, object managers are repositories, posting is a unit of work. The payoff of DDD in 1C is therefore mostly **strategic** — language, context boundaries, aggregate discipline, explicit events. Do not re-implement what the platform gives; do name and bound what it leaves formless.

> **Scope.** This file owns domain-modeling decisions. Layering and dependency direction — `rules/clean-architecture-1c.md`. Register mechanics — `rules/registers-design.md`. Transactions and locks — `rules/locks-and-transactions.md`. Integration mechanics — `rules/integrations-add.md`.

## 1. Ubiquitous Language

- Metadata names and synonyms **are** the ubiquitous language. Objects, attributes, enums are named in Russian domain terms as the business says them; the synonym must match the term used in the task specification. Divergence between spec term and metadata synonym is a defect, not a style issue.
- **One term — one concept.** The same thing must not appear as `Событие` in one module and `Инцидент` in another. When two terms compete, settle it at design time and record the decision in the project's decision log, if one is kept.
- Domain object names carry no implementation vocabulary. `{PREFIX}ОчередьСобытий` — fine (queue is the domain concept); `{PREFIX}ТаблицаВыгрузки` — not (a table is storage, not a concept). Implementation words (`Кэш`, `Буфер`, `Соответствие`) belong only to infrastructure objects.
- Renaming is cheap before release and brutally expensive after (forms, RLS, exchanges, saved settings all hold names). Spend the argument early.

## 2. Bounded Contexts

- **An extension (CFE) is the strongest context boundary the platform offers** — one contour, one extension, one name prefix (e.g. a regulatory-exchange contour and a core-business contour as two extensions over one host configuration, each with its own prefix). Inside a configuration, a context is marked by подсистема + name prefix.
- **Cross-context calls go through the context's public API only** — its `*ПрограммныйИнтерфейс` common modules. Reaching into another context's registers or object internals couples you to its storage layout: read-only access is tolerated with an explicit comment; **writes to another context's data are forbidden** — ask that context's API to do it.
- **Shared kernel** = host-configuration objects used by several contexts. Treat any change to them as a contract change: run impact analysis (RLM: `find_call_hierarchy`, `find_code_usages`, `find_references_to_object`) before touching, and prefer extending over modifying (`rules/extension-patterns.md`).
- The context map (which contour owns what, who calls whom) lives in the Project section of the root contract (`AGENTS.md`). A new context or a moved responsibility is a recorded decision, not a silent refactor.

## 3. Aggregates and Consistency Boundaries

The aggregate root in 1C is an object with a reference — a document or catalog item. Its consistency boundary is what the platform writes in one transaction: **the object + its табличные части + register movements produced by its posting**.

- **One transaction — one aggregate.** Writing another document or catalog object from `ПередЗаписью` / `ОбработкаПроведения` crosses the boundary: it escalates locks, creates recursive posting chains, and makes repost order matter. Cross-aggregate reactions go through domain events (§5) — synchronous subscription or deferred outbox.
- **Movements are written only by their registrar.** A register subordinate to a registrar belongs to that registrar's aggregate; writing its `НаборЗаписей` with someone else's registrar bypasses ownership. Independent information registers are their own micro-aggregates (identity = the dimension set).
- **Choosing the root.** Data always read and written with its parent → табличная часть. A child entity referenced from outside the aggregate → subordinate catalog (`Владелец`). A "line catalog" nothing else references is a smell — it should have been a tab section.
- Cross-aggregate consistency is **eventual by design**: registers and events reconcile aggregates, not multi-object transactions. If the business insists two objects change "together", model the fact that connects them (usually a register) instead of a distributed write.

## 4. Invariants

All write paths converge at the **object module** — forms are only one entry among many (COM, exchanges, background jobs — production writes often bypass forms entirely). Form-side validation is UX sugar; the object module is the enforcement line.

- Enforcement points: `ОбработкаПроверкиЗаполнения` (fillability), `ПередЗаписью` (normalization, cross-field rules, diff vs preimage), `ОбработкаПроведения` (movement invariants). `Отказ = Истина` always ships with a message naming the reason and the field (`ОбщегоНазначенияКлиентСервер.СообщитьПользователю`).
- **Preimage pattern.** Inside `ПередЗаписью` the database still holds the previous version — query by `Ссылка` to compute "before/after" diffs. After the transaction commits, the preimage is gone; write-time is the only moment change-detection predicates can run (the core mechanism of any change-detection contour).
- An invariant that lives only in a form is not an invariant. If you find one during review, move it down to the object module and leave the form check as an early-feedback duplicate.

## 5. Domain Events

- **Synchronous, in-transaction:** подписки на события. All subscription handlers of a context live in `{PREFIX}ПодпискиНаСобытия` (see `rules/dev-standards-architecture.md §1`); keep the handler thin — detect and delegate to a domain-service module.
- **Asynchronous / cross-context / integration:** the **outbox** — an information register (dimensions: aggregate key; attributes: payload, status, attempts) filled inside the write transaction, drained by a регламентное задание. The write transaction records *the fact*; delivery happens outside it.
- **No I/O inside a write transaction.** HTTP calls, file export, COM inside `ОбработкаПроведения` or a subscription handler hold locks for the duration of an external system's latency and make the write's success depend on network weather. Always through outbox + job.
- Name events in domain terms with their business meaning (`ДоговорПереданВАрхив`, `ЗаявкаОдобрена`), not by their transport.

## 6. Domain Services and Repositories

- **The platform is the repository.** `Справочники.X` / `Документы.X` / query language already are the data-access layer — wrapper modules that re-expose `НайтиПоНаименованию` add indirection and nothing else. What you *do* centralize: non-trivial queries scoped to one object type go into that object's **модуль менеджера** as export functions (`Документы.X.АктуальныеНаДату(...)`).
- **A domain service is a server common module named by capability**, not by kinship: `{PREFIX}ФормированиеОчередиСобытий`, not `{PREFIX}Общее`. A module named `Утилиты` / `Разное` is a grab-bag by construction — split by the domain question it answers.
- Logic that concerns exactly one entity belongs to its object/manager module; a service module exists only for logic that genuinely spans entities.

## 7. Value Objects

BSL has no user-defined classes; approximate value objects deliberately:

- Closed value set → `Перечисление`. Reused compound type → `ОпределяемыйТип`. String statuses and numeric magic codes are primitive obsession (`rules/dev-standards-architecture.md §6`).
- Compound value → structure built by a **constructor function** in the domain module, validated at construction, treated as immutable (use `ЗафиксированнаяСтруктура` to enforce):

```bsl
// {PREFIX}Периоды
Функция НовыйПериодДействия(ДатаНачала, ДатаОкончания) Экспорт
	Если ДатаНачала > ДатаОкончания Тогда
		ВызватьИсключение НСтр("ru = 'Период задан некорректно'");
	КонецЕсли;
	Возврат Новый ФиксированнаяСтруктура("ДатаНачала, ДатаОкончания", ДатаНачала, ДатаОкончания);
КонецФункции
```

- Values that always travel together (`Сумма` + `Валюта`) are one value object: pass them as one structure, not as loose parameters (Data Clumps smell).

## 8. Anti-Corruption Layer

- **One module owns each external format.** External field names — an exchange partner's, a regulator's XSD, a bank API's vocabulary — appear in exactly one mapper module (`{PREFIX}ПреобразованиеФормата<Система>`); everything else speaks domain terms. Grep test: an external field name found outside its ACL module is a leak.
- Translation happens at the boundary in both directions — external → domain on intake, domain → external on export. Domain code never branches on external codes.
- When the external model is wrong for the domain (e.g. the source system sends flags valid for one transaction only), the ACL is where the impedance is absorbed: persist what the domain needs before the external artifact evaporates.

## 9. Review Checklist

- [ ] New objects named in spec terms; synonym = spec term; no synonym drift across modules
- [ ] No write to a foreign aggregate inside another aggregate's transaction
- [ ] Movements written only by their registrar
- [ ] Invariants enforced in the object module, not only in forms
- [ ] Integration side effects outside write transactions (outbox + job)
- [ ] External format vocabulary confined to its ACL module
- [ ] Cross-context calls via `*ПрограммныйИнтерфейс` only; no writes into another context's data
