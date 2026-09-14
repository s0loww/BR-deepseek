---
description: "Two composition recipes for when the standard DCS output does not fit: running the layout's query directly (report eats memory on large volumes, or a flat result is needed), and two-pass preprocessing of detail records before the engine folds them into groupings (hiding rows/columns whose folded total is zero). Триггеры: отчёт съедает память, большой отчёт, плоская выгрузка, скрыть нулевые строки, предобработка до свёртки, двухпроходный отчёт."
alwaysApply: false
kind: recipe
---

# Composition recipes — going around the standard DCS output

Both recipes below give up part of what the engine does for free. Reach for
them only when the standard path (`ПроцессорВыводаРезультатаКомпоновкиДанныхВТабличныйДокумент`,
see `dcs-design.md §5`) genuinely cannot do the job — user groupings,
conditional appearance, drill-down and engine totals exist only there.

> **Provenance.** Transferred from external practice (MIT-licensed community
> material), restructured. The structure is sound, but the exact property names
> of the composition objects vary between platform versions — verify the first
> run in the debugger rather than trusting the snippets literally. Both recipes
> fail loudly (an exception at layout compile time), not silently.

## 1. Running the layout's query directly

**When.** The engine holds every intermediate row of the composition in memory,
so a large report can exhaust it long before the output is built. Use this when
you need the raw result as a flat table, or an alternative export next to the
standard "Сформировать" button.

**When not.** Any report whose value is in groupings, appearance or drill-down.
A flat run reproduces the data, not the presentation.

```bsl
// 1. Executable layout. Take the schema as an independent copy from metadata,
//    not through the object's attribute — safer for side effects.
СхемаКомпоновки = ОбъектОтчет.ПолучитьМакет("ОсновнаяСхемаКомпоновкиДанных");

КомпоновщикМакета = Новый КомпоновщикМакетаКомпоновкиДанных;
МакетКомпоновки = КомпоновщикМакета.Выполнить(
    СхемаКомпоновки, Настройки, , ,
    Тип("ГенераторМакетаКомпоновкиДанныхДляКоллекцииЗначений"));

// 2. Query text of the data set. The property is platform-dependent: it can be
//    a string or an object carrying `.Текст`.
ОбъектЗапроса = МакетКомпоновки.НаборыДанных.НаборДанных1.Запрос;
Если ТипЗнч(ОбъектЗапроса) = Тип("Строка") Тогда
    ТекстЗапроса = ОбъектЗапроса;
Иначе
    ТекстЗапроса = ОбъектЗапроса.Текст;
КонецЕсли;

// 3. Parameters come from the COMPILED layout — settings are already folded in.
Запрос = Новый Запрос(ТекстЗапроса);
Для Каждого ЗначениеПараметра Из МакетКомпоновки.ЗначенияПараметров Цикл
    Запрос.УстановитьПараметр(ЗначениеПараметра.Имя, ЗначениеПараметра.Значение);
КонецЦикла;

// 4. Stream the result. `Выгрузить()` puts the whole set back in memory and
//    defeats the purpose of the recipe.
Выборка = Запрос.Выполнить().Выбрать();
Пока Выборка.Следующий() Цикл
    // fill the output area, accumulate totals
КонецЦикла;
```

**Two sources of query and parameters** — pick deliberately:

| Source | What you get | Use when |
|---|---|---|
| Schema (`СхемаКомпоновки.НаборыДанных...Запрос` + `Схема.Параметры`) | Raw query text; parameters set by hand from the settings | Simple reports without complex groupings |
| Compiled layout (`МакетКомпоновки...Запрос` + `МакетКомпоновки.ЗначенияПараметров`) | Query with the settings' filters already embedded; every parameter value collected automatically | Everything else |

**Traps.**

- **Server code belongs in the form module**, not in a common server module:
  only there is `РеквизитФормыВЗначение("Отчет")` available to get the report
  object on the server. Across the client-server boundary pass only
  serializable data (settings serialize, the form does not); return the result
  through temporary storage.
- **Do not name a local variable `НастройкиОтчета`** — it is an attribute of the
  standard report form, and overwriting it breaks `СвойстваРезультата`, so a
  click on the resulting document fails. Same class as
  `form-reserved-names.md`.
- **External data sets** are not wired up automatically when the query runs
  directly — load them into a temporary table under the name the query uses,
  through `Запрос.МенеджерВременныхТаблиц`.
