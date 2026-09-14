---
description: "Entry point for managed-form work — pick the exact companion rules for `Form.xml`, `Form.Module.bsl`, events, async code, reserved names, and XML validation. Load first for any form task; load companions only via the routing table below. Триггеры: работа с формой, с чего начать по форме, какое правило про формы."
alwaysApply: false
kind: router
---

# Managed Forms — Entry Point

This file is the **router** for managed-form work. Load it first, then load only the companion rules selected by the table below — companion files are not auto-attached by file pattern.

## Routing

| Task | Load |
|---|---|
| Create or structurally modify `Form.xml` | `rules/forms-add.md`, `rules/metadata-xml-workarounds.md` |
| Add or rename form event handlers | `rules/forms-events-add.md`, `rules/form-module.md` |
| Edit `Form.Module.bsl` logic | `rules/form-module.md` |
| Set up module regions in a new form module | `dev-standards-forms.md` (form-module template with 5 mandatory regions) |
| Server-side form-module code (reserved names) | `rules/form-reserved-names.md` |
| Client-server architecture (directives, round trips) | `dev-standards-architecture.md §3 → "Client-Server Interaction"`, `anti-patterns.md → "Excessive Client-Server Calls"`, `anti-patterns.md → "Using &НаСервере Instead of &НаСервереБезКонтекста"` |
| Client-side async code (`Асинх` / `Ждать`) | `rules/async-methods.md` |
| Programmatic modification of typical forms (element placement, fill checking, form commands) | `dev-standards-forms.md` |
| Working on an adopted form of an extension | `extension-patterns.md`, `dev-standards-architecture.md §2` |

Each companion file is self-contained — load only the ones that match the task. Do not preload the whole set "to be safe".
