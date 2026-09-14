# Подключение к информационной базе 1С через V83.COMConnector.

function Get-ComConnectionMode {
    param(
        [Parameter(Mandatory)]
        [hashtable]$ProfileSettings
    )

    $mode = $null
    if ($ProfileSettings.ContainsKey('Mode')) {
        $mode = [string]$ProfileSettings['Mode']
    }

    if ([string]::IsNullOrWhiteSpace($mode)) {
        if ($ProfileSettings.ContainsKey('Path') -and $ProfileSettings['Path']) {
            return 'File'
        }
        if ($ProfileSettings.ContainsKey('Host') -and $ProfileSettings['Host'] -and
            $ProfileSettings.ContainsKey('Ref') -and $ProfileSettings['Ref']) {
            return 'Server'
        }
        throw 'Не удалось определить режим подключения: укажите Mode=File|Server|Auto или Path, либо Host+Ref.'
    }

    return $mode
}

function Build-ComConnectionString {
    param(
        [Parameter(Mandatory)]
        [hashtable]$ProfileSettings
    )

    $login = $ProfileSettings['Login']
    $secret = $ProfileSettings['Pass']
    $mode = (Get-ComConnectionMode -ProfileSettings $ProfileSettings).ToUpperInvariant()

    switch ($mode) {
        'FILE' {
            if (-not $ProfileSettings.ContainsKey('Path') -or [string]::IsNullOrWhiteSpace($ProfileSettings['Path'])) {
                throw 'Для Mode=File требуется параметр Path в секции профиля.'
            }
            return 'File="' + $ProfileSettings['Path'] + '";Usr="' + $login + '";Pwd="' + $secret + '";'
        }
        'SERVER' {
            if (-not $ProfileSettings.ContainsKey('Host') -or [string]::IsNullOrWhiteSpace($ProfileSettings['Host']) -or
                -not $ProfileSettings.ContainsKey('Ref') -or [string]::IsNullOrWhiteSpace($ProfileSettings['Ref'])) {
                throw 'Для Mode=Server требуются параметры Host и Ref в секции профиля.'
            }
            return 'Srvr="' + $ProfileSettings['Host'] + '";Ref="' + $ProfileSettings['Ref'] +
                '";Usr="' + $login + '";Pwd="' + $secret + '";'
        }
        'AUTO' {
            if ($ProfileSettings.ContainsKey('Path') -and $ProfileSettings['Path']) {
                $fileSettings = @{}
                $ProfileSettings.GetEnumerator() | ForEach-Object { $fileSettings[$_.Key] = $_.Value }
                $fileSettings['Mode'] = 'File'
                return Build-ComConnectionString -ProfileSettings $fileSettings
            }
            if ($ProfileSettings.ContainsKey('Host') -and $ProfileSettings['Host'] -and
                $ProfileSettings.ContainsKey('Ref') -and $ProfileSettings['Ref']) {
                $serverSettings = @{}
                $ProfileSettings.GetEnumerator() | ForEach-Object { $serverSettings[$_.Key] = $_.Value }
                $serverSettings['Mode'] = 'Server'
                return Build-ComConnectionString -ProfileSettings $serverSettings
            }
            throw 'Для Mode=Auto требуется Path или Host+Ref.'
        }
        default {
            throw "Неизвестный Mode=$mode. Допустимо: File, Server, Auto."
        }
    }
}

function Connect-ComInfobase {
    param(
        [Parameter(Mandatory)]
        [hashtable]$ProfileSettings
    )

    $connectionString = Build-ComConnectionString -ProfileSettings $ProfileSettings
    $mode = Get-ComConnectionMode -ProfileSettings $ProfileSettings
    $connector = New-Object -ComObject 'V83.COMConnector'

    try {
        $connection = $connector.Connect($connectionString)
    } catch {
        throw "Ошибка COM-подключения (Mode=$mode): $($_.Exception.Message)"
    }

    if ($null -eq $connection) {
        throw "Ошибка COM-подключения (Mode=$mode): Connection вернул null. Проверьте путь базы, логин и пароль, а также что 1С не заблокирована сеансом."
    }

    return [pscustomobject]@{
        Connection = $connection
        ConnectionString = $connectionString
        Mode = $mode
    }
}

function Disconnect-ComInfobase {
    param(
        $ConnectionInfo
    )

    if ($null -ne $ConnectionInfo) {
        $ConnectionInfo.Connection = $null
    }

    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
