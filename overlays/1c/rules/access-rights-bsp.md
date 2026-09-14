---
description: "Working with БСП access-group profiles and rights from code: the profile saved but its roles are gone, extension roles silently missing from a profile, assigning a profile to a user, checking a right / role / record-level access. Триггеры: профиль записался без ролей, назначить профиль программно, проверить право, проверить роль, роли расширения не находятся, ПрофилиГруппДоступа."
alwaysApply: false
kind: recipe
---

# Access-group profiles and rights from code (БСП)

Applies to configurations on БСП 3.x when profiles are created or updated from
a code console or an update handler, when profiles are assigned to users, and
when code checks a right, a role or record-level access.

> **Verified** against a Configurator dump of a standard configuration on
> БСП **3.1.11** — attribute types, method signatures and the write handler
> were read from the source, not taken on trust. On a different library
> version re-check before relying on the negative statements below.
>
> This is a **recipe**, not an invariant: it is needed when the task is about
> rights, not on every edit of a module. Load it by the task, not by the file.

## 1. `Роли.Роль` is a reference, never a string

The tabular-section attribute `Справочник.ПрофилиГруппДоступа.Роли.Роль` is a
**composite reference** type:

```
CatalogRef.ИдентификаторыОбъектовРасширений
CatalogRef.ИдентификаторыОбъектовМетаданных
```

```bsl
// WRONG — the row survives the assignment and dies at write time
НоваяСтрока = Профиль.Роли.Добавить();
НоваяСтрока.Роль = "ПолныеПрава";
```

**Symptom.** `Профиль.Записать()` raises nothing, and afterwards the tabular
section holds **0–1 rows instead of N**.

**Why it looks like data loss rather than an error.** The profile's
`ПередЗаписью` walks the `Роли` section and removes rows it does not accept —
it deduplicates by the attribute value and strips administrator roles. Rows
that never received a real reference all carry the same non-value, so the
deduplication collapses every one of them into a single row. Nothing in that
path reports a problem: the write succeeds, the roles are simply not there.

## 2. Extension roles live in a second catalog

Roles that come from a configuration extension are registered in
`ИдентификаторыОбъектовРасширений`, not in `ИдентификаторыОбъектовМетаданных` —
which is exactly why the attribute above is composite.

**Consequence:** a direct query against `Справочник.ИдентификаторыОбъектовМетаданных`
**cannot find an extension role**. The profile then gets its base roles and
silently misses the extension ones — the same failure shape as §1, from a
different cause.

Use the library call, which resolves against **both** catalogs:

```bsl
ПолныеИмена = Новый Массив;
Для Каждого ИмяРоли Из ИменаРолей Цикл
    ПолныеИмена.Добавить("Роль." + ИмяРоли);   // full name of a role identifier
КонецЦикла;

// Соответствие [полное имя -> ссылка]; Ложь — не падать на ненайденных.
КартаИдентификаторов = ОбщегоНазначения.ИдентификаторыОбъектовМетаданных(ПолныеИмена, Ложь);
```

Two related traps:

- With `ВызыватьИсключение = Ложь` unresolved names are **skipped silently** —
  count what came back and report the difference, do not assume a full map.
- In the profile's role list the platform shows role **synonyms**, not names.
  Filtering the interface by a name prefix finds nothing for a role whose
  synonym is human-readable. When the input is synonyms (a spreadsheet, a
  document), match on `Метаданные.Роли[...].Синоним` with a normalized fallback
  (lower case, trimmed, collapsed double spaces) — plain equality on synonyms
  is too brittle for hand-made sources.

## 3. Creating or updating a profile

```bsl
УстановитьПривилегированныйРежим(Истина);

СсылкаПрофиля = Справочники.ПрофилиГруппДоступа.НайтиПоНаименованию(ИмяПрофиля, Истина);
Если СсылкаПрофиля.Пустая() Тогда
    Профиль = Справочники.ПрофилиГруппДоступа.СоздатьЭлемент();
    Профиль.Наименование = ИмяПрофиля;
Иначе
    Профиль = СсылкаПрофиля.ПолучитьОбъект();
КонецЕсли;

Профиль.Роли.Очистить();
Для Каждого ИмяРоли Из ИменаРолей Цикл
    СсылкаИдент = КартаИдентификаторов.Получить("Роль." + ИмяРоли);
    Если СсылкаИдент = Неопределено Тогда
        Продолжить;                      // log it — see §2
    КонецЕсли;
    Профиль.Роли.Добавить().Роль = СсылкаИдент;
КонецЦикла;

Если Профиль.Назначение.Количество() = 0 Тогда
    Профиль.Назначение.Добавить().ТипПользователей = Справочники.Пользователи.ПустаяСсылка();
КонецЕсли;

Профиль.Записать();                      // NOT with ОбменДанными.Загрузка
```

