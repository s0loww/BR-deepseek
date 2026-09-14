# 1C Configuration Manage — Init, Edit, Info, Validate

Comprehensive configuration management: create scaffold, edit properties/composition, analyze structure, validate correctness.

---

## 1. Init — Create Configuration Scaffold

```powershell
# Dry run (default): prints the plan, writes nothing
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-init.ps1 -Name "<Name>" [-OutputDir "<path>"]

# Apply: actually create the files
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-init.ps1 -Name "<Name>" [-OutputDir "<path>"] -Apply
```

Creates minimal configuration structure: `Configuration.xml`, `Languages/Русский.xml`, and basic directory structure.

---

## 2. Edit — Modify Configuration Properties

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-edit.ps1 -ConfigPath '<path>' -Operation <op> -Value '<value>' -Apply
```

| Parameter | Description |
|-----------|-------------|
| `ConfigPath` | Path to Configuration.xml or export directory |
| `Operation` | Operation (see table) |
| `Value` | Value (batch via `;;`) |
| `DefinitionFile` | JSON file with operation array |
| `NoValidate` | Skip auto-validation |
| `Apply` | Apply changes; without it the script prints the plan and exits (dry run) |

### Operations

| Operation | Value Format | Description |
|-----------|-------------|-------------|
| `modify-property` | `Key=Value` (batch `;;`) | Change property |
| `add-childObject` | `Type.Name` (batch `;;`) | Add object to ChildObjects |
| `remove-childObject` | `Type.Name` (batch `;;`) | Remove object from ChildObjects |
| `add-defaultRole` | `Role.Name` or `Name` | Add default role |
| `remove-defaultRole` | `Role.Name` or `Name` | Remove default role |
| `set-defaultRoles` | Names via `;;` | Replace default roles list |

Full property reference: [cf-edit-reference.md](skills/1c-metadata-manage/tools/1c-cf-manage/cf-edit-reference.md).

### Examples

```powershell
# Change version and vendor — dry run first (prints the plan, no changes)
... -Operation modify-property -Value "Version=1.0.0.1 ;; Vendor=Company"
# Then apply
... -Operation modify-property -Value "Version=1.0.0.1 ;; Vendor=Company" -Apply

# Add objects
... -Operation add-childObject -Value "Catalog.Товары ;; Document.Заказ" -Apply

# Default roles
... -Operation set-defaultRoles -Value "ПолныеПрава ;; Администратор" -Apply
```

---

## 3. Info — Analyze Configuration Structure

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-info.ps1 -ConfigPath "<path>"
```

Displays configuration properties, object counts by type, compatibility mode, version, and other key information.

---

## 4. Validate — Check Configuration Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cf-manage/scripts/cf-validate.ps1 -ConfigPath "<path>"
```

| Parameter | Description |
|-----------|-------------|
| `ConfigPath` | Path to Configuration.xml or export directory |
| `MaxErrors` | Stop after N errors (default: 30) |
| `OutFile` | Write result to file (UTF-8 BOM) |

### Checks Performed

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness, MetaDataObject/Configuration, version 2.17/2.20 | ERROR |
| 2 | InternalInfo: 7 ContainedObject, valid ClassId, uniqueness | ERROR |
| 3 | Properties: Name non-empty, Synonym, DefaultLanguage, DefaultRunMode | ERROR/WARN |
| 4 | Properties: enum values (11 properties) | ERROR |
| 5 | ChildObjects: valid type names (44 types), no duplicates, type order | ERROR/WARN |
| 6 | DefaultLanguage references existing Language in ChildObjects | ERROR |
| 7 | Language files Languages/<name>.xml exist | WARN |
| 8 | Object directories from ChildObjects exist (spot-check) | WARN |

Exit code: 0 = OK, 1 = errors.

---

## Typical Workflow

```
1c-cf-manage init        — create configuration scaffold (mutation: requires -Apply)
1c-cf-manage edit        — set properties, add objects (mutation: requires -Apply)
1c-cf-manage validate    — check correctness
1c-cf-manage info        — view structure summary
```

Mutating steps (`init`, `edit`) run as dry run by default: they print the plan and exit. Pass `-Apply` to write changes.

## MCP/RLM Integration

RLM - единственный MCP навигации по коду 1С в сборке (см. `AGENTS.md` -> `## 1C tooling`). Вызовы - через `rlm_execute` после `rlm_start`.

- **get_object_full_structure** / **analyze_object** - структурный паспорт существующих объектов конфигурации (структура, формы, зависимости, код, роли) в один вызов.
- **search_objects** - исследовать существующую структуру конфигурации, проверить имена объектов; найти похожие объекты конфигурации как образец для XML.
- **parse_object_xml** - полная структура существующих объектов конфигурации.

Валидация сгенерированной Configuration-XML - локальным скриптом `1c-cf-validate` (см. Workflow выше), не MCP-инструментом. Сравнение объектов конфигурации с их аналогами в расширении - см. `1c-cfe-manage` -> `cfe-diff.ps1`.
