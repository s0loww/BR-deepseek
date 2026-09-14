#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('bootstrap', 'doctor', 'analyze', 'deploy', 'test')]
    [string]$Command = 'doctor',

    [string]$Profile = (Join-Path (Get-Location) 'agent-1c.json'),
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$script:Steps = New-Object System.Collections.ArrayList
$script:Warnings = New-Object System.Collections.ArrayList
$script:Artifacts = New-Object System.Collections.ArrayList
$script:ExitCode = 0
$script:StartedAt = [DateTime]::UtcNow
$script:ToolRoot = Join-Path $env:LOCALAPPDATA 'agent-1c\tools'
$script:LockPath = Join-Path $PSScriptRoot 'toolchain.lock.json'

# Сторож над 1cv8 и межпроцессный лок на базу. Скрипты проекта, ходящие в ту
# же ИБ мимо этого контура, обязаны подключать ЭТОТ же файл: лок, накрывающий
# один путь из двух, не гарантирует ничего.
. (Join-Path $PSScriptRoot 'lib\1c-guard.ps1')

function Get-1CBaseIdentity {
    <# Строка, однозначно определяющая базу, — ключ лока. #>
    param($Target, [string]$ResolvedPath)

    if ($Target.kind -eq 'file') { return $ResolvedPath }
    if ($Target.kind -eq 'server') { return ([string]$Target.server + '/' + [string]$Target.ref) }
    return ''
}

function Add-Step {
    param([string]$Name, [string]$Status, [string]$Message)
    [void]$script:Steps.Add([ordered]@{ name = $Name; status = $Status; message = $Message })
}

function Resolve-ProjectPath {
    param([string]$PathValue, [string]$ProjectRoot)
    if ([IO.Path]::IsPathRooted($PathValue)) { return [IO.Path]::GetFullPath($PathValue) }
    return [IO.Path]::GetFullPath((Join-Path $ProjectRoot $PathValue))
}

function Read-EnvSection {
    param([string]$Path, [string]$Section)
    $values = @{}
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) { return $values }
    $currentSection = ''
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $text = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($text) -or $text.StartsWith('#')) { continue }
        if ($text -match '^\[(.+)\]$') { $currentSection = $Matches[1].Trim(); continue }
        if ($currentSection -ne $Section) { continue }
        if ($text -match '^([^=]+?)\s*=\s*(.*)$') {
            $key = $Matches[1].Trim()
            $value = $Matches[2].Trim().Trim('"').Trim("'")
            $values[$key] = $value
        }
    }
    return $values
}

function Resolve-TargetCredentials {
    param($Target)
    $result = [ordered]@{ user = $null; password = $null; path = $null }  # airules:allow creds-password (field init, not a hardcoded secret)
    $envValues = @{}
    if ($Target.envFile) {
        $envPath = Resolve-ProjectPath $Target.envFile $script:ProjectRoot
        $envValues = Read-EnvSection $envPath ([string]$Target.envSection)
    }
    if ($Target.userEnv) {
        $envUser = [Environment]::GetEnvironmentVariable([string]$Target.userEnv)
        if ($envUser) { $result.user = $envUser }
    }
    if (-not $result.user -and $envValues.ContainsKey('Login')) { $result.user = $envValues['Login'] }
    if ($Target.passwordEnv) {
        $envPassword = [Environment]::GetEnvironmentVariable([string]$Target.passwordEnv)  # airules:allow creds-password (reads env var, no literal secret)
        if ($envPassword) { $result.password = $envPassword }  # airules:allow creds-password (assignment from env, no literal secret)
    }
    if (-not $result.password -and $envValues.ContainsKey('Pass')) { $result.password = $envValues['Pass'] }  # airules:allow creds-password (reads .env value, no literal secret)
    if ($Target.path) { $result.path = Resolve-ProjectPath $Target.path $script:ProjectRoot }
    elseif ($envValues.ContainsKey('Path')) { $result.path = $envValues['Path'] }
    elseif ($envValues.ContainsKey('File')) { $result.path = $envValues['File'] }
    return $result
}

function Quote-IfNeeded {
    param([string]$Value)
    if ($Value -match '[\s"]') { return '"' + ($Value -replace '"', '\"') + '"' }
    return $Value
}

