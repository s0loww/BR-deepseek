# Чтение текста запроса, параметров и вывод результатов.

function Convert-QueryParameterValue {
    param(
        [string]$RawValue
    )

    $value = $RawValue.Trim()
    if ($value.Length -ge 2 -and $value.StartsWith('"') -and $value.EndsWith('"')) {
        $value = $value.Substring(1, $value.Length - 2)
    }

    if ($value -match '^@date:(.+)$') {
        return [datetime]::Parse($matches[1].Trim())
    }
    if ($value -match '^@number:(.+)$') {
        return [decimal]::Parse($matches[1].Trim(), [System.Globalization.CultureInfo]::InvariantCulture)
    }
    if ($value -match '^@bool:(true|false)$') {
        return [bool]::Parse($matches[1])
    }

    return $value
}

function Read-ComQueryFile {
    param(
        [Parameter(Mandatory)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Файл запроса не найден: $Path"
    }

    $parameters = @{}
    $lines = New-Object System.Collections.Generic.List[string]

    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($rawLine -match '^\s*[;#]\s*@param\s+([^=]+)=(.*)$') {
            $paramName = $matches[1].Trim()
            $parameters[$paramName] = Convert-QueryParameterValue -RawValue $matches[2]
            continue
        }
        $lines.Add($rawLine) | Out-Null
    }

    $text = ($lines -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "Файл запроса пуст: $Path"
    }

    return [pscustomobject]@{
        Text = $text
        Parameters = $parameters
        SourcePath = $Path
    }
}

function Read-ComQueryParametersFile {
    param(
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return @{}
    }

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Файл параметров не найден: $Path"
    }

    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $parsed = $raw | ConvertFrom-Json
    $result = @{}

    if ($parsed -is [System.Management.Automation.PSCustomObject]) {
        $parsed.PSObject.Properties | ForEach-Object {
            $result[$_.Name] = Convert-QueryParameterValue -RawValue ([string]$_.Value)
        }
    } elseif ($parsed -is [hashtable]) {
        $parsed.GetEnumerator() | ForEach-Object {
            $result[$_.Key] = Convert-QueryParameterValue -RawValue ([string]$_.Value)
        }
    } else {
        throw "Файл параметров должен содержать JSON-объект: $Path"
    }

    return $result
}

function Merge-ComQueryParameters {
    param(
        [hashtable]$Primary,
        [hashtable]$Secondary
    )

    $merged = @{}
    if ($Secondary) {
        $Secondary.GetEnumerator() | ForEach-Object { $merged[$_.Key] = $_.Value }
    }
    if ($Primary) {
        $Primary.GetEnumerator() | ForEach-Object { $merged[$_.Key] = $_.Value }
    }
    return $merged
}

function New-ComQueryObject {
    param(
        [Parameter(Mandatory)]
        $Connection,
        [Parameter(Mandatory)]
        [string]$Text,
        [hashtable]$Parameters = @{}
    )

    if ($null -eq $Connection) {
        throw "Connection is null"
    }

    $query = $Connection.NewObject('Query')
    if ($null -eq $query) {
        throw "Failed to create Query object - NewObject returned null"
    }

    $query.Text = $Text

    foreach ($key in $Parameters.Keys) {
        $value = $Parameters[$key]
        if ($value -is [System.Collections.IEnumerable] -and -not ($value -is [string])) {
            $array = $Connection.NewObject('Array')
            foreach ($element in $value) {
                $array.Add($element) | Out-Null
            }
            $query.SetParameter($key, $array) | Out-Null
            continue
        }

        $query.SetParameter($key, $value) | Out-Null
    }

    return $query
}

function Get-ComColumnName {
    param(
        $Column
    )

    foreach ($propertyName in @('Name', 'Имя')) {
        $name = Get-ComPropertySafe -Object $Column -Name $propertyName
        if (-not [string]::IsNullOrWhiteSpace($name)) {
            return [string]$name
        }
    }

    return ''
}

