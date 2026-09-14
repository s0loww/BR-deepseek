---
description: "Constructs that are wrong on sight in 1C code — query inside a loop, dot notation on a reference, subquery in the field list, virtual-table filter in WHERE, missing ПЕРВЫЕ N, needless server round trips — with the corrected form of each. Load before writing or reviewing queries and server-side code. Триггеры: анти-паттерн, медленный запрос, оптимизация кода, ревью запроса."
alwaysApply: false
kind: invariant
---
# 1C Anti-Patterns and Performance Guidelines

Shape-level smells judged over a module or subsystem (God Module, Tight
Coupling, Premature Optimization) are a different thing and live in
`dev-standards-architecture.md §6`. This file is about constructs that are
wrong where they stand.

## Checklist — read this first

Everything below is one of these eleven, in detail. If you only need to know
what to look for, this table is the rule; the sections after it are the
evidence and the corrected form.

| Anti-Pattern | Severity | Check For |
|--------------|----------|-----------|
| Query in loop | CRITICAL | `Для Каждого` followed by `Новый Запрос` |
| Dot notation | CRITICAL | `.Реквизит` on references |
| Subquery in SELECT | CRITICAL | Nested `ВЫБРАТЬ` in field list |
| Ambiguous query alias in JOIN | HIGH | Table alias `КАК X` where field also `КАК X`; `КАК Документ` for Регистратор |
| Virtual table WHERE | HIGH | Conditions on virtual table results |
| Missing TOP N | HIGH | Large queries without `ПЕРВЫЕ` |
| Multiple server calls | HIGH | Sequential `НаСервере` calls from client |
| `&НаСервере` misuse | HIGH | Server call not needing form context |
| Missing cache | MEDIUM | Repeated expensive calls with same params |
| O(n²) loops | MEDIUM | Nested loops searching for matches |
| Deep nesting | MEDIUM | >4 levels of conditionals/loops |
| Dot access on a composite field | HIGH | `Регистратор.<поле>` without `ВЫРАЗИТЬ` |
| `.Наименование` for display only | MEDIUM | `.Наименование` where `ПРЕДСТАВЛЕНИЕ()` would do |
| Subquery inside a join | HIGH | `СОЕДИНЕНИЕ (ВЫБРАТЬ …)` instead of an indexed temp table |
| Virtual table joined directly | HIGH | `СОЕДИНЕНИЕ Регистр….Остатки(…)` without materialising first |
| `ИЛИ` in `ГДЕ` | HIGH | `ГДЕ A = &X ИЛИ B = &Y` instead of `ОБЪЕДИНИТЬ ВСЕ` |
| `ОБЪЕДИНИТЬ` where parts cannot overlap | MEDIUM | missing `ВСЕ` |
| Index added, nothing got faster | HIGH | the condition does not line up with the index — rule and worked example in `dev-standards-architecture.md §3` |

## Critical Anti-Patterns (Must Fix)

### 1. Query in Loop

**Impact:** O(n) database calls → O(1)
**Severity:** CRITICAL

```bsl
// ❌ CRITICAL: N database calls
Для Каждого Строка Из Данные Цикл
    Запрос = Новый Запрос("ВЫБРАТЬ ... ГДЕ Ссылка = &Ссылка");
    Запрос.УстановитьПараметр("Ссылка", Строка.Ссылка);
    РезультатЗапроса = Запрос.Выполнить();
КонецЦикла;

// ✅ OPTIMIZED: 1 database call
Запрос = Новый Запрос;
Запрос.Текст =
"ВЫБРАТЬ ...
|ГДЕ
|   Ссылка В (&СписокСсылок)";
Запрос.УстановитьПараметр("СписокСсылок", 
    Данные.ВыгрузитьКолонку("Ссылка"));
РезультатЗапроса = Запрос.Выполнить();
```

### 2. Direct Attribute Access (Dot Notation)

**Impact:** Loads entire object from database
**Severity:** CRITICAL
**Note:** Project default is a hard ban outside trivial single-call handlers. **[Project rule — stricter than ITS standard]** — ITS allows occasional dot-notation in non-hot code; the project default is to use dedicated БСП methods regardless. See `rules/dev-standards-architecture.md §4`.

```bsl
// ❌ CRITICAL: Full object load for each attribute
ИНН = Контрагент.ИНН;
КПП = Контрагент.КПП;
Наименование = Контрагент.Наименование;

// ✅ OPTIMIZED: Single targeted query via SSL
Реквизиты = ОбщегоНазначения.ЗначенияРеквизитовОбъекта(
    Контрагент, "ИНН, КПП, Наименование");
ИНН = Реквизиты.ИНН;
КПП = Реквизиты.КПП;
Наименование = Реквизиты.Наименование;
```