function Format-DeployCommandLine {
    param([string]$Exe, $Arguments, [string]$Secret)
    $line = (Quote-IfNeeded $Exe) + ' ' + (($Arguments | ForEach-Object { [string]$_ }) -join ' ')
    if (-not [string]::IsNullOrEmpty($Secret)) { $line = $line.Replace($Secret, '<hidden>') }
    return $line
}

function Get-VrunnerPath {
    $command = Get-Command 'vrunner' -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        (Join-Path $script:ToolRoot 'onescript\bin\vrunner.bat'),
        (Join-Path $script:ToolRoot 'onescript\bin\vrunner')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}

function Get-Platform {
    param($ProfileData)
    if ($ProfileData.platform.executable) {
        $explicit = Resolve-ProjectPath $ProfileData.platform.executable $script:ProjectRoot
        if (Test-Path -LiteralPath $explicit -PathType Leaf) { return Get-Item -LiteralPath $explicit }
    }

    $candidates = @()
    foreach ($root in @('C:\Program Files\1cv8', 'C:\Program Files (x86)\1cv8')) {
        if (Test-Path -LiteralPath $root) {
            $candidates += Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
                Where-Object { -not $ProfileData.platform.versionPrefix -or $_.Name.StartsWith([string]$ProfileData.platform.versionPrefix) } |
                ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'bin\1cv8.exe') -ErrorAction SilentlyContinue }
        }
    }
    return $candidates | Sort-Object { try { [version]$_.Directory.Parent.Name } catch { [version]'0.0' } } -Descending | Select-Object -First 1
}

