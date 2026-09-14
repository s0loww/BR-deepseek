---
description: "Generating or structurally modifying a managed form (`Form.xml`). Load when you need to create a new form or add / rearrange elements, data bindings, or commands on an existing one. Триггеры: создать форму, добавить страницу или группу, правка Form.xml, форма не открывается после правки."
alwaysApply: false
kind: recipe
---

# Use following instructions only if you need to generate or modify 1C form

> **Note**: Form and metadata navigation goes through RLM (`rlm_execute`): `parse_form` for a form's handlers, commands and attributes, `get_object_full_structure` for the metadata it binds to, `search` for similar forms elsewhere — see `tooling-playbooks.md → Form Analysis and Generation`.
> Form XML compile / edit / validate — the `1c-metadata-manage` skill (form-manage section).

## To generate new form:
   Step 1: find and inspect similar existing forms in the configuration — via RLM: `parse_form` on the object, or `search` by the metadata object name or the form's purpose.
   Step 2: study the found form's element hierarchy, data bindings, attributes, commands and event handlers (layout-inspection tool, or reading the `Form.xml` directly).
   Step 3: find similar metadata objects for XML reference (metadata search — names only).
   Step 4: retrieve the XSD schema for `Форма` to understand valid `Form.xml` structure, when a schema tool is available.
   Step 5: generate `Form.xml` based on examples and the schema / validator requirements available in the project.
   Step 6: validate the generated XML — against the XSD via the project's XML-verification tool, and through the `1c-metadata-manage` skill (form-manage / form-validate section). Fix errors if any.
   Step 7: use the `1c-metadata-manage` skill (form-manage section) to compile and deploy the form when deployment is requested.
   Step 8: after form compilation or adding new elements, check the root `version` of `Forms/<FormName>/Ext/Form.xml` against the form/version files already loaded in the project/configurator. If the compiler emitted an older version (for example `2.17`) while the project uses a newer one (for example `2.20`), align the root version before loading the extension; otherwise Configurator rejects the XML with "version differs from previously loaded files".
   Step 9: run `1c-form-validate` after the version alignment. A warning about the validator's default expected version is acceptable when Configurator requires the newer version; XML errors are not acceptable.

## To modify existing form:
   Step 1: get the current form structure (elements, bindings, commands, events) via the layout-inspection tool or by reading the `Form.xml`.
   Step 2: retrieve the XSD schema for `Форма` to constrain valid modifications, when a schema tool is available.
   Step 3: modify `Form.xml` according to the schema / validator constraints and current project examples.
   Step 4: validate the changes against the XSD via the project's XML-verification tool.
   Step 5: use the `1c-metadata-manage` skill (form-edit, form-validate) for actual modifications and validation.
   Step 6: after changing form elements, check the root `version` of `Forms/<FormName>/Ext/Form.xml` against the form/version files already loaded in the project/configurator. Align it when needed before loading the extension.
   Step 7: run `1c-form-validate` after the version alignment. A warning about the validator's default expected version is acceptable when Configurator requires the newer version; XML errors are not acceptable.