**SSL Methods Reference:** See `rules/dev-standards-architecture.md §4 "Data Access — Reference Attribute Access"`.

### 3. Subquery in SELECT

**Impact:** N+1 query execution
**Severity:** CRITICAL

```bsl
// ❌ CRITICAL: Subquery executed per row
"ВЫБРАТЬ
|   Заказы.Ссылка,
|   (ВЫБРАТЬ СУММА(Оплаты.Сумма) 
|    ИЗ Документ.Оплата КАК Оплаты 
|    ГДЕ Оплаты.Заказ = Заказы.Ссылка) КАК СуммаОплат
|ИЗ
|   Документ.Заказ КАК Заказы"

// ✅ OPTIMIZED: Single join with aggregation
"ВЫБРАТЬ
|   Заказы.Ссылка КАК Ссылка,
|   ЕСТЬNULL(Оплаты.СуммаОплат, 0) КАК СуммаОплат
|ИЗ
|   Документ.Заказ КАК Заказы
|       ЛЕВОЕ СОЕДИНЕНИЕ (
|           ВЫБРАТЬ
|               Оплаты.Заказ КАК Заказ,
|               СУММА(Оплаты.Сумма) КАК СуммаОплат
|           ИЗ
|               Документ.Оплата КАК Оплаты
|           СГРУППИРОВАТЬ ПО
|               Оплаты.Заказ) КАК Оплаты
|       ПО Заказы.Ссылка = Оплаты.Заказ"
```

## High Priority Anti-Patterns

### 4. Ambiguous Query Alias in JOIN

**Impact:** Runtime query error `Неоднозначное поле "X.Y"` — module fails to compile or execute
**Severity:** HIGH
**Discovered in:** модуль балансировки серий (остатки + резервы к отгрузке)

```bsl
// ❌ BAD: table alias = field alias → "Неоднозначное поле КОтгрузке.Номенклатура"
"ЛЕВОЕ СОЕДИНЕНИЕ (ВЫБРАТЬ
|    Резервы.Номенклатура КАК Номенклатура,
|    СУММА(Резервы.КОтгрузкеОстаток) КАК КОтгрузке
|ИЗ ... ) КАК КОтгрузке
|ПО Остатки.Номенклатура = КОтгрузке.Номенклатура"

// ❌ BAD: alias collides with query language type name
"Обороты.Регистратор КАК Документ"

// ✅ GOOD: distinct table alias, field alias, output alias
"ПОМЕСТИТЬ ВТ_РезервыКОтгрузке ... КАК КОтгрузкеОстаток;
|ЛЕВОЕ СОЕДИНЕНИЕ ВТ_РезервыКОтгрузке КАК РезервыКОтгрузке
|ПО Остатки.Номенклатура = РезервыКОтгрузке.Номенклатура"

// ✅ GOOD: safe registrar alias
"Обороты.Регистратор КАК ДокументРегистратор"
```

**Rule:** in JOIN/`ПО`/`ИМЕЮЩИЕ` — table alias ≠ field alias; avoid `Документ`/`Справочник` as aliases.

### 5. Virtual Table Filter in WHERE

**Impact:** Full table scan instead of index usage
**Severity:** HIGH

```bsl
// ❌ HIGH: Filter after virtual table calculation
"ВЫБРАТЬ
|   Остатки.Номенклатура КАК Номенклатура,
|   Остатки.КоличествоОстаток КАК Остаток
|ИЗ
|   РегистрНакопления.ТоварыНаСкладах.Остатки() КАК Остатки
|ГДЕ
|   Остатки.Склад = &Склад"

// ✅ OPTIMIZED: Filter in virtual table parameters
"ВЫБРАТЬ
|   Остатки.Номенклатура КАК Номенклатура,
|   Остатки.КоличествоОстаток КАК Остаток
|ИЗ
|   РегистрНакопления.ТоварыНаСкладах.Остатки(, Склад = &Склад) КАК Остатки"
```

### 6. Missing ПЕРВЫЕ N

**Impact:** Loads all records when only subset needed
**Severity:** HIGH

```bsl
// ❌ HIGH: Loads all records
"ВЫБРАТЬ
|   Контрагенты.Ссылка КАК Ссылка
|ИЗ
|   Справочник.Контрагенты КАК Контрагенты"

// ✅ OPTIMIZED: Limit at query level
"ВЫБРАТЬ ПЕРВЫЕ 10
|   Контрагенты.Ссылка КАК Ссылка
|ИЗ
|   Справочник.Контрагенты КАК Контрагенты"
```

