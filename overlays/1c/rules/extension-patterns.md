---
description: "1C configuration extension (CFE) patterns — interceptor types (`&Перед` / `&После` / `&Вместо`), `ПродолжитьВызов` rules, change markers, adopted-object constraints. Load when writing or reviewing extension code. Триггеры: расширение конфигурации, Перед и После, Вместо, ИзменениеИКонтроль, ПродолжитьВызов, заимствованный объект, расширение не срабатывает."
alwaysApply: false
kind: invariant
---

# 1C Extension Patterns (CFE)

BSL patterns for working with 1C configuration extensions.

Applies to: extension code (`**/Extensions/**/*.bsl` and similar).

Background reference: `rules/dev-standards-architecture.md §2` (Extensions) — modification priority, directives, placement rules. This file is the **practical** companion: interceptor types, `ПродолжитьВызов` semantics, markers, and adopted-object constraints.

> **Naming convention used in examples.** Below, `Расш1_` / `МоеРасш_` denotes the **extension's own short alias** (set in the extension's properties — typically the `Имя` of the extension or an explicit alias), **not** `{PREFIX}` from `.dev.env`. `{PREFIX}` applies to new metadata objects and attributes; the extension alias applies to procedure / function names introduced by the extension and prevents name collisions between extensions. The two are independent: an extension can both add a new attribute `{PREFIX}Признак` to a typical object and define an interceptor procedure `Расш1_ПриЗаписи` in the same module.
>
> The alias itself MUST NOT contain the letter «ё» — see `rules/dev-standards-core.md §6 → Typography`. Use `МоеРасш_`, `Расш1_`, `MyExt_` or any «ё»-free form.

---

## Interceptor types

| Directive | Type | When to use |
|-----------|------|-------------|
| `&Перед("ИмяМетода")` | Before | Code before the original method |
| `&После("ИмяМетода")` | After | Code after the original method |
| `&Вместо("ИмяМетода")` | Instead | Full replacement / wrap of the method; the only directive where `ПродолжитьВызов()` is allowed |
| `&ИзменениеИКонтроль("ИмяМетода")` | ModificationAndControl | Designer-side workflow over a copied method body with `#Вставка` / `#Удаление` markers — not a hand-written interceptor |

