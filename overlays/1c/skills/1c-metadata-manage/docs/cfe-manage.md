# 1C Extension Manage — Init, Borrow, Diff, Patch, Validate

Comprehensive extension (CFE) management: create scaffold, borrow objects from configuration, analyze changes, generate method interceptors, validate correctness.

---

## 1. Init — Create Extension Scaffold

```powershell
# Dry run (default): prints the plan, writes nothing
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-init.ps1 -Name "МоёРасширение"

# Apply: actually create the scaffold
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-init.ps1 -Name "МоёРасширение" -Apply
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `Name` | Extension name (required) | — |
| `Synonym` | Synonym | = Name |
| `NamePrefix` | Prefix for own objects | = Name + "_" |
| `OutputDir` | Output directory | `src` |
| `Purpose` | `Patch` / `Customization` / `AddOn` | `Customization` |
| `Version` | Extension version | — |
| `Vendor` | Vendor | — |
| `CompatibilityMode` | Compatibility mode | `Version8_3_24` |
| `NoRole` | Without main role | false |
| `Apply` | Apply changes; without it the script prints the plan and exits (dry run) | false |

### What Gets Created

```
<OutputDir>/
├── Configuration.xml         # Extension properties
├── Languages/
│   └── Русский.xml           # Language (borrowed)
└── Roles/                    # If not -NoRole
    └── <Prefix>ОсновнаяРоль.xml
```

**Preparation**: Before creating, get the base configuration version: `1c-cf-manage info <ConfigPath>`.

---

## 2. Borrow — Borrow Objects from Configuration

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-borrow.ps1 -ExtensionPath src -ConfigPath <config> -Object "Catalog.Контрагенты" -Apply
```

| Parameter | Description |
|-----------|-------------|
| `ExtensionPath` | Path to extension directory (required) |
| `ConfigPath` | Path to source configuration (required) |
| `Object` | What to borrow (required), batch via `;;` |
| `Apply` | Apply changes; without it the script prints the plan and exits (dry run) |

Format: `Catalog.X`, `CommonModule.Y`, `Document.Z`. All 44 object types supported. Batch: `"Catalog.X ;; CommonModule.Y ;; Enum.Z"`.

Creates XML files with `ObjectBelonging=Adopted` and `ExtendedConfigurationObject`, adds to ChildObjects.

---

## 3. Diff — Analyze Extension Changes

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-diff.ps1 -ExtensionPath src -ConfigPath <config> -Mode A
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ExtensionPath` | Path to extension (required) | — |
| `ConfigPath` | Path to configuration (required) | — |
| `Mode` | `A` (overview) / `B` (transfer check) | `A` |

**Mode A** — overview: For each object shows `[BORROWED]` (interceptors, own attributes/TS/forms) or `[OWN]` (counts).

**Mode B** — transfer check: For each `&ИзменениеИКонтроль`, extracts `#Вставка`/`#КонецВставки` blocks and searches for them in the configuration module. Statuses: `[TRANSFERRED]`, `[NOT_TRANSFERRED]`, `[NEEDS_REVIEW]`.

---

## 4. Patch — Generate Method Interceptor

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-patch-method.ps1 -ExtensionPath src -ModulePath "Catalog.Контрагенты.ObjectModule" -MethodName "ПриЗаписи" -InterceptorType Before -Apply
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ExtensionPath` | Path to extension (required) | — |
| `ModulePath` | Module path (required) | — |
| `MethodName` | Method to intercept (required) | — |
| `InterceptorType` | `Before` / `After` / `ModificationAndControl` (required) | — |
| `Context` | Context directive | `НаСервере` |
| `IsFunction` | Method is a function (adds `Return`) | false |
| `Apply` | Apply changes; without it the script prints the plan and exits (dry run) | false |

### ModulePath Format

| ModulePath | File |
|------------|------|
| `Catalog.X.ObjectModule` | `Catalogs/X/Ext/ObjectModule.bsl` |
| `Catalog.X.ManagerModule` | `Catalogs/X/Ext/ManagerModule.bsl` |
| `Catalog.X.Form.Y` | `Catalogs/X/Forms/Y/Ext/Form/Module.bsl` |
| `CommonModule.X` | `CommonModules/X/Ext/Module.bsl` |

### Interceptor Types

| Type | Decorator | Purpose |
|------|-----------|---------|
| `Before` | `&Перед` | Code before the original method call |
| `After` | `&После` | Code after the original method call |
| `ModificationAndControl` | `&ИзменениеИКонтроль` | Copy of method body with `#Вставка`/`#Удаление` markers |

**Prerequisite**: Object must be borrowed first (`cfe-borrow`).

---

## 5. Validate — Check Extension Correctness

```powershell
powershell.exe -NoProfile -File skills/1c-metadata-manage/tools/1c-cfe-manage/scripts/cfe-validate.ps1 -ExtensionPath src
```

### Checks (9 steps)

| # | Check | Severity |
|---|-------|----------|
| 1 | XML well-formedness, MetaDataObject/Configuration, version | ERROR |
| 2 | InternalInfo: 7 ContainedObject, valid ClassId | ERROR |
| 3 | Extension properties: ObjectBelonging=Adopted, Name, Purpose, NamePrefix, KeepMapping | ERROR |
| 4 | Enum values: CompatibilityMode, DefaultRunMode, ScriptVariant, InterfaceCompatibilityMode | ERROR |
| 5 | ChildObjects: valid types (44), no duplicates, canonical order | ERROR/WARN |
| 6 | DefaultLanguage references Language in ChildObjects | ERROR |
| 7 | Language files exist | WARN |
| 8 | Object directories exist | WARN |
| 9 | Borrowed objects: ObjectBelonging=Adopted, ExtendedConfigurationObject UUID | ERROR/WARN |

Exit code: 0 = OK, 1 = errors.

---

## Typical Extension Workflow

```
1c-cf-manage info <config>          — get base config version/compatibility
1c-cfe-manage init                  — create extension scaffold (mutation: requires -Apply)
1c-cfe-manage borrow               — borrow objects to modify (mutation: requires -Apply)
1c-cfe-manage patch                 — generate interceptors (mutation: requires -Apply)
1c-cfe-manage validate              — check correctness
1c-cfe-manage diff -Mode A          — review changes overview
1c-cfe-manage diff -Mode B          — check transfer status
```

Mutating steps (`init`, `borrow`, `patch`) run as dry run by default: they print the plan and exit. Pass `-Apply` to write changes.

## MCP/RLM Integration

RLM - единственный MCP навигации по коду 1С в сборке (см. `AGENTS.md` -> `## 1C tooling`). Вызовы - через `rlm_execute` после `rlm_start`.

- **get_object_full_structure** / **analyze_object** - структурный паспорт базового объекта перед заимствованием (структура, формы, зависимости, модули кода, роли).
- **search_objects** - найти объекты для заимствования и проверить пути модулей.
- **parse_object_xml** - полная структура заимствуемого объекта.
- **search** / **safe_grep** - найти методы для перехвата в коде.
- **find_call_hierarchy** / **find_callers_context** - рекурсивный анализ влияния изменений расширения на базовую конфигурацию перед заимствованием.

Структурный дифф базы и расширения после заимствования (атрибуты, формы, процедуры - добавлено/переопределено/без изменений) - локальным инструментом `1c-cfe-manage` -> `cfe-diff.ps1`, не MCP-инструментом. Статическая проверка сгенерированного BSL - `tools/agent-1c` analyze (BSL LS), если настроен.
