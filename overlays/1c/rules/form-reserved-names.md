---
description: "Reserved property names in 1C form modules — ban on using standard form-element property names as local variables. Load from `forms.md` whenever editing server-side form-module code. Триггеры: переменная в модуле формы ведёт себя не так, ПараметрыВыбора перезаписывается, СписокВыбора не работает, имя переменной конфликтует."
alwaysApply: false
kind: invariant
---

# Reserved Names in 1C Form Modules

Ban on using names of standard form-element properties as names of local variables in form modules.

Applies to: writing / editing form-module code (`*.bsl` in form context).

---

## Rule

In 1C form modules, local variables **must not** be named after standard form-element properties:

- `ПараметрыВыбора` (ChoiceParameters)
- `СвязиПараметровВыбора` (ChoiceParameterLinks)
- `СписокВыбора` (ChoiceList)
- `ПараметрыОтбора` (Filter)
- `ОтборСтрок` (RowFilter)

The same trap exists one level up — on **form attributes of standard forms**, not
only on element properties. On the standard report form, `НастройкиОтчета` is an
attribute of the form itself: a server method that assigns a local variable of
that name breaks `СвойстваРезультата`, and a click on the resulting document
fails. Before naming a local variable in a module of a *standard* form, check
that the name is not already an attribute of that form.

> The list is based on practical experience and may be incomplete. When a name conflict is suspected — verify in Designer.

## Why

In `&НаСервере` context of a form module the platform may interpret `ПараметрыВыбора = ...` as an attempt to set a form-element property, not to assign a local variable. If the value type does not match the expected one (`ФиксированныйМассив(ПараметрВыбора)`) — runtime error "Несоответствие типов" ("type mismatch").

## How to name

Use concrete, contextual names:

```bsl
// Bad:
ПараметрыВыбора = Новый Массив;

// Good:
ПараметрыВыбораСтатьи = Новый Массив;
ПараметрыВыбораНоменклатуры = Новый Массив;
```
