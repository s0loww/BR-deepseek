# 1C Template Manage — Add/Remove Templates

Creates or removes a template (layout) of specified type and registers/unregisters it in the root XML of a 1C metadata object. Works with any object type that supports templates: DataProcessor, Document, Catalog, Report, etc.

## Adding a Template

```
1c-template-manage add <ObjectName> <TemplateName> <TemplateType> [-Apply]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName | yes | — | Object name (for EPF) or object path |
| TemplateName | yes | — | Template name |
| TemplateType | yes | — | Type: HTML, Text, SpreadsheetDocument, BinaryData |
| Synonym | no | = TemplateName | Template synonym |
| SrcDir | no | `src` | Source directory |
| -Apply | no | — | Apply changes; without it the script prints the plan and exits (dry run) |

### Command (EPF)

```powershell
# Dry run (default): prints the plan, writes nothing
pwsh -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" -TemplateType "<TemplateType>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"]

# Apply: actually create and register the template
pwsh -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/add-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" -TemplateType "<TemplateType>" [-Synonym "<Synonym>"] [-SrcDir "<SrcDir>"] -Apply
```

### Type Mapping

User may specify type in free form. Determine the correct one from context:

| User Input | TemplateType | Extension | Content |
|------------|-------------|-----------|---------|
| HTML | HTMLDocument | `.html` | Empty HTML document |
| Text, text document | TextDocument | `.txt` | Empty file |
| SpreadsheetDocument, MXL, spreadsheet | SpreadsheetDocument | `.xml` | Minimal spreadsheet |
| BinaryData, binary | BinaryData | `.bin` | Empty file |

### Print Form Naming Convention

For **print form** templates (SpreadsheetDocument type), apply the prefix `PF_MXL_`:

| Context | Name Format | Example |
|---------|-------------|---------|
| Print form (additional data processor of PrintForm kind, or user explicitly says "print form") | `PF_MXL_<ShortName>` | `PF_MXL_M11`, `PF_MXL_Invoice`, `PF_MXL_EnvelopeDL` |
| Other templates (data import, service, settings) | No prefix | `ImportTemplate`, `PrintSettings` |

If user provides a name without prefix but context is a print form, **add the `PF_MXL_` prefix automatically** and notify.

### What Gets Created

```
<SrcDir>/<ObjectName>/Templates/
├── <TemplateName>.xml              # Template metadata (1 UUID)
└── <TemplateName>/
    └── Ext/
        └── Template.<ext>          # Template content
```

### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — adds `<Template>` to the end of `ChildObjects`

---

## Removing a Template

```
1c-template-manage remove <ObjectName> <TemplateName> [-Apply]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| ObjectName | yes | — | Object name |
| TemplateName | yes | — | Template name to remove |
| SrcDir | no | `src` | Source directory |
| -Apply | no | — | Apply changes; without it the script prints the plan and exits (dry run) |

### Command (EPF)

```powershell
pwsh -NoProfile -File skills/1c-metadata-manage/tools/1c-template-manage/scripts/remove-template.ps1 -ProcessorName "<ObjectName>" -TemplateName "<TemplateName>" [-SrcDir "<SrcDir>"] -Apply
```

### What Gets Removed

```
<SrcDir>/<ObjectName>/Templates/<TemplateName>.xml     # Template metadata
<SrcDir>/<ObjectName>/Templates/<TemplateName>/         # Template directory (recursive)
```

### What Gets Modified

- `<SrcDir>/<ObjectName>.xml` — removes `<Template>` from `ChildObjects`

---

## Workflow

1. `1c-template-manage add -Apply` — create template scaffold (dry run without `-Apply`)
2. For SpreadsheetDocument: use `1c-mxl-compile -Apply` to generate the template content (dry run without `-Apply`)
3. `1c-mxl-validate` — validate template structure
4. `1c-mxl-info` — analyze template structure

## MCP/RLM Integration

RLM - единственный MCP навигации по коду 1С в сборке (см. `AGENTS.md` -> `## 1C tooling`). Вызовы - через `rlm_execute` после `rlm_start`.

- **search_objects** - проверить, что родительский объект существует и поддерживает макеты.
- **parse_object_xml** - структура родительского объекта для подтверждения совместимости с макетом.
- **search** - найти похожие реализации макетов в коде проекта.

