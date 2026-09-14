---
description: "Development standards — project parameters, code style, modification comments, naming, documentation headers. Триггеры: как оформлять код, комментарии модификации, правка типовой конфигурации, именование объектов, шапка процедуры."
alwaysApply: false
kind: invariant
---

# Development Standards — Core

## 1. Project Parameters (.dev.env)

**Before starting any code task**, read the `.dev.env` file from the project root. If it does not exist — **stop and request parameters from the user**. Guessing values is PROHIBITED.

Parameters and their effect on code generation:

| Parameter | Effect |
|---|---|
| `{PREFIX}` | Prefix for ALL new metadata objects, attributes, form elements, roles |
| `{COMPANY}` | Used in modification comment templates |
| `{DEVELOPER}` | Used in modification comment templates |
| `{PLATFORM_VERSION}` | Determines available platform features (e.g. `Асинх` / `Ждать` from 8.3.18 vs `ОписаниеОповещения` callbacks for older versions). See `rules/dev-standards-architecture.md §3 "Async and Modality"` |
| `{COMMENT_OPEN}` | Opening modification comment template with placeholders `{COMPANY}`, `{DEVELOPER}`, `{DATE}`, `{TASK}` |
| `{COMMENT_CLOSE}` | Closing modification comment template |
| `{NEW_OBJECTS_IN}` | Where to place new objects: `main_configuration` (default) or `extension` |

Task number `{TASK}` is **only required when modification comment markers are produced** — i.e. when the change touches **typical (standard) configuration code** and the templates `{COMMENT_OPEN}` / `{COMMENT_CLOSE}` reference `{TASK}`. For new objects with `{PREFIX}` (no per-method markers) and for review / analysis / documentation tasks `{TASK}` is **not required** — do not block on it.

When `{TASK}` is required and not provided — ask the user once and reuse the same value across the whole change.

> For tasks without code generation (review, analysis, documentation) — parameters are not blocking.

See `.dev.env.example` in the project root for the template (installed from
the overlay). `PREFIX` and `PLATFORM_VERSION` must match the Project section
of the root contract (`AGENTS.md`) — on mismatch, ask the
user which source is current instead of picking one silently.

## 2. Code Style (single source of truth — referenced from `AGENTS.md`)

Applies to every module. Region layout and the rules specific to form modules —
`rules/dev-standards-forms.md`.

### Formatting
- **Indentation:** TAB only (not spaces).
- **Line length:** ≤ 120 characters when the line can be wrapped correctly. Don't introduce a line break that leaves a single variable on a new line.
- **One statement per line.** Single-line constructs with complex logic are prohibited.
- In conditions and loops, add blank lines before and after the code inside the block for better readability.
- Follow linter / BSL Language Server recommendations. Use `//BSLLS:` comments for targeted, justified suppressions.

### Alignment
- For groups of similar assignments **into local variables** — align `=` with spaces.
- **DO NOT** align when setting object properties via dot notation — use single space around `=`.

### Quality Metrics

| Metric | Limit | Strictness |
|---|---|---|
| Method length | ≤ 200 lines (exception: query texts) | hard limit |
| Method length | > 100 lines — candidate for decomposition | review trigger |
| Control structure nesting | < 5 levels | hard limit |
| Cognitive complexity | < 15 | review trigger |
| Method parameters | ≤ 5 (additional via Structure as 6th) | hard limit |

### String Building
Use `СтрШаблон()` for composing strings, **NOT** concatenation via `+`.
Exception: simple `Prefix + Suffix` is acceptable when it reads better.

### Forbidden Calls and Constructs

