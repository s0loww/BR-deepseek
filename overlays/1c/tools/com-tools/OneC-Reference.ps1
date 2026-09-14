# Работа со ссылками и объектами 1С через COM.

function Convert-ComText {
    param($Value)

    if ($null -eq $Value) {
        return ''
    }

    return ([string]$Value).Trim()
}

function Get-ComReferenceUuid {
    param(
        $Connection,
        $Value
    )

    if ($null -eq $Value) {
        return ''
    }

    try {
        return Convert-ComText $Connection.XMLString($Value)
    } catch {
        return ''
    }
}

function Get-ComReferencePresentation {
    param(
        $Connection,
        $Value
    )

    if ($null -eq $Value) {
        return ''
    }

    $query = New-ComQueryObject -Connection $Connection -Text @'
ВЫБРАТЬ
    ПРЕДСТАВЛЕНИЕ(&Значение) КАК Представление
'@ -Parameters @{ Значение = $Value }

    $selection = $query.Execute().Select()
    if (-not $selection.Next()) {
        return ''
    }

    return Convert-ComText $selection.Get(0)
}

function Get-ComObjectFromReference {
    param(
        $Reference
    )

    if ($null -eq $Reference) {
        return $null
    }

    foreach ($methodName in @('ПолучитьОбъект', 'GetObject')) {
        try {
            return Invoke-ComMethod -Object $Reference -Name $methodName
        } catch {
            continue
        }
    }

    throw 'Не удалось получить объект по ссылке.'
}

function Test-ComReferenceFilled {
    param(
        $Connection,
        $Value
    )

    if ($null -eq $Value) {
        return $false
    }

    $uuid = Get-ComReferenceUuid -Connection $Connection -Value $Value
    return -not [string]::IsNullOrWhiteSpace($uuid)
}

function Find-ComDocumentReference {
    param(
        $Connection,
        [Parameter(Mandatory)]
        [string]$DocumentType,
        [Parameter(Mandatory)]
        [string]$Number,
        [Parameter(Mandatory)]
        [datetime]$Date
    )

    $rows = Invoke-ComQueryRows -Connection $Connection -Text @"
ВЫБРАТЬ ПЕРВЫЕ 1
    Док.Ссылка КАК Ссылка,
    Док.Номер КАК Номер,
    Док.Дата КАК Дата,
    Док.Проведен КАК Проведен,
    Док.ПометкаУдаления КАК ПометкаУдаления
ИЗ
    Документ.$DocumentType КАК Док
ГДЕ
    Док.Номер = &Номер
    И Док.Дата = &Дата
"@ -Parameters @{
        Номер = $Number
        Дата = $Date
    } -Columns @('Reference', 'Number', 'Date', 'Posted', 'DeletionMark')

    if ($rows.Count -eq 0) {
        return $null
    }

    return $rows[0]
}