function Get-BslExecutable {
    $lock = Get-Content -LiteralPath $script:LockPath -Raw | ConvertFrom-Json
    $base = Join-Path $script:ToolRoot ("bsl-language-server\" + $lock.bslLanguageServer.version)
    return Join-Path $base $lock.bslLanguageServer.executable
}

function Install-BslLanguageServer {
    $lock = Get-Content -LiteralPath $script:LockPath -Raw | ConvertFrom-Json
    $target = Join-Path $script:ToolRoot ("bsl-language-server\" + $lock.bslLanguageServer.version)
    $exe = Join-Path $target $lock.bslLanguageServer.executable
    if (Test-Path -LiteralPath $exe) {
        Add-Step 'bootstrap.bsl' 'skipped' ("Уже установлен: " + $exe)
        return $exe
    }

    New-Item -ItemType Directory -Path $target -Force | Out-Null
    $archive = Join-Path $env:TEMP ("bsl-language-server-" + $lock.bslLanguageServer.version + '.zip')
    Invoke-WebRequest -Uri $lock.bslLanguageServer.url -OutFile $archive -UseBasicParsing
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    if ($actualHash -ne $lock.bslLanguageServer.sha256) {
        throw "Контрольная сумма BSL LS не совпала. Ожидалась $($lock.bslLanguageServer.sha256), получена $actualHash"
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $target -Force
    if (-not (Test-Path -LiteralPath $exe)) { throw "BSL LS распакован, но executable не найден: $exe" }
    Add-Step 'bootstrap.bsl' 'ok' ("Установлен BSL LS " + $lock.bslLanguageServer.version)
    return $exe
}

function Get-TargetArguments {
    param($Target, $ResolvedPath)
    if ($Target.kind -eq 'file') {
        if ([string]::IsNullOrWhiteSpace($ResolvedPath)) { throw 'Путь файловой ИБ не определён (testTarget.path пуст и не найден Path в envFile).' }
        return @('/F', ('"' + $ResolvedPath + '"'))
    }
    if ($Target.kind -eq 'server') { return @('/S', ('"' + $Target.server + '/' + $Target.ref + '"')) }
    throw 'Тестовая цель не настроена.'
}

function Add-Credentials {
    param([System.Collections.ArrayList]$Arguments, $Credentials)
    if ($Credentials.user) { [void]$Arguments.Add('/N'); [void]$Arguments.Add((Quote-IfNeeded $Credentials.user)) }
    if ($Credentials.password) { [void]$Arguments.Add('/P'); [void]$Arguments.Add((Quote-IfNeeded $Credentials.password)) }
}

function Invoke-Doctor {
    $platform = Get-Platform $script:ProfileData
    if ($platform) { Add-Step 'doctor.platform' 'ok' $platform.FullName } else { Add-Step 'doctor.platform' 'error' '1cv8.exe не найден'; $script:ExitCode = 2 }

    $bsl = Get-BslExecutable
    if (Test-Path -LiteralPath $bsl) {
        $lock = Get-Content -LiteralPath $script:LockPath -Raw | ConvertFrom-Json
        Add-Step 'doctor.bsl' 'ok' ("$bsl (закреплена версия $($lock.bslLanguageServer.version))")
    } else {
        Add-Step 'doctor.bsl' 'warning' 'BSL LS не установлен; выполните bootstrap'
        [void]$script:Warnings.Add('BSL LS недоступен')
    }

    $vrunner = Get-VrunnerPath
    if ($vrunner) { Add-Step 'doctor.vanessa-runner' 'ok' $vrunner } else { Add-Step 'doctor.vanessa-runner' 'optional' 'Не установлен' }
}

function Invoke-Analyze {
    $bsl = Get-BslExecutable
    if (-not (Test-Path -LiteralPath $bsl)) { throw 'BSL LS не установлен. Сначала выполните bootstrap.' }
    $source = Resolve-ProjectPath $script:ProfileData.sourceDir $script:ProjectRoot
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Каталог исходников не найден: $source" }
    $out = Join-Path $script:RunDir 'bsl'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $stdout = Join-Path $out 'stdout.log'
    $stderr = Join-Path $out 'stderr.log'
    $arguments = @('analyze', '--srcDir', ('"' + $source + '"'), '--workspaceDir', ('"' + $script:ProjectRoot + '"'), '--outputDir', ('"' + $out + '"'), '--reporter', 'json', '--reporter', 'junit', '--reporter', 'sarif', '--silent')
    $process = Start-Process -FilePath $bsl -ArgumentList $arguments -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    $code = $process.ExitCode
    [void]$script:Artifacts.Add($out)
    if ($code -ne 0) { Add-Step 'analyze.bsl' 'error' "BSL LS завершился с кодом $code"; $script:ExitCode = $code }
    else {
        $jsonReport = Join-Path $out 'bsl-json.json'
        $severityCounts = @{}
        if (Test-Path -LiteralPath $jsonReport) {
            $analysis = Get-Content -LiteralPath $jsonReport -Raw | ConvertFrom-Json
            foreach ($diagnostic in ($analysis.fileinfos | ForEach-Object { @($_.diagnostics) })) {
                if ($diagnostic.severity) {
                    if (-not $severityCounts.ContainsKey($diagnostic.severity)) { $severityCounts[$diagnostic.severity] = 0 }
                    $severityCounts[$diagnostic.severity]++
                }
            }
        }
        $summary = ($severityCounts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ', '
        if ($severityCounts.ContainsKey('Error') -and $severityCounts['Error'] -gt 0) {
            Add-Step 'analyze.bsl' 'error' "Найдены ошибки: $summary. Отчёты: $out"
            $script:ExitCode = 4
        } else {
            Add-Step 'analyze.bsl' 'ok' "Результат: $summary. Отчёты: $out"
        }
    }
}

function Invoke-Deploy {
    $target = $script:ProfileData.testTarget
    if (-not $target -or $target.kind -eq 'none') { Add-Step 'deploy' 'planned' 'Тестовая ИБ не настроена; мутации отсутствуют'; return }
    if ($target.environment -eq 'production') { throw 'Deploy в production запрещён политикой agent-1c.' }
    $platform = Get-Platform $script:ProfileData
    if (-not $platform) { throw '1cv8.exe не найден.' }
    $source = Resolve-ProjectPath $script:ProfileData.sourceDir $script:ProjectRoot

    $extensionName = $null
    if ($script:ProfileData.extension -and $script:ProfileData.extension.name) { $extensionName = [string]$script:ProfileData.extension.name }

    $credentials = Resolve-TargetCredentials $target
    $planMessage = "Загрузить XML из $source и обновить тестовую ИБ ($($target.kind))"
    if ($extensionName) { $planMessage += "; расширение $extensionName (-Extension)" }
    Add-Step 'deploy.plan' 'ok' $planMessage

    # Общая часть командной строки DESIGNER — переиспользуется каждым запуском.
    $common = New-Object System.Collections.ArrayList
    [void]$common.Add('DESIGNER')
    foreach ($arg in (Get-TargetArguments $target $credentials.path)) { [void]$common.Add($arg) }
    Add-Credentials $common $credentials
    [void]$common.Add('/DisableStartupDialogs')

    $runs = New-Object System.Collections.ArrayList
    if ($extensionName) {
        # Платформа (проверено на 8.3.27) отвергает /LoadConfigFromFiles -Extension и
        # /UpdateDBCfg -Extension в ОДНОМ запуске DESIGNER. Для расширения деплой
        # выполняется двумя последовательными запусками с теми же флагами; для основной
        # конфигурации совмещённый запуск работает и остаётся одним.
        $loadLog = Join-Path $script:RunDir 'deploy-load.log'
        $load = New-Object System.Collections.ArrayList
        [void]$load.AddRange($common)
        [void]$load.Add('/LoadConfigFromFiles'); [void]$load.Add(('"' + $source + '"'))
        [void]$load.Add('-Extension'); [void]$load.Add((Quote-IfNeeded $extensionName))
        [void]$load.Add('-Format'); [void]$load.Add('Hierarchical')
        [void]$load.Add('/Out'); [void]$load.Add(('"' + $loadLog + '"'))
        [void]$runs.Add(@{ name = 'load'; args = $load; log = $loadLog })

        $updateLog = Join-Path $script:RunDir 'deploy-update.log'
        $update = New-Object System.Collections.ArrayList
        [void]$update.AddRange($common)
        [void]$update.Add('/UpdateDBCfg'); [void]$update.Add('-Extension'); [void]$update.Add((Quote-IfNeeded $extensionName))
        [void]$update.Add('/Out'); [void]$update.Add(('"' + $updateLog + '"'))
        [void]$runs.Add(@{ name = 'update'; args = $update; log = $updateLog })
    }
    else {
        $log = Join-Path $script:RunDir 'deploy.log'
        $single = New-Object System.Collections.ArrayList
        [void]$single.AddRange($common)
        [void]$single.Add('/LoadConfigFromFiles'); [void]$single.Add(('"' + $source + '"'))
        [void]$single.Add('/UpdateDBCfg')
        [void]$single.Add('/Out'); [void]$single.Add(('"' + $log + '"'))
        [void]$runs.Add(@{ name = 'load+update'; args = $single; log = $log })
    }

    foreach ($run in $runs) {
        $redactedCommand = Format-DeployCommandLine $platform.FullName $run.args $credentials.password
        Add-Step "deploy.command.$($run.name)" 'planned' $redactedCommand
    }

    if (-not $Apply) { Add-Step 'deploy.apply' 'dry-run' 'Для применения требуется -Apply'; return }

    # Лок держится на ОБА запуска: между load и update конфигурация в базе уже
    # изменена, но не применена — чужой деплой в этот промежуток ломает обе стороны.
    $guardLog = Join-Path $script:RunDir 'guard.log'
    $baseId = Get-1CBaseIdentity $target $credentials.path
    $lock = $null
    if ($baseId) { $lock = Enter-1CBaseLock -Target $baseId -LogPath $guardLog }
    try {
        foreach ($run in $runs) {
            $guard = Invoke-Guarded1C -FilePath $platform.FullName -ArgumentList ([string[]]$run.args) `
                -Label "deploy/$($run.name)" -LogPath $guardLog
            [void]$script:Artifacts.Add($run.log)
            if ($guard.Killed) {
                $hint = ''
                if ($guard.DialogSeen) { $hint = ' У процесса было окно — вероятен модальный диалог платформы.' }
                Add-Step "deploy.apply.$($run.name)" 'error' "Сторож снял процесс: $($guard.Reason).$hint"
                throw "Deploy ($($run.name)) снят сторожем: $($guard.Reason).$hint См. $guardLog"
            }
            if ($guard.ExitCode -ne 0) { throw "Deploy ($($run.name)) завершился с кодом $($guard.ExitCode). См. $($run.log)" }
            Add-Step "deploy.apply.$($run.name)" 'ok' "Шаг выполнен за $($guard.DurationSec) с, пик памяти $($guard.PeakPrivateGb) ГБ; лог: $($run.log)"
        }
    }
    finally {
        Exit-1CBaseLock $lock
        [void]$script:Artifacts.Add($guardLog)
    }
    Add-Step 'deploy.apply' 'ok' ("Тестовая ИБ обновлена; запусков: " + $runs.Count)
}

function Get-OneScriptBin {
    return Join-Path $script:ToolRoot 'onescript\bin'
}

function Get-VanessaEpfPath {
    # Приоритет: свежий vanessa-automation (GitHub-релиз). bddRunner из opm-пакета add (6.8.0, 2021)
    # несовместим с платформой 8.3.27 — падает на разборе версии режима совместимости при загрузке плагинов.
    $vanessaRoot = Join-Path $script:ToolRoot 'vanessa'
    if (Test-Path -LiteralPath $vanessaRoot -PathType Container) {
        $found = Get-ChildItem -LiteralPath $vanessaRoot -Directory |
            Sort-Object Name -Descending |
            ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'vanessa-automation-single.epf') -ErrorAction SilentlyContinue } |
            Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    $fallback = Join-Path $script:ToolRoot 'onescript\lib\add\bddRunner.epf'
    if (Test-Path -LiteralPath $fallback -PathType Leaf) { return $fallback }
    return $null
}

function ConvertTo-JsonScalar {
    param($Value)
    $json = ConvertTo-Json -InputObject ([string]$Value) -Compress
    return $json.Substring(1, $json.Length - 2)
}

function Expand-TemplateToFile {
    param([string]$TemplatePath, [hashtable]$Replacements, [string]$OutputPath)
    $text = Get-Content -LiteralPath $TemplatePath -Raw -Encoding UTF8
    foreach ($key in $Replacements.Keys) {
        $text = $text.Replace('{{' + $key + '}}', (ConvertTo-JsonScalar $Replacements[$key]))
    }
    # UTF-8 строго С BOM: VAParams читает 1С — ЧтениеТекста определяет кодировку по BOM,
    # без BOM на ru-Windows файл читается как windows-1251 и JSON с кириллическими ключами не парсится
    # (симптом: модалка «Не удалось прочитать файл настроек JSON»).
    $encoding = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllText($OutputPath, $text, $encoding)
}

function Remove-SecretFromFiles {
    param([string[]]$Files, [string]$Secret)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    foreach ($file in $Files) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $content = Get-Content -LiteralPath $file -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }
        $masked = $content
        if (-not [string]::IsNullOrEmpty($Secret)) { $masked = $masked.Replace($Secret, '<hidden>') }
        # Пароль тест-клиента передаётся аргументом /P с кавычками (ДопПараметры VAParams) — маскируем и его след  # airules:allow creds-p-flag (masking pattern, not a secret)
        $masked = [regex]::Replace($masked, '/P"[^"]*"', '/P"<hidden>"')  # airules:allow creds-p-flag (masking pattern, not a secret)
        if ($masked -ne $content) {
            [System.IO.File]::WriteAllText($file, $masked, $encoding)
        }
    }
}

function Invoke-Test {
    $vrunner = Get-VrunnerPath
    if (-not $vrunner) { Add-Step 'test.vanessa' 'unavailable' 'Vanessa Runner не установлен или не добавлен в PATH'; $script:ExitCode = 3; return }
    $vanessaEpf = Get-VanessaEpfPath
    if (-not $vanessaEpf) { Add-Step 'test.vanessa' 'unavailable' 'Vanessa-Automation не установлена: положите vanessa-automation-single.epf в %LOCALAPPDATA%\agent-1c\tools\vanessa\<версия>\'; $script:ExitCode = 3; return }

    $target = $script:ProfileData.testTarget
    if (-not $target -or $target.kind -eq 'none') { Add-Step 'test.vanessa' 'planned' 'Тестовая ИБ не настроена; смоук пропущен'; return }
    if ($target.environment -eq 'production') { throw 'Тестирование в production запрещено политикой agent-1c.' }
    if ($target.kind -ne 'file') { throw 'Vanessa-смоук настроен только для файловой ИБ (testTarget.kind = file).' }

    $platform = Get-Platform $script:ProfileData
    if (-not $platform) { throw '1cv8.exe не найден.' }
    $v8version = $platform.Directory.Parent.Name

    $credentials = Resolve-TargetCredentials $target
    if ([string]::IsNullOrWhiteSpace($credentials.path)) { throw 'Путь файловой ИБ не определён (testTarget.path пуст и не найден Path в envFile).' }

    $featuresRel = 'tools/agent-1c/vanessa-suite/features'
    $settingsTemplateRel = 'tools/agent-1c/vanessa-suite/vanessa-settings.template.json'
    $addTemplateRel = 'tools/agent-1c/vanessa-suite/vanessa-add-params.template.json'
    $testClientTimeout = 300
    $ordinaryApp = 0
    if ($script:ProfileData.vanessa) {
        $vanessaCfg = $script:ProfileData.vanessa
        if ($vanessaCfg.featuresDir) { $featuresRel = [string]$vanessaCfg.featuresDir }
        if ($vanessaCfg.settingsTemplate) { $settingsTemplateRel = [string]$vanessaCfg.settingsTemplate }
        if ($vanessaCfg.addParamsTemplate) { $addTemplateRel = [string]$vanessaCfg.addParamsTemplate }
        if ($vanessaCfg.testClientTimeoutSeconds) { $testClientTimeout = [int]$vanessaCfg.testClientTimeoutSeconds }
        if ($null -ne $vanessaCfg.ordinaryApp) { $ordinaryApp = [int]$vanessaCfg.ordinaryApp }
    }

    $featuresDir = Resolve-ProjectPath $featuresRel $script:ProjectRoot
    $settingsTemplate = Resolve-ProjectPath $settingsTemplateRel $script:ProjectRoot
    $addTemplate = Resolve-ProjectPath $addTemplateRel $script:ProjectRoot
    if (-not (Test-Path -LiteralPath $featuresDir -PathType Container)) { throw "Каталог фич не найден: $featuresDir" }
    if (-not (Test-Path -LiteralPath $settingsTemplate -PathType Leaf)) { throw "Шаблон настроек не найден: $settingsTemplate" }
    if (-not (Test-Path -LiteralPath $addTemplate -PathType Leaf)) { throw "Шаблон Vanessa-ADD не найден: $addTemplate" }

    $outputDir = Join-Path $script:RunDir 'reports'
    New-Item -ItemType Directory -Path (Join-Path $outputDir 'junit') -Force | Out-Null

    # Имена БЕЗ ведущей точки: VA не читает settings-файл с именем, начинающимся с точки
    # (симптом: модалка «Не удалось прочитать файл настроек JSON»).
    $settingsTmp = Join-Path $script:RunDir 'vrunner-settings.tmp.json'
    $addTmp = Join-Path $script:RunDir 'vanessa-add-params.tmp.json'
    $stdout = Join-Path $script:RunDir 'vanessa-stdout.log'
    $stderr = Join-Path $script:RunDir 'vanessa-stderr.log'

    # Библиотечные шаги VA (пакет add: открытие внешнего файла и прочие) подхватываются
    # только через КаталогиБиблиотек временного VAParams. Путь — ТОЛЬКО прямыми слешами:
    # с обратными VA каталог молча не находит и шаги остаются нераспознанными.
    $vaLibrariesDir = Join-Path $script:ToolRoot 'onescript\lib\add\features\libraries'
    if (-not (Test-Path -LiteralPath $vaLibrariesDir -PathType Container)) {
        Add-Step 'test.vanessa.libraries' 'warning' "Каталог библиотечных фич не найден: $vaLibrariesDir; шаги пакета add будут нераспознаны (поставьте пакет через opm)"
    }
    $ibConnection = '/F' + ($credentials.path -replace '\\', '/')
    $ibFileConnection = 'File="' + $credentials.path + '";'

    Add-Step 'test.plan' 'ok' "Смоук Vanessa-Automation против $($ibConnection) под '$($credentials.user)'; epf: $vanessaEpf; фичи: $featuresDir; тонкий клиент: $([bool]($ordinaryApp -eq 0))"

    $previousPath = $env:PATH
    $hadPwdVar = Test-Path Env:\RUNNER_DBPWD
    $previousPwd = if ($hadPwdVar) { $env:RUNNER_DBPWD } else { $null }
    try {
        Expand-TemplateToFile $settingsTemplate ([ordered]@{
            IB_CONNECTION = $ibConnection
            LOGIN         = $credentials.user
            V8VERSION     = $v8version
        }) $settingsTmp

        # ДанныеКлиентовТестирования: vrunner передаёт /P только тест-МЕНЕДЖЕРУ; профиль
        # «Этот клиент» VA собирает без пароля → интерактивное окно логина → таймаут.
        # Поэтому логин/пароль тест-клиента уходят в ДопПараметры временного VAParams
        # (файл живёт до выхода vrunner, затирается и удаляется в finally).
        Expand-TemplateToFile $addTemplate ([ordered]@{
            V8VERSION          = $v8version
            OUTPUT_DIR         = ($outputDir -replace '\\', '/')
            FEATURES_DIR       = ($featuresDir -replace '\\', '/')
            TESTCLIENT_TIMEOUT = [string]$testClientTimeout
            IB_FILE_CONNECTION = $ibFileConnection
            VA_LIBRARIES_DIR   = ($vaLibrariesDir -replace '\\', '/')
            LOGIN              = [string]$credentials.user
            PASSWORD           = [string]$credentials.password  # airules:allow creds-password (template value from resolved credentials, no literal secret)
        }) $addTmp

        $env:PATH = (Get-OneScriptBin) + ';' + $env:PATH
        if ($credentials.password) { $env:RUNNER_DBPWD = $credentials.password } else { $env:RUNNER_DBPWD = '' }

        $arguments = New-Object System.Collections.ArrayList
        [void]$arguments.Add('vanessa')
        [void]$arguments.Add('--settings');        [void]$arguments.Add($settingsTmp)
        [void]$arguments.Add('--vanessasettings');  [void]$arguments.Add($addTmp)
        [void]$arguments.Add('--pathvanessa');      [void]$arguments.Add($vanessaEpf)
        [void]$arguments.Add('--path');             [void]$arguments.Add($featuresDir)
        [void]$arguments.Add('--ordinaryapp');      [void]$arguments.Add([string]$ordinaryApp)
        [void]$arguments.Add('--v8version');        [void]$arguments.Add($v8version)
        [void]$arguments.Add('--workspace');        [void]$arguments.Add($script:RunDir)
        [void]$arguments.Add('--additional-keys');  [void]$arguments.Add('DisableFirstRunHelper')

        $displayCommand = (Quote-IfNeeded $vrunner) + ' ' + (($arguments | ForEach-Object { Quote-IfNeeded ([string]$_) }) -join ' ')
        Add-Step 'test.command' 'planned' ($displayCommand + '  [секрет: RUNNER_DBPWD=<hidden> в окружении + /P с кавычками во временном VAParams (затирается в finally)]')

        # Тест тоже держит базу: деплой, влезший в середину прогона Vanessa,
        # меняет конфигурацию под работающими сценариями. Лок — тот же, что у деплоя.
        # Память здесь НЕ сторожим: vrunner лишь ждёт дочерние 1cv8 и всегда
        # выглядит пустым и стоящим; остаётся таймаут (прогон длиннее деплоя).
        $guardLog = Join-Path $script:RunDir 'guard.log'
        $baseId = Get-1CBaseIdentity $target $credentials.path
        $testLock = $null
        if ($baseId) { $testLock = Enter-1CBaseLock -Target $baseId -LogPath $guardLog }
        try {
            $guard = Invoke-Guarded1C -FilePath $vrunner -ArgumentList ([string[]]$arguments) `
                -Label 'test/vrunner' -TimeoutOnly -LogPath $guardLog `
                -TimeoutMinutes ([int](Get-1CGuardSetting 'AGENT1C_TEST_TIMEOUT_MIN' 45)) `
                -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        }
        finally {
            Exit-1CBaseLock $testLock
            [void]$script:Artifacts.Add($guardLog)
        }
        if ($guard.Killed) {
            Add-Step 'test.vanessa' 'error' "Сторож снял прогон: $($guard.Reason). См. $guardLog"
            $script:ExitCode = 1
            return
        }
        $code = $guard.ExitCode

        Remove-SecretFromFiles @($stdout, $stderr, (Join-Path $outputDir 'vanessaonline.txt'), (Join-Path $outputDir 'message.txt')) $credentials.password
        [void]$script:Artifacts.Add($outputDir)
        [void]$script:Artifacts.Add($stdout)

        $statusPath = Join-Path $outputDir 'buildstatus.log'
        $statusText = ''
        if (Test-Path -LiteralPath $statusPath -PathType Leaf) { $statusText = (Get-Content -LiteralPath $statusPath -Raw -ErrorAction SilentlyContinue) }
        if ($statusText) { $statusText = $statusText.Trim() }

        if ($code -eq 0) {
            Add-Step 'test.vanessa' 'ok' "Смоук пройден (exit 0). buildstatus: '$statusText'. Отчёты: $outputDir"
        } else {
            Add-Step 'test.vanessa' 'error' "Смоук завершился с кодом $code. buildstatus: '$statusText'. Логи: $stdout / $stderr; отчёты: $outputDir"
            $script:ExitCode = $code
        }
    } finally {
        if (Test-Path -LiteralPath $settingsTmp -PathType Leaf) { Remove-Item -LiteralPath $settingsTmp -Force -ErrorAction SilentlyContinue }
        if (Test-Path -LiteralPath $addTmp -PathType Leaf) {
            # VAParams содержит пароль тест-клиента — затираем содержимое перед удалением
            try { [System.IO.File]::WriteAllText($addTmp, '{}') } catch {}
            Remove-Item -LiteralPath $addTmp -Force -ErrorAction SilentlyContinue
        }
        $env:PATH = $previousPath
        if ($hadPwdVar) { $env:RUNNER_DBPWD = $previousPwd } else { Remove-Item Env:\RUNNER_DBPWD -ErrorAction SilentlyContinue }
    }
}

try {
    $profilePath = [IO.Path]::GetFullPath($Profile)
    if (-not (Test-Path -LiteralPath $profilePath)) { throw "Профиль не найден: $profilePath" }
    $script:ProjectRoot = Split-Path -Parent $profilePath
    $script:ProfileData = Get-Content -LiteralPath $profilePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($script:ProfileData.schemaVersion -ne 1) { throw 'Неподдерживаемая версия профиля.' }
    $resultRoot = Resolve-ProjectPath $script:ProfileData.resultDir $script:ProjectRoot
    $script:RunDir = Join-Path $resultRoot ((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + $Command)
    New-Item -ItemType Directory -Path $script:RunDir -Force | Out-Null

    switch ($Command) {
        'bootstrap' { [void](Install-BslLanguageServer); Invoke-Doctor }
        'doctor' { Invoke-Doctor }
        'analyze' { Invoke-Analyze }
        'deploy' { Invoke-Deploy }
        'test' { Invoke-Test }
    }
} catch {
    $script:ExitCode = 1
    Add-Step $Command 'error' $_.Exception.Message
} finally {
    if ($script:RunDir) {
        $report = [ordered]@{
            schemaVersion = 1
            projectId = if ($script:ProfileData) { $script:ProfileData.projectId } else { $null }
            command = $Command
            apply = [bool]$Apply
            startedAtUtc = $script:StartedAt.ToString('o')
            finishedAtUtc = [DateTime]::UtcNow.ToString('o')
            exitCode = $script:ExitCode
            steps = @($script:Steps)
            warnings = @($script:Warnings)
            artifacts = @($script:Artifacts)
        }
        $reportPath = Join-Path $script:RunDir 'result.json'
        $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
        Write-Host "Отчёт: $reportPath"
    }
}

exit $script:ExitCode