- `Попытка ... Исключение` around DB reads/writes is **PROHIBITED**, except for explicit, well-justified transaction control.
- `ЗаписьЖурналаРегистрации()` is **PROHIBITED** unless explicitly requested by the task.
- `Сообщить()` for user notifications is **PROHIBITED**. Use `ОбщегоНазначения.СообщитьПользователю` (server) / `ОбщегоНазначенияКлиент.СообщитьПользователю` (client).
- `Выполнить()` and `Вычислить()` are **PROHIBITED** without extreme necessity (see `rules/dev-standards-architecture.md §3`).
- Hardcoded credentials (passwords, tokens, API keys) in code are **PROHIBITED**.
- `?(Условие, Значение1, Значение2)` ternary operator is **PROHIBITED in any form**, including the simple non-nested case. Use `Если ... Иначе` or extract a small helper function. Rationale: keeps logic visible in step-debugger and code review. **[Project rule — stricter than ITS standard.]**
- Boolean comparisons against `Истина` / `Ложь` are forbidden — use the boolean expression directly.
- Yoda syntax (`Если 0 = Сумма`) is **PROHIBITED**.

### Naming

- **Variable names MUST reflect business meaning and role.** Type suffixes are allowed only when they remove ambiguity and do not turn into Hungarian notation.
- Hungarian notation (`МассивКонтрагентов`, `ТаблицаДанных`) is **PROHIBITED** — use the business name (`Контрагенты`, `Данные`).
- Names from the 1C global context (`Документы`, `Справочники`, `Пользователи`, `Регистры`, `Метаданные`, `Константы`, etc.) MUST NOT be used as local variables — they cause name collisions and reduce readability.
- The `Получить*` prefix in function names is discouraged when the return value is obvious from the name or when the function returns a collection (`Контрагенты()` over `ПолучитьКонтрагентов()`). Acceptable when delegating directly to a platform call or implementing a БСП-compatible API contract.
- **Boolean variables — positive names only** (`ПроверкаПройдена`, not `ПроверкаНеПройдена`).
- **"Magic numbers" are PROHIBITED** — extract into named variables/constants.
- **String value enumerations** — in alphabetical order.

### Conditions
- Complex conditions (3+ constructs) — extract into a separate method.

### Function Parameters
- Function parameter MUST NOT be used as additional output — all output via return value.
- For additional parameters — use constructor function pattern:

```bsl
Функция ПараметрыЗаполнения() Экспорт
	Параметры = Новый Структура;
	Параметры.Вставить("Дата");
	Параметры.Вставить("Валюта");
	Параметры.Вставить("ПересчитыватьСумму", Истина);
	Возврат Параметры;
КонецФункции
```

## 3. Modification Comments

Modification markers are used **only when modifying typical (standard) code** in typical configuration modules.

### Format
- Opening comment: value of `{COMMENT_OPEN}` from `.dev.env`
- Closing comment: value of `{COMMENT_CLOSE}` from `.dev.env`
- A space is mandatory after `//`
- **Verify the actual marker against already-marked edits in this very
  configuration** before writing the first one. The prefix is a team
  convention, not a platform rule, and it differs between projects. If what
  you find on the spot disagrees with `.dev.env` — ask, do not impose either.
  Markers are merge metadata, not a journal: no task numbers, dates or authors
  inside them, that is what version control is for (the `TODO` reference below
  is a different thing).

### Typical Code Modification
Removed typical code — **comment out, DO NOT delete**:

```bsl
// {COMMENT_OPEN}
НовоеЗначение = {PREFIX}ПреобразоватьЗначение(Значение1);
// ТиповаяПроцедура(Значение1, Значение2);
ТиповаяПроцедура(НовоеЗначение, Значение2);
// {COMMENT_CLOSE}
```

### New Procedures in Typical Modules
Comment is placed **inside** the procedure, after the header:

```bsl
Функция НоваяФункция(Параметр) Экспорт
	// {COMMENT_OPEN}
	// ... code ...
	Возврат Результат;
	// {COMMENT_CLOSE}
КонецФункции
```

### Entirely New (Non-Typical) Objects
In modules of new objects (with `{PREFIX}`) — markers per method are **NOT NEEDED**. Instead — **a single block at the module header** describing the object.

### Editing someone else's query

When adding a condition to an existing query, keep the shape the original
author chose. If the query is one string literal, the new lines go **inside**
that literal — do not introduce `+ "..."` concatenation that was not there.
Keep the `|` indentation and keyword positions as they are.