- **Never set `ОбменДанными.Загрузка = Истина` to "make the write go
  through".** The `ПередЗаписью` shown in §1 returns early in that mode, and so
  do the handlers that register the profile in the access subsystem. The
  profile lands in the catalog and never reaches the rights machinery — a
  failure that surfaces much later, as a user without the rights they were
  granted.
- **Do not edit a supplied profile.** The library keeps a
  `ПоставляемыйПрофильИзменен` flag, marks parts of a supplied profile
  non-editable and owns a full update path for them
  (`ОбновитьПоставляемыеПрофили`, `ЗаполнитьПоставляемыйПрофиль`). Whatever the
  exact restore semantics on a given version, your edit is at best contested by
  the library on the next configuration update. Create your own profile.

## 4. Assigning a profile to a user

```bsl
// Профиль — ссылка, уникальный идентификатор поставляемого профиля или его имя.
УправлениеДоступом.ВключитьПрофильПользователю(Пользователь, Профиль);
УправлениеДоступом.ВыключитьПрофильПользователю(Пользователь, Профиль = Неопределено);
УправлениеДоступом.УстановитьПраваПользователя(Пользователь, ГруппыДоступа, ГруппыПользователей);
```

`Пользователь` is a `СправочникСсылка.Пользователи` or
`СправочникСсылка.ВнешниеПользователи`. `ВключитьПрофильПользователю` is built
for the **simplified** rights mode, where it finds or creates a personal access
group; with the simplified mode off, work through access groups via
`УстановитьПраваПользователя`. Passing `Неопределено` as the profile to
`ВыключитьПрофильПользователю` disables **all** of the user's profiles — do not
reach for it as a "clean slate" without meaning exactly that.

## 5. Checking a right, a role, record-level access

```bsl
Пользователи.РолиДоступны(ИменаРолей, Пользователь, УчитыватьПривилегированныйРежим)
Пользователи.ЭтоПолноправныйПользователь(Пользователь, ПроверятьПраваАдминистрированияСистемы, УчитыватьПривилегированныйРежим)
УправлениеДоступом.ЕстьПраво(Право, СсылкаНаОбъект, Пользователь)
УправлениеДоступом.ЕстьРоль(Роль, СсылкаНаОбъект, Пользователь)
УправлениеДоступом.ЧтениеРазрешено(ОписаниеДанных, Пользователь)
УправлениеДоступом.ИзменениеРазрешено(ОписаниеДанных, Пользователь)
```

- **`ИменаРолей` is a comma-separated *string*, not an array** — the parameter
  is documented as such in the module, and an array silently checks nothing
  useful. Returns `Истина` if at least one of the roles is available.
- **Prefer the library over the platform's `РольДоступна`** in a configuration
  on БСП: the platform function accounts for neither privileged mode nor the
  fully-authorized user.
- **`ЕстьПраво`'s second argument is a reference to a data object** (a file
  folder and the like), not a metadata object. Passing `Метаданные.*` is a
  mistake.
- **`ЕстьРоль` checks the role through access-group profiles with read
  restrictions applied**; a plain configuration-role check without record-level
  restrictions is `Пользователи.РолиДоступны`.
- **`ЧтениеРазрешено` / `ИзменениеРазрешено` are about record-level access.** In
  the non-performance variant, asking about a user other than the current one
  raises an exception — check `УправлениеДоступом.ПроизводительныйВариант()`
  first.
- The client-side equivalent of the full-rights check is
  `ПользователиКлиент.ЭтоПолноправныйПользователь(...)`, current user only.

## 6. What to check before calling an unfamiliar method here

The rights API is a place where plausible names are easy to invent and easy to
get wrong — `ДобавлениеПользователейВГруппу`, for one, does not exist on 3.1.11;
assignment is `ВключитьПрофильПользователю`, full reset is
`УстановитьПраваПользователя`. Confirm an unfamiliar method against the module
source and note which region it sits in — see the standard-library API section
of `dev-standards-architecture.md §3`.

## Companion rules

| Concern | File |
|---|---|
| Static role rights in `Rights.xml`, enums in roles | `metadata-xml-workarounds.md §6` |
| Which library methods are callable at all | `dev-standards-architecture.md §3` |
| Extension patterns and adopted objects | `extension-patterns.md` |
| Role XML tooling (create / analyze / validate) | the `1c-metadata-manage` skill (`role-manage` doc) |