> **Verified on 8.3.27 (bsl-analyzer 0.2.28, file infobase runtime).**
> `ПродолжитьВызов()` compiles **only** inside `&Вместо` — anywhere else it is
> `Blocker: WrongUseFunctionProceedWithCall`. Write every full-override /
> wrap-around interceptor as `&Вместо`. `&ИзменениеИКонтроль` is a separate
> designer workflow (a modified copy of the vendor's method body, where the
> designer tracks the diff against the vendor's code) — do **not** mix its
> markers into hand-written methods (see "Change markers" below).

### Before / After — simple interceptors

```bsl
&НаСервере
&Перед("ПриЗаписи")
Процедура Расш1_ПриЗаписи()
    // Runs BEFORE the original ПриЗаписи
КонецПроцедуры

&НаСервере
&После("ПриЗаписи")
Процедура Расш1_ПослеЗаписи()
    // Runs AFTER the original ПриЗаписи
КонецПроцедуры
```

### Вместо — full replacement / wrap

```bsl
&НаСервере
&Вместо("ОбработкаЗаполнения")
Процедура Расш1_ОбработкаЗаполнения(ДанныеЗаполнения, СтандартнаяОбработка)
    Если НеНашСлучай() Тогда
        ПродолжитьВызов(ДанныеЗаполнения, СтандартнаяОбработка); // bit-for-bit original
        Возврат;
    КонецЕсли;

    // own code before / instead / after the original
    ПродолжитьВызов(ДанныеЗаполнения, СтандартнаяОбработка);
    // own code operating on the original's result
КонецПроцедуры
```

For a *function*, return the wrapped value: `Возврат ПродолжитьВызов(...)`.
The `&Вместо` body is plain extension code — **no** `#Вставка` / `#Удаление`
markers inside it (see below).

---

## ПродолжитьВызов() rules

- `&Перед` — the original runs automatically afterwards. **Do not call manually.**
- `&После` — the original has already executed; `ПродолжитьВызов()` is not used.
- `&Вместо` — `ПродолжитьВызов()` is **mandatory** for the original to run (call it
  with the same parameters; for functions — return its value). Without it, the
  original method does **not** execute. It is also the **only** directive where
  the call compiles.

---

## Change markers

`#Вставка` / `#КонецВставки` and `#Удаление` / `#КонецУдаления` belong **only**
to the designer's `ИзменениеИКонтроль` workflow (a modified copy of a vendor
method body, where the designer tracks the diff against the vendor's code).
They preserve diff/merge semantics when the base configuration is updated.

**Never put these markers into hand-written `&Вместо` / `&Перед` / `&После`
methods.** Verified on 8.3.27 (file infobase runtime): markers inside a plain
`&Вместо` method make the platform **silently skip applying the module** — the
deploy succeeds (`LoadConfigFromFiles` / `UpdateDBCfg` exit 0), the syntax
checker emits only odd secondary diagnostics, but the interceptor never runs.
This failure mode costs hours because nothing reports an error; if an
interceptor "does nothing" after a clean deploy, check for stray markers first.

---

## Constraints on adopted (borrowed) objects

- An adopted object (`ObjectBelonging=Adopted`) is **not a copy** — it is a reference to a base-configuration object brought into the extension's scope so that the extension can attach interceptors and add its own attributes / tabular sections / form elements. The original definition still lives in the base configuration; on a base-configuration update the adopted object is automatically re-read, and the extension is re-applied on top of it.
- You **cannot** delete existing attributes / tabular sections of an adopted object — they belong to the base configuration.
- You **can** add your own attributes / tabular sections (with `{PREFIX}` from `.dev.env`).
- Modules of adopted objects — interceptors only (`&Перед` / `&После` / `&Вместо`), no direct edits to the original procedure body.
- Forms of adopted objects — you can add elements, you cannot delete existing ones.

---

## Identifiers of adopted objects

Two different uuids live in one file and are easy to swap:

- `ExtendedConfigurationObject` — the uuid of the object **in the base
  configuration**. It is a controlled property, checked on apply. Copy it from
  the base-configuration dump for the root element **and for every adopted
  child** (dimension, resource, attribute).
- the element's own `uuid` — a **new** GUID belonging to the extension side.

Swap them and the load still succeeds; the failure appears later, on apply, as
«Конфликт внутренних идентификаторов у объекта» or «Значение контролируемого
свойства ОбъектРасширяемойКонфигурации не совпадает». An adopted dimension or
attribute of a reference type additionally requires the target object to be
adopted too.

After fixing borrowing identifiers, recreate the objects cleanly: load once
**without** them (cleared from storage), then load **with** them. Editing the
files in place can leave a conflicting saved copy behind.

## Adopted managed form — two element trees in one file

`Form.xml` of an adopted form contains **two** copies of the element tree: the
extension's own merged tree at the top, and a snapshot of the donor form in a
`BaseForm` block at the end, used only for conflict detection against the base
configuration.

Add new elements, buttons and commands **only to the top tree**. Anything
placed inside `BaseForm` is ignored at best; a button that references an
extension command from there fails the load with «Неверное имя команды
элемента формы» — the donor form does not know the extension's commands. The
`BaseForm` snapshot is not edited at all: it must stay byte-for-byte as the
donor's. New commands go into the extension's `Commands` block, before
`BaseForm`.

## Getting a real error list out of a silent apply

`/UpdateDBCfg -Extension` can exit with code 101, an **empty** `/Out` log and
nothing in the event log: it fails silently on apply errors.

To see the actual problems, dump the extension to `.cfe` via
`/DumpCfg -Extension` and call
`РасширениеКонфигурации.ПроверитьВозможностьПрименения(ДвоичныеДанные, Истина)`
from a COM session — it returns **all** problems, not just the first.

A neighbouring cause of a broken update: leftover `1Cv8tmp.*.cfl` files in the
infobase directory from an interrupted restructuring. In the technological log
this shows up as a missing database file named `1Cv8tmp`.

## An external data processor cannot be typed over extension objects

Building an `.epf` via `/LoadExternalDataProcessorOrReportFromFiles` resolves
types **against the base configuration only**. A form attribute (or a table
column) typed with an object that the **extension** adds breaks the build —
even though the same type works inside the extension. The error names the form
markup file while the real problem is in the `Attributes` block, so chasing
element order there is a dead end.

Diagnose in two runs: build a known-good processor to clear the toolchain,
then cut the form down to a single attribute.

Workaround: keep a presentation or a name in the form attribute as
`xs:string` and resolve the reference in the object module by name. Types from
the **base** configuration work normally. The consequence is structural: an
`.epf` cannot declare a typed attribute over extension-owned objects at all —
either strings and UUIDs, or the processor lives inside the extension.

---

## Anti-patterns

### Direct edit of an adopted module

```bsl
// WRONG: editing original code in place
Процедура ПриЗаписи()
    // changed code...
КонецПроцедуры

// RIGHT: interceptor
&Перед("ПриЗаписи")
Процедура Расш1_ПриЗаписи()
    // additional code
КонецПроцедуры
```

### Forgotten ПродолжитьВызов

```bsl
// DANGEROUS: original method will not execute!
&Вместо("ОбработкаПроведения")
Процедура Расш1_ОбработкаПроведения(Отказ, РежимПроведения)
    // own code...
    // FORGOT: ПродолжитьВызов(Отказ, РежимПроведения);
КонецПроцедуры
```

### No prefix in extension method names

```bsl
// Bad: name conflict with other extensions
Процедура ДополнительнаяПроверка()

// Good: extension prefix
Процедура МоеРасш_ДополнительнаяПроверка()
```

---

## Extension purpose tag

Set the `Purpose` (Назначение) of the extension in its properties:

| Type | Purpose | When to use |
|------|---------|-------------|
| Patch | `Patch` | Minimal changes, interceptors only |
| Customization | `Customization` | Attributes, forms, modules |
| AddOn | `AddOn` | Full new functionality |

The `Purpose` value affects update behaviour and the way the platform reapplies the extension after a base-configuration update.