### 7. Excessive Client-Server Calls

**Impact:** Network overhead, context serialization
**Severity:** HIGH

```bsl
// ❌ HIGH: Multiple server calls
&НаКлиенте
Процедура Обработать(Команда)
    Данные1 = ПолучитьДанные1НаСервере();
    Данные2 = ПолучитьДанные2НаСервере();
    Данные3 = ПолучитьДанные3НаСервере();
КонецПроцедуры

// ✅ OPTIMIZED: Single server call
&НаКлиенте
Процедура Обработать(Команда)
    ВсеДанные = ПолучитьВсеДанныеНаСервере();
КонецПроцедуры

&НаСервереБезКонтекста
Функция ПолучитьВсеДанныеНаСервере()
    Результат = Новый Структура;
    Результат.Вставить("Данные1", ПолучитьДанные1());
    Результат.Вставить("Данные2", ПолучитьДанные2());
    Результат.Вставить("Данные3", ПолучитьДанные3());
    Возврат Результат;
КонецФункции
```

### 8. Using &НаСервере Instead of &НаСервереБезКонтекста

**Impact:** Unnecessary form context transfer
**Severity:** HIGH

```bsl
// ❌ HIGH: Transfers full form context
&НаСервере
Функция ПолучитьДанныеНаСервере()
    Возврат ВыполнитьЗапрос();
КонецФункции

// ✅ OPTIMIZED: No context transfer
&НаСервереБезКонтекста
Функция ПолучитьДанныеНаСервере(Параметры)
    Возврат ВыполнитьЗапрос(Параметры);
КонецФункции
```

## Medium Priority Anti-Patterns

### 9. Missing Caching

**Impact:** Repeated expensive operations
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: Same calculation repeated
Для Каждого Строка Из ТаблицаДанных Цикл
    Курс = ПолучитьКурсВалюты(Строка.Валюта, Строка.Дата);
КонецЦикла;

// ✅ OPTIMIZED: Cache results
КэшКурсов = Новый Соответствие;

Для Каждого Строка Из ТаблицаДанных Цикл
    
    Ключ = Строка.Валюта + "|" + Формат(Строка.Дата, "ДФ=yyyyMMdd");
    Курс = КэшКурсов.Получить(Ключ);
    
    Если Курс = Неопределено Тогда
        Курс = ПолучитьКурсВалюты(Строка.Валюта, Строка.Дата);
        КэшКурсов.Вставить(Ключ, Курс);
    КонецЕсли;
    
КонецЦикла;
```

### 10. O(n²) Algorithm

**Impact:** Exponential performance degradation
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: O(n²) nested loop search
Для Каждого Строка1 Из Таблица1 Цикл
    Для Каждого Строка2 Из Таблица2 Цикл
        Если Строка1.Ключ = Строка2.Ключ Тогда
            // Process match
        КонецЕсли;
    КонецЦикла;
КонецЦикла;

// ✅ OPTIMIZED: O(n) with Map lookup
ИндексТаблицы2 = Новый Соответствие;
Для Каждого Строка2 Из Таблица2 Цикл
    ИндексТаблицы2.Вставить(Строка2.Ключ, Строка2);
КонецЦикла;

Для Каждого Строка1 Из Таблица1 Цикл
    Строка2 = ИндексТаблицы2.Получить(Строка1.Ключ);
    Если Строка2 <> Неопределено Тогда
        // Process match
    КонецЕсли;
КонецЦикла;
```

### 11. Deep Nesting

**Impact:** Poor readability, hard to maintain
**Severity:** MEDIUM

```bsl
// ❌ MEDIUM: Deep nesting (>4 levels)
Если Условие1 Тогда
    Если Условие2 Тогда
        Если Условие3 Тогда
            Если Условие4 Тогда
                // Logic
            КонецЕсли;
        КонецЕсли;
    КонецЕсли;
КонецЕсли;

// ✅ OPTIMIZED: Early returns
Если НЕ Условие1 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие2 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие3 Тогда
    Возврат;
КонецЕсли;

Если НЕ Условие4 Тогда
    Возврат;
КонецЕсли;

// Logic
```

## Query constructs that cost a plan

Six constructs that compile and return correct data, and cost an index or a
join while doing it. Sourced from the ITS optimization standards — the
mechanism is stated so the rule can be applied to a case that does not look
exactly like the example; the numbers are not ours and no measurement here
claims otherwise.

### 12. Dot access on a composite-type field

