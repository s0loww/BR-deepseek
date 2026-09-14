# Общие функции чтения .env и разрешения путей логов для COM-скриптов.

function Read-ComEnvFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Env-файл не найден: $Path"
    }

    $result = @{}
    $section = $null

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if ($line.Length -eq 0 -or $line.StartsWith('#') -or $line.StartsWith(';')) {
            continue
        }

        if ($line -match '^\[(.+)\]$') {
            $section = $matches[1]
            if (-not $result.ContainsKey($section)) {
                $result[$section] = @{}
            }
            continue
        }

        if ($section -and $line -match '^([^=]+?)\s*=\s*(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $result[$section][$key] = $value
        }
    }

    return $result
}

function Get-ComProfileSettings {
    param(
        [Parameter(Mandatory)]
        [hashtable]$Settings,
        [Parameter(Mandatory)]
        [string]$Profile
    )

    if (-not $Settings.ContainsKey($Profile)) {
        throw "В env отсутствует секция [$Profile]."
    }

    $profileSettings = $Settings[$Profile]
    foreach ($requiredKey in @('Login', 'Pass')) {
        if (-not $profileSettings.ContainsKey($requiredKey) -or [string]::IsNullOrWhiteSpace($profileSettings[$requiredKey])) {
            throw "В секции [$Profile] не задан обязательный параметр $requiredKey."
        }
    }

    return $profileSettings
}

function Resolve-ComLogPath {
    param(
        [hashtable]$Settings,
        [string]$OverridePath,
        [Parameter(Mandatory)]
        [string]$ScriptName,
        [Parameter(Mandatory)]
        [string]$ProjectRoot,
        [datetime]$Timestamp = (Get-Date)
    )

    $stamp = $Timestamp.ToString('yyyyMMdd_HHmmss')
    $defaultFileName = "${ScriptName}_${stamp}.log"

    if ($OverridePath) {
        if ([System.IO.Path]::HasExtension($OverridePath)) {
            $logFile = $OverridePath
        } else {
            $logFile = Join-Path $OverridePath $defaultFileName
        }
    } elseif ($Settings.ContainsKey('COM') -and $Settings['COM'].ContainsKey('LogPath') -and $Settings['COM']['LogPath']) {
        $baseDir = $Settings['COM']['LogPath']
        $logFile = Join-Path $baseDir $defaultFileName
    } else {
        $logFile = Join-Path (Join-Path $ProjectRoot 'var\com-tools-logs') $defaultFileName
    }

    $logDir = Split-Path -Parent $logFile
    if (-not (Test-Path -LiteralPath $logDir)) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }

    return $logFile
}

function Write-ComLogLine {
    param(
        [Parameter(Mandatory)]
        [string]$LogFile,
        [AllowEmptyString()]
        [string]$Message = ''
    )

    Add-Content -LiteralPath $LogFile -Value $Message -Encoding UTF8
}

function Write-ComLogHeader {
    param(
        [Parameter(Mandatory)]
        [string]$LogFile,
        [Parameter(Mandatory)]
        [hashtable]$Meta
    )

    Write-ComLogLine -LogFile $LogFile -Message ('=' * 80)
    foreach ($key in ($Meta.Keys | Sort-Object)) {
        Write-ComLogLine -LogFile $LogFile -Message ("{0}: {1}" -f $key, $Meta[$key])
    }
    Write-ComLogLine -LogFile $LogFile -Message ('=' * 80)
}
