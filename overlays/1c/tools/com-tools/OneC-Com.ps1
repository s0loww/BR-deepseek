# Безопасные обёртки для вызовов COM-объектов 1С.

function Invoke-ComMethod {
    param(
        $Object,
        [Parameter(Mandatory)]
        [string]$Name,
        [object[]]$Arguments = @()
    )

    $result = $Object.GetType().InvokeMember(
        $Name,
        [System.Reflection.BindingFlags]::InvokeMethod,
        $null,
        $Object,
        $Arguments
    )
    Write-Output -NoEnumerate $result
}

function Get-ComPropertySafe {
    param(
        $Object,
        [Parameter(Mandatory)]
        [string]$Name
    )

    try {
        $result = $Object.GetType().InvokeMember(
            $Name,
            [System.Reflection.BindingFlags]::GetProperty,
            $null,
            $Object,
            @()
        )
        Write-Output -NoEnumerate $result
    } catch {
        return $null
    }
}

function Get-ComCollectionCount {
    param(
        $Collection
    )

    if ($null -eq $Collection) {
        return 0
    }

    foreach ($methodName in @('Count', 'Количество')) {
        try {
            return [int](Invoke-ComMethod -Object $Collection -Name $methodName)
        } catch {
            continue
        }
    }

    $countProperty = Get-ComPropertySafe -Object $Collection -Name 'Count'
    if ($null -ne $countProperty) {
        return [int]$countProperty
    }

    if ($Collection -is [System.Array]) {
        return $Collection.Length
    }

    return @($Collection).Count
}

function Get-ComCollectionItem {
    param(
        $Collection,
        [int]$Index
    )

    if ($null -eq $Collection) {
        throw "Не удалось получить элемент коллекции с индексом $Index."
    }

    try {
        return $Collection.Get($Index)
    } catch {
    }

    foreach ($methodName in @('Get', 'Получить')) {
        try {
            return Invoke-ComMethod -Object $Collection -Name $methodName -Arguments @($Index)
        } catch {
            continue
        }
    }

    if ($Collection -is [System.Array]) {
        return $Collection[$Index]
    }

    throw "Не удалось получить элемент коллекции с индексом $Index."
}

function Convert-ComValueToText {
    param(
        $Connection,
        $Value
    )

    if ($null -eq $Value) {
        return ''
    }

    $valueType = $Value.GetType()
    if ($valueType.FullName -eq 'System.__ComObject') {
        try {
            return [string]$Connection.String($Value)
        } catch {
            return '[COM]'
        }
    }

    if ($Value -is [datetime]) {
        return $Value.ToString('yyyy-MM-ddTHH:mm:ss')
    }

    return [string]$Value
}