`Регистратор.Дата` on a register makes the optimizer join **every** document
type the field can hold. Name the type with `ВЫРАЗИТЬ`; for several types, a
`ВЫБОР … КОГДА … ССЫЛКА …` over the two or three that actually occur.

```bsl
// Bad — joins all registrator types
ТоварыНаСкладах.Регистратор.Дата
// Good
ВЫРАЗИТЬ(ТоварыНаСкладах.Регистратор КАК Документ.ПоступлениеТоваровУслуг).Дата
```

### 13. `.Наименование` where a presentation is enough

`Склад.Наименование` adds a join to the catalog. If the value is only shown,
`ПРЕДСТАВЛЕНИЕ(Склад)` returns the presentation without it.

### 14. Subquery inside a join

A subquery in `СОЕДИНЕНИЕ (…)` has no index. Materialise it into a temporary
table **with `ИНДЕКСИРОВАТЬ ПО` on the join key** — the temp table without the
index buys much less than it looks.

### 15. Joining a virtual table directly

`ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.X.Остатки(&Дата,)` joins against a
computed result. Put the virtual table into a temp table first, index it by
the join key, then join. (Filtering *inside* the virtual table's parameters
rather than in `ГДЕ` is a separate rule — §5 above.)

### 16. `ИЛИ` in `ГДЕ`

`ИЛИ` across different fields blocks index use. Split into separate queries
joined by `ОБЪЕДИНИТЬ ВСЕ`, each with its own indexable condition.

### 17. `ОБЪЕДИНИТЬ` where duplicates cannot occur

`ОБЪЕДИНИТЬ` adds a grouping pass to remove duplicates. When the parts cannot
overlap — different documents, disjoint periods — `ОБЪЕДИНИТЬ ВСЕ` skips it.
This is the single cheapest edit on the list; it is also the one most often
left as-is out of habit.

## Optimized Patterns

### Batch Query with Temp Table

```bsl
МенеджерВТ = Новый МенеджерВременныхТаблиц;

Запрос = Новый Запрос;
Запрос.МенеджерВременныхТаблиц = МенеджерВТ;

// Step 1: Create temp table with input data
Запрос.Текст =
"ВЫБРАТЬ
|   Данные.Номенклатура КАК Номенклатура,
|   Данные.Склад КАК Склад
|ПОМЕСТИТЬ ВТ_Входные
|ИЗ
|   &ТаблицаДанных КАК Данные";
Запрос.УстановитьПараметр("ТаблицаДанных", ТаблицаДанных);
Запрос.Выполнить();

// Step 2: Join with register for batch result
Запрос.Текст =
"ВЫБРАТЬ
|   ВТ_Входные.Номенклатура КАК Номенклатура,
|   ВТ_Входные.Склад КАК Склад,
|   ЕСТЬNULL(Остатки.КоличествоОстаток, 0) КАК Остаток
|ИЗ
|   ВТ_Входные КАК ВТ_Входные
|       ЛЕВОЕ СОЕДИНЕНИЕ РегистрНакопления.ТоварыНаСкладах.Остатки(
|           ,
|           (Номенклатура, Склад) В
|               (ВЫБРАТЬ ВТ.Номенклатура, ВТ.Склад ИЗ ВТ_Входные КАК ВТ)
|       ) КАК Остатки
|       ПО ВТ_Входные.Номенклатура = Остатки.Номенклатура
|           И ВТ_Входные.Склад = Остатки.Склад";
РезультатЗапроса = Запрос.Выполнить();
```

### Bulk SSL Attribute Access

```bsl
// Instead of individual calls in loop
СписокКонтрагентов = ТаблицаДанных.ВыгрузитьКолонку("Контрагент");

// Get all attributes in single call
ТаблицаРеквизитов = ОбщегоНазначения.ЗначенияРеквизитовОбъектов(
    СписокКонтрагентов, "ИНН, КПП, Наименование");

// Build lookup map
СоответствиеРеквизитов = Новый Соответствие;
Для Каждого СтрокаРеквизитов Из ТаблицаРеквизитов Цикл
    СоответствиеРеквизитов.Вставить(
        СтрокаРеквизитов.Ссылка, СтрокаРеквизитов);
КонецЦикла;
```

## Where the neighbours are

| Concern | File |
|---|---|
| Shape-level smells over a module / subsystem | `dev-standards-architecture.md §6` |
| Scoring findings when reporting a review | the `code-reviewer` / `arch-reviewer` roles |
| Authoritative query rules | `dev-standards-architecture.md §3` |
| Report-side query traps | `dcs-design.md`, `dcs-composition-recipes.md` |