function Get-ComValueTableColumns {
    param(
        $ValueTable
    )

    $columnsObject = Get-ComPropertySafe -Object $ValueTable -Name 'Columns'
    if ($null -eq $columnsObject) {
        $columnsObject = Get-ComPropertySafe -Object $ValueTable -Name 'Колонки'
    }
    if ($null -eq $columnsObject) {
        throw 'Таблица значений не содержит коллекцию колонок.'
    }

    $columns = New-Object System.Collections.Generic.List[string]
    $columnCount = Get-ComCollectionCount -Collection $columnsObject

    for ($index = 0; $index -lt $columnCount; $index++) {
        $column = Get-ComCollectionItem -Collection $columnsObject -Index $index
        $columnName = Get-ComColumnName -Column $column
        if ([string]::IsNullOrWhiteSpace($columnName)) {
            $columnName = "Column$index"
        }
        $columns.Add($columnName) | Out-Null
    }

    return @($columns.ToArray())
}

function Get-ComValueTableCell {
    param(
        $Row,
        [int]$ColumnIndex,
        [string]$ColumnName
    )

    foreach ($methodName in @('Get', 'Получить')) {
        try {
            return Invoke-ComMethod -Object $Row -Name $methodName -Arguments @($ColumnIndex)
        } catch {
            continue
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($ColumnName)) {
        try {
            return $Row.$ColumnName
        } catch {
            try {
                return Invoke-ComMethod -Object $Row -Name 'Get' -Arguments @($ColumnName)
            } catch {
                return $null
            }
        }
    }

    return $null
}

function Convert-ComValueTableRow {
    param(
        $Connection,
        $Row,
        [string[]]$ColumnNames
    )

    $values = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -lt $ColumnNames.Count; $index++) {
        $cellValue = Get-ComValueTableCell -Row $Row -ColumnIndex $index -ColumnName $ColumnNames[$index]
        $values.Add((Convert-ComValueToText -Connection $Connection -Value $cellValue)) | Out-Null
    }

    return @($values.ToArray())
}

function Invoke-ComQueryDryRun {
    param(
        [Parameter(Mandatory)]
        $Connection,
        [Parameter(Mandatory)]
        [string]$Text,
        [hashtable]$Parameters = @{},
        [int]$MaxPreviewRows = 20
    )

    $fullResult = Invoke-ComQueryApply -Connection $Connection -Text $Text -Parameters $Parameters -MaxRows 0
    $previewRows = @($fullResult.Rows | Select-Object -First $MaxPreviewRows)

    return [pscustomobject]@{
        ColumnNames = $fullResult.ColumnNames
        PreviewRows = $previewRows
        TotalRows = $fullResult.TotalRows
        Truncated = ($fullResult.TotalRows -gt $MaxPreviewRows)
        MaxPreviewRows = $MaxPreviewRows
    }
}

function Get-ComValueTableRow {
    param(
        $ValueTable,
        [int]$RowIndex
    )

    foreach ($methodName in @('Get', 'Получить')) {
        try {
            return Invoke-ComMethod -Object $ValueTable -Name $methodName -Arguments @($RowIndex)
        } catch {
            continue
        }
    }

    return Get-ComCollectionItem -Collection $ValueTable -Index $RowIndex
}

function Get-ComValueTableRowCount {
    param(
        $ValueTable
    )

    if ($null -eq $ValueTable) {
        return 0
    }

    try {
        return [int]$ValueTable.Количество()
    } catch {
    }

    try {
        return [int]$ValueTable.Count()
    } catch {
    }

    foreach ($methodName in @('Count', 'Количество')) {
        try {
            return [int](Invoke-ComMethod -Object $ValueTable -Name $methodName)
        } catch {
            continue
        }
    }

    return Get-ComCollectionCount -Collection $ValueTable
}

function Invoke-ComQueryApply {
    param(
        [Parameter(Mandatory)]
        $Connection,
        [Parameter(Mandatory)]
        [string]$Text,
        [hashtable]$Parameters = @{},
        [int]$MaxRows = 0
    )

    $query = New-ComQueryObject -Connection $Connection -Text $Text -Parameters $Parameters
    $valueTable = $query.Execute().Unload()
    $columnNames = Get-ComValueTableColumns -ValueTable $valueTable
    $rowCount = Get-ComValueTableRowCount -ValueTable $valueTable

    if ($MaxRows -gt 0 -and $rowCount -gt $MaxRows) {
        throw "Запрос вернул $rowCount строк, лимит MaxRows=$MaxRows. Увеличьте лимит или сузьте запрос."
    }

    $rows = New-Object System.Collections.Generic.List[object]
    for ($rowIndex = 0; $rowIndex -lt $rowCount; $rowIndex++) {
        $row = Get-ComValueTableRow -ValueTable $valueTable -RowIndex $rowIndex
        $values = Convert-ComValueTableRow -Connection $Connection -Row $row -ColumnNames $columnNames
        $rows.Add([pscustomobject]@{
            RowNumber = $rowIndex + 1
            Values = $values
        }) | Out-Null
    }

    return [pscustomobject]@{
        ColumnNames = $columnNames
        Rows = @($rows.ToArray())
        TotalRows = $rowCount
    }
}

