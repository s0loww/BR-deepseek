# Экспорт результатов COM-скриптов в CSV и артефакты.

function New-ComOutputPath {
    param(
        [Parameter(Mandatory)]
        [string]$OutputDir,
        [Parameter(Mandatory)]
        [string]$FilePrefix,
        [string]$Extension = '.csv',
        [datetime]$Timestamp = (Get-Date)
    )

    if (-not (Test-Path -LiteralPath $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    }

    $fileName = '{0}_{1}{2}' -f $FilePrefix, $Timestamp.ToString('yyyyMMdd_HHmmss'), $Extension
    return Join-Path $OutputDir $fileName
}

function Export-ComResultCsv {
    param(
        [AllowEmptyCollection()]
        [object[]]$Rows = @(),
        [Parameter(Mandatory)]
        [string]$Path,
        [string]$Delimiter = ';'
    )

    if ($null -eq $Rows -or $Rows.Count -eq 0) {
        return $null
    }

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $Rows | Export-Csv -LiteralPath $Path -Delimiter $Delimiter -NoTypeInformation -Encoding UTF8
    return $Path
}
