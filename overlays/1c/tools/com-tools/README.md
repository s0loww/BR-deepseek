# com-tools

Переносимая PowerShell-библиотека для работы с 1С через `V83.COMConnector`.
Ядро — read-only чтение (запросы, справочники, объекты) плюс единый контракт
режима записи (`-Apply`/DryRun). Мутационные и доменные сценарии живут не здесь,
а в доменных папках целевого проекта, которые подключают это ядро.

## Требования

- Windows PowerShell 5.1 (`powershell.exe`), **не** `pwsh` — `V83.COMConnector`
  в pwsh падает на `Connect()`.
- Зарегистрированный `V83.COMConnector`.
- Файл окружения `.env` с профилями подключения (см. `env.example` в шаблоне
  проектного слоя). `.env` — git-ignored, никогда не коммитится.

## Запуск

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <script.ps1> -EnvPath <path-to-.env> -Profile <NAME>
```

Подключение библиотеки в новом скрипте:

```powershell
. (Join-Path $PSScriptRoot '..\lib\OneC-Bootstrap.ps1')
$session = Initialize-ComToolsSession -EnvPath $EnvPath -Profile $Profile -ScriptName 'MyScript'
try {
    $connection = $session.ConnectionInfo.Connection
    # ... работа с базой ...
} finally {
    Complete-ComToolsSession -Session $session
}
```

`-EnvPath` и `-Profile` — обязательные параметры без дефолтов: путь к базе,
логин и пароль библиотека не хардкодит.

## DryRun / -Apply

Контракт режима записи един (см. `rules/script-contract.md`): по умолчанию
скрипт работает в DryRun (только чтение / превью), реальные мутации включаются
явным флагом `-Apply`. Резолв флага — `Resolve-ComApplyMode` из `OneC-Params.ps1`
(поддержаны legacy-алиасы `-Write`/`-WhatIf`/`-DryRun` для совместимости). После
`-Apply` состояние перечитывается независимым запросом, а не берётся на слово из
собственного вывода скрипта.

## Структура в целевом проекте

```
com-tools/
  lib/                    # это ядро (OneC-*.ps1)
  <domain>/               # доменные / разовые сценарии, подключают lib/
  examples/
    queries/              # .sql для проб
    parameters/           # JSON-параметры
```

Переиспользуемое ядро живёт в `lib/`; одноразовые и доменные сценарии — в папках
по задачам и подключают `lib/`, а не дублируют его. **Перед написанием нового
скрипта сначала ищи готовый или образец в существующих папках.**

## Формат `.sql`-запросов

Параметры задаются заголовочными комментариями в самом файле запроса:

```
; @param ДатаНачала=@date:2026-01-01T00:00:00
; @param ЛимитСтрок=@number:100
; @param ТолькоПроведённые=@bool:true
; @param Номер=00000001
```

Типы: `@date:` → дата/время, `@number:` → число, `@bool:true|false` → булево,
без префикса → строка. Значения можно вынести в отдельный JSON-файл параметров
(`Read-ComQueryParametersFile`); файловые параметры имеют приоритет над
заголовками запроса.

## Лог-каталог

Путь лога разрешается `Resolve-ComLogPath`: сначала параметр `-LogPath`, затем
`COM.LogPath` из `.env`, иначе дефолт `var/com-tools-logs/` в корне проекта.

## Модули `lib/`

| Модуль | Функции |
|--------|---------|
| `OneC-Bootstrap.ps1` | `Import-ComToolsLib`, `Initialize-ComToolsSession`, `Complete-ComToolsSession`, `Get-ComToolsRoot` |
| `OneC-Env.ps1` | `Read-ComEnvFile`, `Get-ComProfileSettings`, `Resolve-ComLogPath`, `Write-ComLogLine`, `Write-ComLogHeader` |
| `OneC-Connect.ps1` | `Get-ComConnectionMode`, `Build-ComConnectionString`, `Connect-ComInfobase`, `Disconnect-ComInfobase` (File/Server/Auto) |
| `OneC-Com.ps1` | `Invoke-ComMethod`, `Get-ComPropertySafe`, `Get-ComCollectionCount`, `Get-ComCollectionItem`, `Convert-ComValueToText` |
| `OneC-Query.ps1` | `Read-ComQueryFile`, `Read-ComQueryParametersFile`, `New-ComQueryObject`, `Invoke-ComQueryDryRun`, `Invoke-ComQueryApply`, `Invoke-ComQueryRows`, `Write-ComQueryResultToLog`, `Get-ComQueryFileList` |
| `OneC-Reference.ps1` | `Get-ComReferenceUuid`, `Get-ComReferencePresentation`, `Get-ComObjectFromReference`, `Test-ComReferenceFilled`, `Find-ComDocumentReference` |
| `OneC-Export.ps1` | `New-ComOutputPath`, `Export-ComResultCsv` |
| `OneC-Params.ps1` | `Resolve-ComApplyMode`, `Get-ComRunModeName`, `Write-ComApplyModeDeprecation` (единый контракт `-Apply`) |

Дополнительные модули донорской библиотеки (документные шапки и probe режимов
записи, планы CSV, проведение/распроведение, сравнение наборов строк, обмен
между базами) в это минимальное ядро не входят — доезжают по мере надобности
через возврат практики.

## Что почитать перед написанием скрипта

- `rules/com-powershell-1c.md` — грабли COM/PowerShell и проверенные
  обходы (runtime, обёртки, коллекции, документы, запросы, безопасность записи).
- `rules/script-contract.md` — generic-контракт автоматизационных скриптов
  (DryRun/Apply, exit-коды, отчёты, креды, идемпотентность).
