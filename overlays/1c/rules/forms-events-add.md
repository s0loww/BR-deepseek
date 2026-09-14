---
description: "Wiring a form event handler into the form XML. Load when adding, renaming, or removing an event hook (`OnOpen`, `BeforeWrite`, …) on a 1C managed form. Триггеры: добавить обработчик события формы, ПриОткрытии, ПередЗаписью, обработчик не вызывается, событие не зарегистрировано."
alwaysApply: false
kind: recipe
---

# **IMPORTANT!** — don't forget to add the event hook to the form XML file.
The file is usually named `Form.xml` in the parent directory of the module code.

Event hooks in XML look like:

```xml
<Events>
	<Event name="OnOpen">ПриОткрытии</Event>
	<Event name="BeforeWrite">ПередЗаписью</Event>
	<Event name="OnCreateAtServer">ПриСозданииНаСервере</Event>
</Events>
```

Common form events (this is a **non-exhaustive subset** — the platform exposes dozens of form, item, and table events):

| XML Event Name | Russian Handler Name | Description |
|----------------|----------------------|-------------|
| `OnOpen` | `ПриОткрытии` | Client, when form opens |
| `OnClose` | `ПриЗакрытии` | Client, when form closes |
| `BeforeWrite` | `ПередЗаписью` | Client, before write |
| `AfterWrite` | `ПриЗаписи` | Client, after write |
| `OnCreateAtServer` | `ПриСозданииНаСервере` | Server, form creation |
| `BeforeWriteAtServer` | `ПередЗаписьюНаСервере` | Server, before write |
| `AfterWriteAtServer` | `ПриЗаписиНаСервере` | Server, after write |
| `OnReadAtServer` | `ПриЧтенииНаСервере` | Server, when reading object |

The value inside the `<Event>` tag is the name of the handler procedure in the form module.

## Getting the full event list

For the complete and authoritative list of available events, do **not** rely on this table. Use:

- RLM `parse_form(object, form)` on a similar existing form, or reading the form's XML — every wired-up event is listed under each element with its handler name.
- RLM `search` / `parse_form` across other objects to locate canonical examples that already use the event you need.
- Platform documentation for the specific form-item type: there is no documentation tool in this build — confirm in the Designer's syntax assistant, and mark an event name you could not confirm as unverified.
