# Единый контракт режима записи: -Apply по умолчанию DryRun, legacy-алиасы сохранены.

function Resolve-ComApplyMode {
    param(
        [switch]$Apply,
        [switch]$Write,
        [switch]$WhatIf,
        [switch]$DryRun,
        [ValidateSet('DryRun', 'Apply')]
        [string]$DefaultMode = 'DryRun'
    )

    if ($Apply -or $Write) {
        return $true
    }

    if ($WhatIf) {
        return $false
    }

    if ($DryRun) {
        return $false
    }

    return ($DefaultMode -eq 'Apply')
}

function Get-ComRunModeName {
    param(
        [Parameter(Mandatory)]
        [bool]$ApplyMode
    )

    if ($ApplyMode) {
        return 'Apply'
    }

    return 'DryRun'
}

function Write-ComApplyModeDeprecation {
    param(
        [string]$LegacySwitch
    )

    if ([string]::IsNullOrWhiteSpace($LegacySwitch)) {
        return
    }

    Write-Warning "Параметр -$LegacySwitch устарел, используйте -Apply."
}