- **Post-processing done by the configuration** on the compiled layout is lost
  if you take the raw query from the schema instead of the compiled layout.
- The output document itself still grows with the row count — for very large
  volumes output in chunks.
- When reconciling against the standard run, compare **data and resource
  totals only**, never the visual result.

## 2. Two-pass preprocessing before the fold

**When.** Detail records must be filtered or transformed *before* the engine
folds them into groupings. The canonical case: a cross-tab where a row or
column folds to zero (Jan −1200 plus Mar +1200) — the cell is empty but the
grouping frame stays. A query, `ИМЕЮЩИЕ` or a filter cannot express it, because
folding happens after grouping.

**Cheaper alternative first.** Post-processing the output document with
`Видимость = Ложь` is far simpler. It also hides grouping headers and leaves
traces — if you can live with that, stop here and do not use this recipe.

**Shape.** Both passes run inside `ПриКомпоновкеРезультата` with
`СтандартнаяОбработка = Ложь`:

1. **Pass 1 — get a flat detail table.** A cross-tab cannot be output into a
   collection, so build **flat** settings (detail records, all fields) and
   output through `ГенераторМакетаКомпоновкиДанныхДляКоллекцииЗначений` +
   `ПроцессорВыводаРезультатаКомпоновкиДанныхВКоллекциюЗначений` into a
   `ТаблицаЗначений`.
2. **Process the table** — drop or transform rows.
3. **Pass 2 — output the cross-tab.** The output schema must **stay
   query-based**; substitute the data set at runtime, on the already compiled
   layout.

```bsl
// Runtime substitution of the data set in the COMPILED layout.
СтарыйНабор = Макет.НаборыДанных[0];
НовыйНабор  = Макет.НаборыДанных.Добавить(Тип("НаборДанныхОбъектМакетаКомпоновкиДанных"));
НовыйНабор.ИмяОбъекта    = "Результат";
НовыйНабор.Имя           = СтарыйНабор.Имя;
НовыйНабор.ИсточникДанных = СтарыйНабор.ИсточникДанных;
Для Каждого Поле Из СтарыйНабор.Поля Цикл
    ЗаполнитьЗначенияСвойств(НовыйНабор.Поля.Добавить(), Поле);
КонецЦикла;
ЗаполнитьЗначенияСвойств(НовыйНабор, СтарыйНабор);
Макет.НаборыДанных.Удалить(СтарыйНабор);

ПроцессорКомпоновки.Инициализировать(
    Макет, Новый Структура("Результат", ТаблицаДеталей), Расшифровка, Истина);
```

**Why runtime and not in the schema file.** Converting the output data set to
`Объект` **in the schema** kills reference navigation: the object's fields are
untyped, and `КомпоновщикМакета.Выполнить` fails with "Поле не найдено" at
**compile time**, before any data is touched. On the compiled layout the types
are already resolved from the query, so the substitution is safe.

**Traps.**

- **Derived parameters** of the schema (`НачалоПериода = &Период.ДатаНачала`,
  `ТекущаяДата = ТекущаяДатаСеанса()`) are **not parsed** by the collection
  generator — `Инициализировать` fails with a syntax error on the expression.
  Set such parameters to explicit computed values in code.
- **Do not carry the whole parameter set over** from the output settings: the
  output keeps derived parameters as `ВыражениеКомпоновкиДанных`, and they leak
  into pass 1. Take only the period, compute the rest.
- **`ПараметрыДанных.НайтиЗначениеПараметра` expects a
  `ПараметрКомпоновкиДанных`, not a string** — passing a string gives a type
  mismatch. `УстановитьЗначениеПараметра` does accept a string; the asymmetry
  is real, not a typo.
- **Determine resource columns from `Схема.ПоляИтога`, not from the column
  type.** Sums coming out of a query with left joins have a composite
  `Null` + `Число` type, so a strict "is a number" test discards them and the
  report comes out empty.
- **Zero-filter semantics:** drop a detail row only when **all** its resources
  are zero. Partially filled rows stay — otherwise the fold silently changes
  the numbers instead of only hiding empty frames.

## Companion rules

| Concern | File |
|---|---|
| Report design rules, standard programmatic override | `dcs-design.md` |
| Reserved names in form modules | `form-reserved-names.md` |
| Long-running execution of a heavy report | `platform-solutions.md §2` |
| Query anti-patterns | `anti-patterns.md` |
