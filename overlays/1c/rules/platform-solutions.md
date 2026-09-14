---
description: "Case book of common 1C platform pitfalls and proven fix templates: emptiness checks, long-running operations, temporary storage, transactions inside event handlers, copying objects, server time, collection search, external components on the thin client, background jobs started from an external data processor, a configuration load that hangs with no diagnostics, and restructuring errors. Триггеры: странное поведение платформы, длительная операция, временное хранилище, поиск в коллекции тормозит, загрузка конфигурации виснет без диагностики, реструктуризация таблицы падает, фоновое задание из внешней обработки не стартует."
alwaysApply: false
kind: case
---

# Platform Cases & Fix Templates

Each case follows the schema: **problem → symptom → correct template → reference to ITS standard or short rationale**.

---

## 1. Checking values for emptiness

**Problem.** Wrong predicate causes false positives on empty references, uninitialized variables, and attributes with default values.

**Symptom.** Conditions like `Если Контрагент <> Неопределено` skip empty refs `Справочники.Контрагенты.ПустаяСсылка()`; `Если ЗначениеЗаполнено(Реквизит)` on a form may return `Истина` for a freshly initialized composite reference.

**Template.**

```bsl
// Universal "non-empty" check for any value type.
Если ЗначениеЗаполнено(Контрагент) Тогда
    // ...
КонецЕсли;
```

For form attributes with reference or composite types — first copy the value to a local variable and check that, to avoid repeated platform property access:

```bsl
ТекущийКонтрагент = Объект.Контрагент;

Если ЗначениеЗаполнено(ТекущийКонтрагент) Тогда
    // ...
КонецЕсли;
```

**Standard.** ITS: "Использование функции ЗначениеЗаполнено".

---

## 2. Long-running operations

**Problem.** Direct background-job calls bypassing the БСП "Long-running operations" subsystem leave the UI without progress, no cancel handling, and no result serialization.

**Symptom.** Hanging client, no progress indication, "Cancel" button does nothing, result is lost on network drops.

**Template.** Use `ДлительныеОперации.ВыполнитьФункцию` with the correct method-name format:

```bsl
// On the server.
Параметры = Новый Структура;
Параметры.Вставить("ДатаНачала", ДатаНачала);
Параметры.Вставить("ДатаОкончания", ДатаОкончания);

ДлительнаяОперация = ДлительныеОперации.ВыполнитьФункцию(
    ПараметрыВыполнения,
    "Отчеты.ПродажиПоПериоду.СформироватьДанныеНаСервере",
    Параметры);
```

- `ИмяВыполняемогоМетода` format: `ИмяОбщегоМодуля.ИмяФункции` or `Тип.ИмяОбъекта.ИмяМетода` (no `ОбщийМодуль.` prefix).
- On the client, hook `ДлительныеОперацииКлиент.ОжидатьЗавершение` to poll status.
- Do NOT pass into a background job a temporary-storage address bound to the form session — pass serializable parameters; if needed, place the result into temporary storage from inside the job.

**Standard.** БСП: "Long-running operations" subsystem.

---

## 3. Temporary storage: correct functions

**Problem.** Using `ВременноеХранилище` as if it were an object instead of platform-level global functions.

**Symptom.** Error: «Метод объекта не обнаружен (Поместить)».

**Template.**

```bsl
// Wrong
Адрес = ВременноеХранилище.Поместить(Данные, УникальныйИдентификатор);
Данные = ВременноеХранилище.Получить(Адрес);

// Correct - platform global functions
Адрес = ПоместитьВоВременноеХранилище(Данные, УникальныйИдентификатор);
Данные = ПолучитьИзВременногоХранилища(Адрес);
```

**Standard.** Platform syntax assistant.

---

## 4. Transactions in event handlers

**Problem.** Nested transactions in `ПередЗаписью` / `ПриЗаписи` of an object lead to a double `НачалоТранзакции` and unexpected rollback behavior.

**Symptom.** "Транзакция не активна" on rollback, partially saved data on inner errors, cross-session locks.

**Fix.** In object-write event handlers **do not open your own transaction** — the platform has already opened one around `ПередЗаписью` → write → `ПриЗаписи` → posting. If an outer transaction is genuinely needed, it belongs in the calling code.

**Owned by `locks-and-transactions.md` §2.** The full treatment lives there: which operations open an implicit transaction, the only correct shape for an explicit one in calling code (with logging and re-raise), and what must never run inside a transaction. This entry exists so the symptom leads there — it does not carry its own copy of the template.

**Standard.** ITS: "Использование транзакций".

---

## 5. Copying objects and tabular sections

**Problem.** Calling a non-existent or wrong method `Копия()` instead of `Скопировать()`.

**Symptom.** "Метод объекта не обнаружен", lost rows of tabular sections when manually copying via a loop.

**Template.**