function Write-ComQueryResultToLog {
    param(
        [Parameter(Mandatory)]
        [string]$LogFile,
        [Parameter(Mandatory)]
        $QueryResult,
        [Parameter(Mandatory)]
        [string]$Mode,
        [int]$MaxPreviewRows = 20
    )

    Write-ComLogLine -LogFile $LogFile -Message ''
    Write-ComLogLine -LogFile $LogFile -Message '--- QUERY RESULT ---'
    Write-ComLogLine -LogFile $LogFile -Message ("Columns: {0}" -f ($QueryResult.ColumnNames -join ' | '))
    Write-ComLogLine -LogFile $LogFile -Message ("TotalRows: {0}" -f $QueryResult.TotalRows)

    if ($Mode -eq 'DryRun') {
        Write-ComLogLine -LogFile $LogFile -Message ("PreviewRows: {0}" -f $QueryResult.PreviewRows.Count)
        if ($QueryResult.Truncated) {
            Write-ComLogLine -LogFile $LogFile -Message ("NOTE: показаны первые {0} строк. Для полного вывода запустите с -Apply." -f $MaxPreviewRows)
        }
        foreach ($row in $QueryResult.PreviewRows) {
            Write-ComLogLine -LogFile $LogFile -Message ("{0}: {1}" -f $row.RowNumber, ($row.Values -join ' | '))
        }
        return
    }

    foreach ($row in $QueryResult.Rows) {
        Write-ComLogLine -LogFile $LogFile -Message ("{0}: {1}" -f $row.RowNumber, ($row.Values -join ' | '))
    }
}

function Invoke-ComQueryRows {
    param(
        [Parameter(Mandatory)]
        $Connection,
        [Parameter(Mandatory)]
        [string]$Text,
        [hashtable]$Parameters = @{},
        [Parameter(Mandatory)]
        [string[]]$Columns
    )

    $query = New-ComQueryObject -Connection $Connection -Text $Text -Parameters $Parameters
    $selection = $query.Execute().Select()
    $rows = New-Object System.Collections.Generic.List[object]

    while ($selection.Next()) {
        $row = [ordered]@{}
        for ($index = 0; $index -lt $Columns.Count; $index++) {
            $row[$Columns[$index]] = $selection.Get($index)
        }
        $rows.Add([pscustomobject]$row) | Out-Null
    }

    return @($rows.ToArray())
}

function Get-ComQueryFileList {
    param(
        [string]$QueryDirectory,
        [string[]]$QueryFiles
    )

    $result = New-Object System.Collections.Generic.List[string]

    if ($QueryFiles) {
        foreach ($path in $QueryFiles) {
            if (-not (Test-Path -LiteralPath $path)) {
                throw "Файл запроса не найден: $path"
            }
            $result.Add((Resolve-Path -LiteralPath $path).Path) | Out-Null
        }
        return ,$result.ToArray()
    }

    if ([string]::IsNullOrWhiteSpace($QueryDirectory)) {
        throw 'Укажите -QueryDirectory или -QueryFiles.'
    }

    if (-not (Test-Path -LiteralPath $QueryDirectory)) {
        throw "Каталог запросов не найден: $QueryDirectory"
    }

    Get-ChildItem -LiteralPath $QueryDirectory -File -Filter '*.sql' |
        Sort-Object Name |
        ForEach-Object { $result.Add($_.FullName) | Out-Null }

    if ($result.Count -eq 0) {
        throw "В каталоге нет .sql файлов: $QueryDirectory"
    }

    return ,$result.ToArray()
}