The reason is the diff: a change of literal structure rewrites lines that carry
no change in meaning, and the reviewer can no longer see what actually happened.
If the original already concatenates — continue in that style.

### Refactoring edits — where the explanation lives

For refactoring and performance edits of existing code the explanatory ballast
must **not** stay at the change sites: a marker pair plus `Было/Стало` prose at
every site makes the procedure unreadable. Canonical layout:

**At each change site** — the marker pair and the working code, nothing else:

```bsl
// {COMMENT_OPEN}
НовыйКод();
// {COMMENT_CLOSE}
```

No `Было/Стало` lines and no commented-out original at the site.

**All explanations and the commented-out original** go into one collapsible block
at the top of the modified procedure, wrapped in a real region (pseudo-regions
are prohibited — see "General Rules" below):

```bsl
Процедура Имя(...)

	#Область ОписаниеИзменений_<TaskId>
	// {COMMENT_OPEN}
	// <what the edit does, one line>
	// Change sites in the body carry markers without explanations — the
	// explanations and the original code are collected here.
	// 1. <what it was> → <what it became>.
	//    Было: <the original line verbatim, with its indentation>
	// 2. ...
	// {COMMENT_CLOSE}
	#КонецОбласти
```

- The region name must be a valid identifier (`-` → `_`); the task id lives
  there, not inside the markers (markers stay free of dates, authors and task
  numbers — see "Format" above). One region per procedure per task id; numbered
  points inside it cover several sites in that procedure.
- The "comment out, DO NOT delete" rule is satisfied by the `Было:` lines of the
  header block — the original text is preserved verbatim, in one place instead of
  scattered across the body.
- For an entirely new procedure added by the refactoring the markers still wrap
  the whole body, and its explanation block goes into the same kind of region
  right after the header.

### General Rules
- `TODO` / `FIXME` must contain a task reference: `// TODO No.14752: description`
- **Pseudo-regions via comments are PROHIBITED** — use only `#Область` / `#КонецОбласти`

## 4. Metadata Naming

| Element | Rule |
|---|---|
| New metadata objects | Prefix `{PREFIX}` in name (e.g., `{PREFIX}ContractAmount`) |
| Object synonyms | No prefix. If conflicts — add `({COMPANY})` |
| New roles | Prefix `{PREFIX}` |
| Subsystems | `{PREFIX}AddedObjects` and `{PREFIX}ModifiedObjects` |
| Attributes of typical objects | Prefix `{PREFIX}` |
| Form elements on typical forms | Prefix `{PREFIX}` |

**Inside non-typical (new) objects** (name already has `{PREFIX}`):
- Attributes, tabular sections, form elements, commands, procedures — **WITHOUT prefix**

- Place all new objects into subsystems
- Composite types used repeatedly — via `DefinedType`

**The `Удалить` prefix means "already dead".** Objects and attributes named
`УдалитьКонтрагент`, `УдалитьАдрес` and the like are retired stubs kept for
backward compatibility. Treat them as non-existent: do not read, write,
reference or extend them in new code, and never pick one as the target of a
new field. Look for the current object without the prefix; if only the
prefixed one exists, that is a question for the analyst, not a naming choice.

### Object Type Selection

| Task | Object Type |
|---|---|
| Reference data | `Catalog` |
| Business transactions | `Document` |
| Quantity/amount accumulation | `AccumulationRegister` |
| Arbitrary data with dimensions | `InformationRegister` |
| User reports | `Report` (with DCS) |
| Data processing | `DataProcessor` |
| Fixed set of values | `Enum` |

## 5. Procedure/Function Documentation

Mandatory for all `Экспорт` procedures/functions (except predefined handlers):

```bsl
// Возвращает спецодежду для должности на указанную дату.
//
// Параметры:
//  ДатаДействия - Дата
//  Должность - СправочникСсылка.Должности
//
// Возвращаемое значение:
//  СправочникСсылка.{PREFIX}СпецодеждаДляДолжностей
//
Функция АктуальнаяСпецодеждаДляДолжности(ДатаДействия, Должность) Экспорт
```

