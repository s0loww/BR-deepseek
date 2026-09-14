# db-load-cf v1.0 — Load 1C configuration from CF file
# Source: https://github.com/Nikolay-Shirokov/cc-1c-skills
<#
.SYNOPSIS
    Загрузка конфигурации 1С из CF-файла

.DESCRIPTION
    Загружает конфигурацию из бинарного CF-файла в информационную базу.
    Поддерживает загрузку расширений.

.PARAMETER V8Path
    Путь к каталогу bin платформы или к 1cv8.exe

.PARAMETER InfoBasePath
    Путь к файловой информационной базе

.PARAMETER InfoBaseServer
    Сервер 1С (для серверной базы)

.PARAMETER InfoBaseRef
    Имя базы на сервере

.PARAMETER UserName
    Имя пользователя 1С

.PARAMETER PasswordEnv
    Имя переменной окружения, содержащей пароль пользователя.
    Секреты не передаются аргументами командной строки (script-contract).

.PARAMETER InputFile
    Путь к CF-файлу для загрузки

.PARAMETER Extension
    Загрузить как расширение

.PARAMETER AllExtensions
    Загрузить все расширения из архива

.PARAMETER Apply
    Применить загрузку. Без этого флага скрипт работает в режиме DryRun:
    показывает команду, которая была бы выполнена, и завершается без изменений.

.EXAMPLE
    .\db-load-cf.ps1 -InfoBasePath "<infobase-dir>" -InputFile "config.cf"

.EXAMPLE
    .\db-load-cf.ps1 -InfoBasePath "<infobase-dir>" -InputFile "ext.cfe" -Extension "МоёРасширение" -Apply
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$V8Path,

    [Parameter(Mandatory=$false)]
    [string]$InfoBasePath,

    [Parameter(Mandatory=$false)]
    [string]$InfoBaseServer,

    [Parameter(Mandatory=$false)]
    [string]$InfoBaseRef,

    [Parameter(Mandatory=$false)]
    [string]$UserName,

    [Parameter(Mandatory=$false)]
    [string]$PasswordEnv,

    [Parameter(Mandatory=$true)]
    [string]$InputFile,

    [Parameter(Mandatory=$false)]
    [string]$Extension,

    [Parameter(Mandatory=$false)]
    [switch]$AllExtensions,

    [Parameter(Mandatory=$false)]
    [switch]$Apply
)

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Resolve password from environment (script-contract: no secrets in CLI args) ---
$Password = $null
if ($PasswordEnv) {
    $Password = [Environment]::GetEnvironmentVariable($PasswordEnv)
    if (-not $Password) {
        if ($Apply) {
            Write-Host "Error: environment variable '$PasswordEnv' is not set or empty" -ForegroundColor Red
            exit 1
        }
        Write-Host "Warning: environment variable '$PasswordEnv' is not set - dry run continues; -Apply will fail until it is set" -ForegroundColor Yellow
    }
}

# --- Resolve V8Path ---
if (-not $V8Path) {
    $found = Get-ChildItem "C:\Program Files\1cv8\*\bin\1cv8.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) {
        $V8Path = $found.FullName
    } else {
        Write-Host "Error: 1cv8.exe not found. Specify -V8Path" -ForegroundColor Red
        exit 1
    }
} elseif (Test-Path $V8Path -PathType Container) {
    $V8Path = Join-Path $V8Path "1cv8.exe"
}

if (-not (Test-Path $V8Path)) {
    Write-Host "Error: 1cv8.exe not found at $V8Path" -ForegroundColor Red
    exit 1
}

# --- Validate connection ---
if (-not $InfoBasePath -and (-not $InfoBaseServer -or -not $InfoBaseRef)) {
    Write-Host "Error: specify -InfoBasePath or -InfoBaseServer + -InfoBaseRef" -ForegroundColor Red
    exit 1
}

# --- Validate input file ---
if (-not (Test-Path $InputFile)) {
    Write-Host "Error: input file not found: $InputFile" -ForegroundColor Red
    exit 1
}

# --- Temp dir ---
$tempDir = Join-Path $env:TEMP "db_load_cf_$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    # --- Build arguments ---
    $arguments = @("DESIGNER")

    if ($InfoBaseServer -and $InfoBaseRef) {
        $arguments += "/S", "`"$InfoBaseServer/$InfoBaseRef`""
    } else {
        $arguments += "/F", "`"$InfoBasePath`""
    }

    if ($UserName) { $arguments += "/N`"$UserName`"" }
    if ($Password) { $arguments += "/P`"$Password`"" }  # airules:allow creds-echo (not echoed; masked before Write-Host)

    $arguments += "/LoadCfg", "`"$InputFile`""

    # --- Extensions ---
    if ($Extension) {
        $arguments += "-Extension", "`"$Extension`""
    } elseif ($AllExtensions) {
        $arguments += "-AllExtensions"
    }

    # --- Output ---
    $outFile = Join-Path $tempDir "load_cf_log.txt"
    $arguments += "/Out", "`"$outFile`""
    $arguments += "/DisableStartupDialogs"

    # --- DryRun gate (script-contract: mutations only under explicit -Apply) ---
    $argDisplay = $arguments -join ' '
    if ($Password) { $argDisplay = $argDisplay.Replace($Password, '***') }
    if (-not $Apply) {
        Write-Host "DRY RUN: would run 1cv8.exe $argDisplay" -ForegroundColor Yellow
        Write-Host "No changes made. Re-run with -Apply to load the configuration."
        exit 0
    }

    # --- Execute ---
    Write-Host "Running: 1cv8.exe $argDisplay"
    $process = Start-Process -FilePath $V8Path -ArgumentList $arguments -NoNewWindow -Wait -PassThru
    $exitCode = $process.ExitCode

    # --- Result ---
    if ($exitCode -eq 0) {
        Write-Host "Configuration loaded successfully from: $InputFile" -ForegroundColor Green
    } else {
        Write-Host "Error loading configuration (code: $exitCode)" -ForegroundColor Red
    }

    if (Test-Path $outFile) {
        $logContent = Get-Content $outFile -Raw -ErrorAction SilentlyContinue
        if ($logContent) {
            Write-Host "--- Log ---"
            Write-Host $logContent
            Write-Host "--- End ---"
        }
    }

    exit $exitCode

} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
