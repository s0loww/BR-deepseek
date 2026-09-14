# Единая точка подключения библиотек com-tools.
# Dot-source этот файл один раз — все lib-модули загрузятся в текущую область.

$script:ComToolsLibDir = $PSScriptRoot
$script:ComToolsRoot = Split-Path -Parent $PSScriptRoot

$script:ComToolsModuleNames = @(
    'OneC-Env.ps1',
    'OneC-Connect.ps1',
    'OneC-Com.ps1',
    'OneC-Query.ps1',
    'OneC-Reference.ps1',
    'OneC-Export.ps1',
    'OneC-Params.ps1'
)

function Get-ComToolsRoot {
    return $script:ComToolsRoot
}

function Import-ComToolsLib {
    param(
        [string]$LibDir = $script:ComToolsLibDir
    )

    if (Get-Command Read-ComEnvFile -ErrorAction SilentlyContinue) {
        return $LibDir
    }

    foreach ($moduleName in $script:ComToolsModuleNames) {
        $modulePath = Join-Path $LibDir $moduleName
        if (-not (Test-Path -LiteralPath $modulePath)) {
            throw "Модуль com-tools не найден: $modulePath"
        }
        . $modulePath
    }

    return $LibDir
}

foreach ($moduleName in $script:ComToolsModuleNames) {
    $modulePath = Join-Path $script:ComToolsLibDir $moduleName
    if (-not (Test-Path -LiteralPath $modulePath)) {
        throw "Модуль com-tools не найден: $modulePath"
    }
    . $modulePath
}

function Initialize-ComToolsSession {
    param(
        [Parameter(Mandatory)]
        [string]$EnvPath,
        [Parameter(Mandatory)]
        [string]$Profile,
        [string]$ScriptName,
        [string]$LogPath,
        [string]$LibDir
    )

    $ErrorActionPreference = 'Stop'
    $OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    if ($LibDir) {
        Import-ComToolsLib -LibDir $LibDir | Out-Null
    }

    $toolsRoot = Get-ComToolsRoot
    $projectRoot = Split-Path -Parent $toolsRoot
    $settings = Read-ComEnvFile -Path $EnvPath
    $profileSettings = Get-ComProfileSettings -Settings $settings -Profile $Profile
    $startedAt = Get-Date
    $logFile = Resolve-ComLogPath -Settings $settings -OverridePath $LogPath -ScriptName $ScriptName -ProjectRoot $projectRoot -Timestamp $startedAt
    $connectionInfo = Connect-ComInfobase -ProfileSettings $profileSettings

    return [pscustomobject]@{
        Settings = $settings
        ProfileSettings = $profileSettings
        Profile = $Profile
        EnvPath = $EnvPath
        ProjectRoot = $projectRoot
        ToolsRoot = $toolsRoot
        StartedAt = $startedAt
        LogFile = $logFile
        ConnectionInfo = $connectionInfo
    }
}

function Complete-ComToolsSession {
    param(
        $Session,
        [string]$Status = 'OK',
        [string]$ErrorMessage = ''
    )

    if ($Session.LogFile) {
        Write-ComLogLine -LogFile $Session.LogFile -Message ''
        Write-ComLogLine -LogFile $Session.LogFile -Message ("FinishedAt: {0}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
        Write-ComLogLine -LogFile $Session.LogFile -Message ("Status: {0}" -f $Status)
        if ($ErrorMessage) {
            Write-ComLogLine -LogFile $Session.LogFile -Message ("Error: {0}" -f $ErrorMessage)
        }
    }

    if ($null -ne $Session.ConnectionInfo) {
        Disconnect-ComInfobase -ConnectionInfo $Session.ConnectionInfo
    }
}