```bsl
// Value table.
КопияТаблицы = ИсходнаяТаблица.Скопировать();

// Structure.
КопияСтруктуры = Новый Структура;
Для Каждого КлючИЗначение Из ИсходнаяСтруктура Цикл
    КопияСтруктуры.Вставить(КлючИЗначение.Ключ, КлючИЗначение.Значение);
КонецЦикла;

// Document as a brand new object.
НовыйДокумент = Документы.РеализацияТоваровУслуг.СоздатьДокумент();
ЗаполнитьЗначенияСвойств(НовыйДокумент, ИсходныйДокумент, , "Номер,Дата,ПометкаУдаления,Проведен");
НовыйДокумент.Товары.Загрузить(ИсходныйДокумент.Товары.Выгрузить());
```

**Note.** For documents, you must clear `Номер`, `Дата`, `ПометкаУдаления`, `Проведен` — otherwise the platform may try to overwrite the source.

---

## 6. Time on the server

**Problem.** Using `ТекущаяДата()` on the server gives different values across cluster nodes and ignores the session time zone.

**Symptom.** Documents with "future" or "past" dates when users work in different time zones; mismatched logs and postings.

**Template.**

```bsl
// On the server - do NOT use
Текущая = ТекущаяДата();

// On the server
Текущая = ТекущаяДатаСеанса();

// On the client - ТекущаяДата() is acceptable, but obtaining it from the server is preferred
```

**Standard.** ITS: "Использование функций для работы с датой и временем".

---

## 7. Searching in collections: choosing by complexity

**Problem.** Linear `Найти()` / `НайтиПоЗначению()` in large collections is O(n) per call; inside a loop you get O(n²).

**Template.**

- Up to ~100 elements — `Найти()` / `НайтиПоЗначению()` is acceptable.
- From ~1000 elements upwards or inside a loop — build an index on `Соответствие` (Map), lookup becomes O(1):

```bsl
ИндексПоИНН = Новый Соответствие;

Для Каждого Строка Из ТаблицаКонтрагентов Цикл
    ИндексПоИНН.Вставить(Строка.ИНН, Строка.Контрагент);
КонецЦикла;

// O(1) lookup in subsequent loops.
Контрагент = ИндексПоИНН.Получить(ИНН);
```

- For frequent multi-key lookups — use `ТаблицаЗначений.Индексы.Добавить("Поле1, Поле2")` + `НайтиСтроки(Структура)` for indexed linear search.

---

## 8. External components on the thin client

**Problem.** Synchronous attach of an external component blocks the UI and does not work in the web client.

**Template.** Use the asynchronous form via `НачатьПодключениеВнешнейКомпоненты` + `ОписаниеОповещения`:

```bsl
&НаКлиенте
Процедура ПодключитьСканер()
    Оповещение = Новый ОписаниеОповещения("ПослеПодключенияСканера", ЭтотОбъект);
    НачатьПодключениеВнешнейКомпоненты(Оповещение, "ОбщийМакет.СканерКомпонента", "Сканер", ТипВнешнейКомпоненты.Native);
КонецПроцедуры

&НаКлиенте
Процедура ПослеПодключенияСканера(Подключено, ДополнительныеПараметры) Экспорт

    Если Не Подключено Тогда
        ОбщегоНазначенияКлиент.СообщитьПользователю("Не удалось подключить сканер.");
        Возврат;
    КонецЕсли;

    // ...
КонецПроцедуры
```

**Version note.** The callback shape above is the floor — it works everywhere.
On `{PLATFORM_VERSION}` ≥ 8.3.18 the project standard prefers `Асинх` / `Ждать`
over `ОписаниеОповещения` (`dev-standards-architecture.md §3`), and mixing the
two inside one `Асинх` procedure is forbidden. Write the async form there and
keep the callback for older targets — `async-methods.md` has both shapes.

**Standard.** ITS: "Внешние компоненты, асинхронный интерфейс".

---

## 9. Managed locks and deadlock prevention

**Problem.** Missing or incorrect managed locks cause read-write conflicts during posting; inconsistent lock ordering across documents leads to deadlocks.

**Symptom.** Sporadic «Конфликт блокировок при выполнении транзакции», deadlocks under load (especially in document posting), reading uncommitted data, balance inconsistencies after parallel posting.

**First move.** Lock the **register** you are about to read and modify, before reading it, and lock it in the same canonical order everywhere. Locking the document does not protect a register read, and two postings taking the same registers in different orders deadlock by construction.

**Owned by `locks-and-transactions.md`.** That rule is the treatment in full: lock primitives and modes (§3), the ordering contract (§4), the posting pattern with `ИсточникДанных` (§5), and how to read `TLOCK` / `TDEADLOCK` when diagnosing (§6). This entry is the symptom-side index into it, not a second copy — a compressed copy of a lock contract is exactly the thing that drifts and then contradicts the original.

**Standard.** ITS: "Управление блокировкой данных в транзакции", "Особенности проведения документов".

