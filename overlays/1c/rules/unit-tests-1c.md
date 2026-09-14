---
description: "Writing unit tests for 1C code with YaXUnit — when a unit test is the right channel at all, test naming, the Arrange / Act / Assert shape, and the boundary with scenario runs. Load when asked to cover a routine with tests, or when deciding between a unit test and a scenario. Триггеры: юнит-тест, покрыть тестами функцию, YaXUnit, ЮТест, модульный тест, какой тест писать."
alwaysApply: false
kind: recipe
---

# Unit tests for 1C code (YaXUnit)

What makes a test worth keeping at all — seams agreed in advance, vertical
red-green slices, no tautological or implementation-coupled assertions — is
`rules/test-discipline.md`, and it applies here unchanged. This file is only
about the 1C-specific shape.

## Before writing one

- **Only if the project already runs YaXUnit.** Introducing a test framework
  is a decision with its own infrastructure cost, not a side effect of a
  change. No framework in the project — say so and offer it as a separate
  piece of work.
- **Pick the channel deliberately.** A unit test earns its place on logic that
  can be exercised without the platform's data layer: computation, parsing,
  transformation, branching. Everything whose value is "the document posted and
  the register moved as expected" belongs in a scenario run instead — the
  tester role's channel order in the agent definition covers that. Writing a
  unit test that stands up a document, writes it and reads the register back is
  a scenario test wearing the wrong hat: slower, more brittle, and it fails for
  reasons that have nothing to do with the logic it claims to check.
- Pure logic is far cheaper to test after it has been pulled into
  `*КлиентСервер` functions — parameters in, value out, no data access
  (`clean-architecture-1c.md`). If the routine cannot be tested without a
  database, that is usually a statement about the routine, not about testing.

## Shape

```bsl
Процедура Тест<ИмяФункции>_<Сценарий>() Экспорт

    // Arrange
    <входные данные>

    // Act
    Результат = <вызов проверяемой функции>;

    // Assert
    ЮТест.ОжидаетЧто(Результат).<проверка>;

КонецПроцедуры
```

Three blocks, in that order, one behaviour per test. A test that acts twice is
two tests; a test that asserts on something it did not act on is a leftover.

## Naming

`Тест<Функция>_<Сценарий>` — the scenario half is what the reader needs, so it
carries the case rather than a number: `СуществующийОбъект`,
`НесуществующийОбъект`, `НеверныйПараметр`, `ПустоеЗначение`,
`ГраничноеУсловие`. `Тест1` / `Тест2` names a position in a file, which
changes when someone inserts a test above.

The boundary case deserves its own test rather than an extra assertion inside
the main one: when it breaks, the name should say what broke.

## Companion rules

| Concern | File |
|---|---|
| What makes a test worth keeping | `test-discipline.md` |
| Extracting pure logic that can be tested at all | `clean-architecture-1c.md` |
| Scenario runs, deployment, verification channels | the `tester` role and the stack's test contour |
