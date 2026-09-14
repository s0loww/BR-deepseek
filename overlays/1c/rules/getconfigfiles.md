---
description: "The object you need to edit has no source in the working copy — export it from the infobase through Designer (`/DumpConfigToFiles` with an object list, main configuration or an extension). Load before editing an object whose sources are missing, or when the local sources are suspected stale. Триггеры: нет исходников объекта, выгрузить объект из базы, DumpConfigToFiles, получить конфигурацию в файлы."
alwaysApply: false
kind: recipe
---

# Exporting Objects from an Infobase to the Repository

## Parameters (defined in `.dev.env` or supplied by the user at task start)

| Placeholder | Purpose |
|---|---|
| `{PLATFORM_PATH}` | Path to the 1C platform installation directory (containing `bin\1cv8.exe`). Example: `C:\Program Files\1cv8\8.3.23.1997` |
| `{INFOBASE_PATH}` | Path to a file infobase or the connection string of a server infobase |
| `{IB_USER}` | Infobase user name |
| `{IB_PASSWORD}` | Password (when required) |
| `{EXPORT_PATH}` | Directory where object sources are exported |
| `{EXTENSION_NAME}` | Extension name when exporting from an extension; otherwise omit the `-Extension` argument |
| `{LOG_PATH}` | Designer log file |

If a value is unknown — **ask the user**, do not guess. Project-stable values go into `.dev.env`.

## Steps

**Step 1.** Compose the list of objects to export in `repoobjects.txt` (one full metadata-object name per line, e.g. `Справочник.Контрагенты`). Build the list via RLM (`search_objects`, `find_by_type`), confirming against local `src/` (see `tooling-playbooks.md → MCP-first Search`). An object that is missing from the working copy may also be missing from the RLM index built over it — then take the full name from the Designer's metadata tree.

Write the list as **UTF-8 with BOM**: without the BOM Designer answers
`Ошибка чтения файла-списка`. Agent write tools produce UTF-8 **without** BOM,
so a generated list must be re-saved before the run
(`io.open(path, 'w', encoding='utf-8-sig')`).

**Step 2.** Run the export through Designer. Objects are exported **in full**, strictly into the specified directory — **do NOT create new subdirectories**.

> This produces the **standard dump layout** (`Documents/<X>/Ext/ObjectModule.bsl`). If the project instead keeps sources unpacked by `v8unpack`, the layout is a different one — singular directory names, `*.obj.bsl` / `*.mgr.bsl` modules, forms as `*.elem.json` — and paths from this recipe will not be found. See `rules/v8unpack-source-structure.md`.

```powershell
$cliArgs = @(
    'DESIGNER',
    '/F', '{INFOBASE_PATH}',
    '/N', '{IB_USER}',
    '/P', '{IB_PASSWORD}',
    '/DisableStartupMessages',
    '/DumpConfigToFiles', '{EXPORT_PATH}',
    '-listFile', 'repoobjects.txt',
    '-Extension', '{EXTENSION_NAME}',
    '/Out', '{LOG_PATH}'
)
$proc = Start-Process -FilePath '{PLATFORM_PATH}\bin\1cv8.exe' `
    -ArgumentList $cliArgs -Wait -PassThru
$proc.ExitCode
```

When exporting from the main configuration (not from an extension) — drop the `-Extension {EXTENSION_NAME}` argument.

> **Do not launch it as `& '…\1cv8.exe' …`.** Designer is a GUI application:
> the call returns immediately, `$LASTEXITCODE` stays empty, and the script walks
> on over an empty export directory reporting success. Only `Start-Process -Wait`
> actually waits, and only its `ExitCode` says whether the run failed.

**Step 3.** Inspect `{LOG_PATH}` for errors before starting any edits. An empty
log is not a pass on its own: confirm the exit code is `0` and that the expected
files actually appeared under `{EXPORT_PATH}`.

## Limits and pitfalls

- **The list file is read as UTF-8 with BOM only** — otherwise
  `Ошибка чтения файла-списка`. The same error is sometimes **transient** on a
  just-written file (a byte-identical file reads fine a minute later): retry
  once before diagnosing anything else.
- **A list export is not a full export.** With `-listFile` Designer writes the
  listed objects only — no `Configuration.xml` with `<ChildObjects>` and no root
  `Ext/`. Such sources are fine to read, search and edit, but
  `/LoadConfigFromFiles` will not assemble a configuration back from them. When
  the goal is a complete tree, export without `-listFile`.
- **Object inventory without exporting anything** —
  `/DumpConfigToFiles {EXPORT_PATH} -configDumpInfoOnly` writes
  `ConfigDumpInfo.xml` and nothing else (tens of MB on a large configuration);
  the metadata skill exposes the same run as `-Mode UpdateInfo`. Use it to size
  the work or to compare the local tree against `<ChildObjects>`.