---

## 10. Background job from an external data processor

**Problem.** The "Long-running operations" subsystem runs the job on the
server, and the server has to be able to find the processor by name. A
processor opened through "file → open" (rather than registered in the
additional-reports-and-processors catalog) does not exist on the server, so the
job cannot be started at all.

**Symptom.** The background start fails for a processor that works fine when
run interactively; the same code works once the processor is registered in the
catalog.

**Template.** Put a copy of the processor on the server through temporary
storage at open time, and start the job by that copy's file name:

```bsl
// Client, ПриОткрытии: push the processor file into temporary storage,
// then in the callback ask the server for a copy.
&НаСервере
Функция КопияОбработкиНаСервере(Хранение)
    ИмяФайла = ПолучитьИмяВременногоФайла();
    ПолучитьИзВременногоХранилища(Хранение).Записать(ИмяФайла);
    Возврат ИмяФайла;                    // keep it in a form attribute
КонецФункции

// Server: name = the temp file for an external processor, the full metadata
// name for a built-in one.
ПараметрыЗадания = Новый Структура;
ПараметрыЗадания.Вставить("ИмяОбработки", ИмяОбработкиИлиФайла);
ПараметрыЗадания.Вставить("ИмяМетода", "<процедура модуля объекта>");
ПараметрыЗадания.Вставить("ПараметрыВыполнения", ПараметрыОбработки);
ПараметрыЗадания.Вставить("ЭтоВнешняяОбработка", ЭтоВнешняяОбработка);

Возврат ДлительныеОперации.ВыполнитьВФоне(
    "ДлительныеОперации.ВыполнитьПроцедуруМодуляОбъектаОбработки",
    ПараметрыЗадания, ПараметрыВыполнения);
```

Constraints that follow from the job running elsewhere: **the processor's own
attributes and tabular sections are not available inside the job** — pass
everything through parameters (same reason as §2: nothing bound to the form
session survives the hop).

**Do not reach for the unsafe-mode escape by default.** Re-creating the
processor without safe mode inside the job (`ВнешниеОбработки.Создать` with the
protection description that suppresses warnings) removes a platform protection
for the whole run. It is justified only when the job genuinely needs privileged
operations that safe mode blocks, and then it belongs in the design discussion,
with the reason written down next to the call — not slipped in to make an error
go away.

**Standard.** БСП: "Long-running operations" subsystem; see also §2 for the
general case.

---

## 11. Загрузка конфигурации или расширения виснет без диагностики

**Problem.** `DESIGNER /LoadConfigFromFiles` не завершается и ничего не сообщает:
`/Out` пуст, кода возврата нет, процесс висит десятками секунд и дольше.

**Symptom.** Отказ без единого признака отказа. Именно поэтому кейс здесь:
искать причину идут по симптому, а не по теме «XML метаданных».

**Первый подозреваемый — права на типы, которые прав не несут.** Блок
`<object>` на `Enum.*` (а также `FunctionalOption`, `DefinedType`,
`CommonModule`, `CommonPicture`, `CommonTemplate`) в `Rights.xml` роли
избыточен всегда, а на некоторых сборках платформы, по внешним наблюдениям,
подвешивает загрузку. Проверяется до запуска валидатором ролей скилла
метаданных. Разбор и вторая известная форма (новый объект вместе с ролью на
него в одной выгрузке) — `metadata-xml-workarounds.md §6`.

**Standard.** —

---

## 12. «Ошибка SDBL: Слишком большое значение описателя длины»

**Problem.** Платформа падает при реструктуризации таблицы после правки
метаданных, хотя XML валиден и загрузился.

**Symptom.** Ошибка приходит не при загрузке, а позже — при реструктуризации,
и указывает на длину, которую в изменённом реквизите никто не задавал.

**Две причины, обе в квалификаторах типа.** Строка фиксированной длины больше
1024 символов (для длинных текстов длина должна быть `0` — хранение LOB), либо
у числа не задан явно дробный квалификатор: отсутствующий читается при
реструктуризации не как ноль, а как максимум. Точные имена элементов для
выгрузки Конфигуратора и для EDT различаются — `metadata-xml-workarounds.md §7`.

**Standard.** —

---

## Extending this case book

This file is a stack-specific case book of typical pitfalls, using the
"Problem → Symptom → Template → Standard" schema below.

When you discover a new typical pitfall:

1. Add a new section using the "Problem → Symptom → Template → Standard" schema.
   **If the topic already has an owning rule, the entry keeps Problem and
   Symptom and points at it instead of carrying a template.** The case book is
   the symptom-side index; a compressed second copy of someone else's rule
   drifts, and the day it contradicts the original nobody can tell which one is
   current.
2. If the solution depends on the platform or БСП version — state the version explicitly.
3. If a minimal reproducible example exists — include it.
4. When possible, link to ITS, the platform documentation, or a specific БСП module.