- Description starts with a verb: "Возвращает...", "Проверяет...", "Рассчитывает..."
- DO NOT start with "Процедура...", "Функция..." or the function name
- For structure parameters — describe keys via `*`
- For arrays — specify element type

## 6. Typography

These rules apply only to 1C code artifacts: modules, in-module comments, identifiers, string literals, metadata synonyms / presentations and user-facing messages. Project markdown files and rule documentation are out of scope.

- **Do not use the letter «ё»** in 1C code and user-facing configuration text. Replace it with «е» in module comments, metadata synonyms, presentations and user messages. Rationale: keyboard-layout drift across the team and in baseline configurations breaks text search.
- **Do not use the em-dash** `—`. Replace it with a hyphen `-`. Rationale: encoding mismatches in the 1C toolchain (especially in event log and platform logs) turn the em-dash into `?`.
- For user-facing text use guillemet quotes `«...»`. In code string literals — standard `"..."`.
- Do not use non-breaking spaces or other invisible Unicode characters in code.

## 7. Comments — OK / NOT OK Examples

Goal: cut LLM noise and keep only useful comments. This section is the authoritative comment rule for generated project code.

### NOT OK — code paraphrase and noise

```bsl
// Получаем массив контрагентов
Контрагенты = ПолучитьКонтрагентов();

// Цикл по строкам таблицы
Для Каждого Строка Из Таблица Цикл

// Возвращаем результат
Возврат Результат;
```

```bsl
//////////////////////////////////////////////////////////////////
// Модуль: ОбщегоНазначения
// Автор: Иванов И.И.
// Дата: 15.03.2024
// Описание: Общие функции
// История изменений:
//   15.03.2024 — добавлено
//   17.03.2024 — исправлено
//////////////////////////////////////////////////////////////////
```

Decorative `///` banners and module headers with authorship / change history are forbidden — git already tracks that information.

### OK — motivation, context, constraints

```bsl
// НДС не начисляется при экспорте, см. ст. 164 НК РФ
Если Контрагент.Резидент И Не Документ.Экспорт Тогда

// Кеш используется потому, что метод вызывается ~10000 раз при проведении
// крупных накладных и каждый вызов делает запрос к регистру цен.
ИндексЦен = Новый Соответствие;

// Хак: платформа 8.3.23 не возвращает корректный тип в РазделительИБ
// при первом вызове после старта сеанса - повторяем запрос один раз.
Тип = Метаданные.ОбщиеРеквизиты.РазделительИБ.Тип;
Если Тип.Типы().Количество() = 0 Тогда
    Тип = Метаданные.ОбщиеРеквизиты.РазделительИБ.Тип;
КонецЕсли;

// TODO No.14752: после миграции на платформу 8.3.25 убрать обходной путь.
```

### Verification rule

Before keeping a comment, answer: **"What does this comment tell the reader that the code itself does not?"** If the answer is "nothing" — delete the comment.

## 8. Platform names are verified, not recalled

Property names, enum members and manager methods of the platform are checked
against the syntax reference **before** a deploy cycle, not after. The
compiler does not catch an invented name: it fails at run time, on the
contour, and each round trip costs a full deploy.

This is not a style preference — it is the observed cost. A single session
burned three deploy cycles on plausible-looking names; the real ones differed
in ways no amount of recall would have produced.

The same applies to metadata of a system being integrated with: names of
objects, attributes and types are confirmed against the actual structure of
**both** sides, never assumed from the other one.

## 9. Checking your own work

No separate self-checking pass sits on top of the gates. What a change must
pass, and in what order, is `rules/verification-matrix.md`: syntax, then
logic and performance, then style and standards — each with its own pass
criterion and a bounded retry budget. Instructing a re-read of your own output
on top of that buys nothing and costs a pass; the instrumental gates are the bar.

The one thing worth carrying at the moment of writing rather than at the gate:
before opening a transaction, consider whether an outer one is already open
(an object write, for instance). Templates — `rules/platform-solutions.md`.
