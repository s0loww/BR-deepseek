# role-compile v1.1 — Compile a 1C role from JSON DSL
# Restored per dsl-reference.md (the original cc-1c-skills compiler was not ported).
<#
.SYNOPSIS
    Компиляция роли 1С из JSON DSL в XML (descriptor + Rights.xml)

.DESCRIPTION
    Читает JSON-описание роли (формат — tools/1c-role-compile/dsl-reference.md):
    пресеты @view/@edit, явные права, переопределения, RLS-ограничения, шаблоны
    ограничений, русские синонимы типов и прав. Генерирует:
      <RolesDir>/<Name>.xml           — descriptor метаданных (UUID сохраняется,
                                        если файл уже существует)
      <RolesDir>/<Name>/Ext/Rights.xml — права роли
    Регистрацию <Role> в Configuration.xml скрипт НЕ выполняет — только
    напоминает о ней.

.PARAMETER DslPath
    Путь к JSON-файлу описания роли

.PARAMETER RolesDir
    Каталог Roles/ выгрузки конфигурации (целевое место генерации)

.PARAMETER Apply
    Применить генерацию. Без этого флага скрипт работает в режиме DryRun:
    показывает план (файлы, объекты, права, предупреждения) и завершается
    без изменений.

.EXAMPLE
    .\role-compile.ps1 -DslPath role.json -RolesDir "<workspace-dir>\cfsrc\Roles"

.EXAMPLE
    .\role-compile.ps1 -DslPath role.json -RolesDir "<workspace-dir>\cfsrc\Roles" -Apply
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$DslPath,

    [Parameter(Mandatory)]
    [string]$RolesDir,

    [Parameter(Mandatory=$false)]
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- 1. Translation tables (Russian -> English), per dsl-reference.md ---

$typeMap = @{
    "Справочник" = "Catalog"; "Документ" = "Document"
    "РегистрСведений" = "InformationRegister"; "РегистрНакопления" = "AccumulationRegister"
    "РегистрБухгалтерии" = "AccountingRegister"; "РегистрРасчета" = "CalculationRegister"
    "Константа" = "Constant"; "ПланСчетов" = "ChartOfAccounts"
    "ПланВидовХарактеристик" = "ChartOfCharacteristicTypes"
    "ПланВидовРасчета" = "ChartOfCalculationTypes"; "ПланОбмена" = "ExchangePlan"
    "БизнесПроцесс" = "BusinessProcess"; "Задача" = "Task"
    "Обработка" = "DataProcessor"; "Отчет" = "Report"
    "ОбщаяФорма" = "CommonForm"; "ОбщаяКоманда" = "CommonCommand"
    "Подсистема" = "Subsystem"; "КритерийОтбора" = "FilterCriterion"
    "ЖурналДокументов" = "DocumentJournal"; "Последовательность" = "Sequence"
    "ВебСервис" = "WebService"; "HTTPСервис" = "HTTPService"
    "СервисИнтеграции" = "IntegrationService"; "ПараметрСеанса" = "SessionParameter"
    "ОбщийРеквизит" = "CommonAttribute"; "Конфигурация" = "Configuration"
    "Перечисление" = "Enum"
}

$nestedTypeMap = @{
    "Реквизит" = "Attribute"; "СтандартныйРеквизит" = "StandardAttribute"
    "ТабличнаяЧасть" = "TabularSection"; "Измерение" = "Dimension"
    "Ресурс" = "Resource"; "Команда" = "Command"
    "РеквизитАдресации" = "AddressingAttribute"
}

$rightMap = @{
    "Чтение" = "Read"; "Добавление" = "Insert"; "Изменение" = "Update"
    "Удаление" = "Delete"; "Просмотр" = "View"; "Редактирование" = "Edit"
    "ВводПоСтроке" = "InputByString"; "Проведение" = "Posting"
    "ОтменаПроведения" = "UndoPosting"; "Использование" = "Use"
    "Получение" = "Get"; "Установка" = "Set"; "Старт" = "Start"
    "Выполнение" = "Execute"; "УправлениеИтогами" = "TotalsControl"
    "ИнтерактивноеДобавление" = "InteractiveInsert"
    "ИнтерактивнаяПометкаУдаления" = "InteractiveSetDeletionMark"
    "ИнтерактивноеСнятиеПометкиУдаления" = "InteractiveClearDeletionMark"
    "ИнтерактивноеУдаление" = "InteractiveDelete"
    "ИнтерактивноеУдалениеПомеченных" = "InteractiveDeleteMarked"
    "ИнтерактивноеПроведение" = "InteractivePosting"
    "ИнтерактивноеПроведениеНеоперативное" = "InteractivePostingRegular"
    "ИнтерактивнаяОтменаПроведения" = "InteractiveUndoPosting"
    "ИнтерактивноеИзменениеПроведенных" = "InteractiveChangeOfPosted"
    "ИнтерактивныйСтарт" = "InteractiveStart"
    "ИнтерактивнаяАктивация" = "InteractiveActivate"
    "ИнтерактивноеВыполнение" = "InteractiveExecute"
    "Администрирование" = "Administration"
    "АдминистрированиеДанных" = "DataAdministration"
    "ТонкийКлиент" = "ThinClient"; "ТолстыйКлиент" = "ThickClient"
    "ВебКлиент" = "WebClient"; "МобильныйКлиент" = "MobileClient"
    "ВнешнееСоединение" = "ExternalConnection"; "Вывод" = "Output"
    "СохранениеДанныхПользователя" = "SaveUserData"
}

# --- 2. Presets, per dsl-reference.md ---

$presetView = @{}
foreach ($t in @("Catalog","ExchangePlan","Document","ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes","BusinessProcess","Task")) {
    $presetView[$t] = @("Read","View","InputByString")
}
foreach ($t in @("InformationRegister","AccumulationRegister","AccountingRegister","CalculationRegister","Constant","DocumentJournal")) {
    $presetView[$t] = @("Read","View")
}
$presetView["Sequence"] = @("Read")
foreach ($t in @("CommonForm","CommonCommand","Subsystem","FilterCriterion","CommonAttribute")) {
    $presetView[$t] = @("View")
}
foreach ($t in @("DataProcessor","Report")) { $presetView[$t] = @("Use","View") }
$presetView["SessionParameter"] = @("Get")
$presetView["Configuration"] = @("ThinClient","WebClient","Output","SaveUserData","MainWindowModeNormal")

$presetEdit = @{}
foreach ($t in @("Catalog","ExchangePlan","ChartOfAccounts","ChartOfCharacteristicTypes","ChartOfCalculationTypes")) {
    $presetEdit[$t] = @("Read","Insert","Update","Delete","View","Edit","InputByString","InteractiveInsert","InteractiveSetDeletionMark","InteractiveClearDeletionMark")
}
$presetEdit["Document"] = @("Read","Insert","Update","Delete","View","Edit","InputByString","Posting","UndoPosting","InteractiveInsert","InteractiveSetDeletionMark","InteractiveClearDeletionMark","InteractivePosting","InteractivePostingRegular","InteractiveUndoPosting","InteractiveChangeOfPosted")
$presetEdit["BusinessProcess"] = @("Read","Insert","Update","Delete","View","Edit","InputByString","Start","InteractiveInsert","InteractiveSetDeletionMark","InteractiveClearDeletionMark","InteractiveActivate","InteractiveStart")
$presetEdit["Task"] = @("Read","Insert","Update","Delete","View","Edit","InputByString","Execute","InteractiveInsert","InteractiveSetDeletionMark","InteractiveClearDeletionMark","InteractiveActivate","InteractiveExecute")
foreach ($t in @("InformationRegister","AccumulationRegister","AccountingRegister","Constant")) {
    $presetEdit[$t] = @("Read","Update","View","Edit")
}
$presetEdit["DocumentJournal"] = @("Read","View")
$presetEdit["Sequence"] = @("Read","Update")
$presetEdit["SessionParameter"] = @("Get","Set")
$presetEdit["CommonAttribute"] = @("View","Edit")

$presets = @{ "view" = $presetView; "edit" = $presetEdit }

# Types that cannot carry rights in a role, per dsl-reference.md
$noRightsTypes = @("Enum","CommonModule","DefinedType","CommonPicture","CommonTemplate","Language","FunctionalOption","FunctionalOptionsParameter","EventSubscription","ScheduledJob","StyleItem")

$script:warnings = @()
$script:errors = @()

function Add-Warn { param([string]$msg) $script:warnings += $msg }
function Add-Err  { param([string]$msg) $script:errors += $msg }

function Translate-Right {
    param([string]$name)
    $n = $name.Trim()
    if ($rightMap.ContainsKey($n)) { return $rightMap[$n] }
    return $n
}

function Translate-ObjectName {
    # Translate type segments (1st, and 3rd for nested) of a dot-path name.
    param([string]$name)
    $parts = $name.Split(".")
    if ($parts.Count -ge 1 -and $typeMap.ContainsKey($parts[0])) { $parts[0] = $typeMap[$parts[0]] }
    if ($parts.Count -ge 3 -and $nestedTypeMap.ContainsKey($parts[2])) { $parts[2] = $nestedTypeMap[$parts[2]] }
    return ($parts -join ".")
}

function Resolve-Preset {
    param([string]$objName, [string]$presetName)
    $type = $objName.Split(".")[0]
    if ($objName.Split(".").Count -ge 3) {
        Add-Warn "${objName}: presets are not applicable to nested objects (View/Edit only) - preset '@$presetName' ignored"
        return @()
    }
    if (-not $presets.ContainsKey($presetName)) {
        Add-Err "${objName}: unknown preset '@$presetName' (available: @view, @edit)"
        return @()
    }
    $table = $presets[$presetName]
    if (-not $table.ContainsKey($type)) {
        $available = @()
        foreach ($p in $presets.Keys) { if ($presets[$p].ContainsKey($type)) { $available += "@$p" } }
        $hint = if ($available.Count -gt 0) { " (available for ${type}: $($available -join ', '))" } else { " (no presets for '$type' - use explicit rights)" }
        Add-Warn "${objName}: preset '@$presetName' is not defined for type '$type'$hint - skipped"
        return @()
    }
    return $table[$type]
}

# Build one normalized object entry: name + ordered rights (name -> @{value; rls})
function New-RoleObject {
    param([string]$name)
    return [pscustomobject]@{
        Name   = $name
        Rights = New-Object System.Collections.Specialized.OrderedDictionary
    }
}

function Set-Right {
    param($roleObj, [string]$rightName, [bool]$value)
    $r = Translate-Right $rightName
    if ($roleObj.Rights.Contains($r)) {
        $roleObj.Rights[$r].value = $value
    } else {
        $roleObj.Rights.Add($r, @{ value = $value; rls = $null })
    }
}

# --- 3. Read and normalize the DSL ---

if (-not (Test-Path $DslPath)) {
    Write-Host "Error: DSL file not found: $DslPath" -ForegroundColor Red
    exit 1
}

try {
    $dsl = Get-Content -Path $DslPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Write-Host "Error: cannot parse JSON: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

if (-not $dsl.name) {
    Write-Host "Error: DSL field 'name' is required" -ForegroundColor Red
    exit 1
}

$roleName = [string]$dsl.name
$synonym  = if ($dsl.PSObject.Properties["synonym"] -and $dsl.synonym) { [string]$dsl.synonym } else { $roleName }
$comment  = if ($dsl.PSObject.Properties["comment"] -and $dsl.comment) { [string]$dsl.comment } else { "" }

$flagSetForNewObjects = $false
$flagSetForAttributes = $true
$flagIndependentChild = $false
if ($dsl.PSObject.Properties["setForNewObjects"]) { $flagSetForNewObjects = [bool]$dsl.setForNewObjects }
if ($dsl.PSObject.Properties["setForAttributesByDefault"]) { $flagSetForAttributes = [bool]$dsl.setForAttributesByDefault }
if ($dsl.PSObject.Properties["independentRightsOfChildObjects"]) { $flagIndependentChild = [bool]$dsl.independentRightsOfChildObjects }

$roleObjects = @()

$dslObjects = @()
if ($dsl.PSObject.Properties["objects"] -and $dsl.objects) { $dslObjects = @($dsl.objects) }

foreach ($entry in $dslObjects) {
    if ($entry -is [string]) {
        # Shorthand: "Type.Name: @preset" | "Type.Name: Right1, Right2"
        $colonIdx = $entry.IndexOf(":")
        if ($colonIdx -lt 1) {
            Add-Err "Bad shorthand entry (expected 'Object: rights'): $entry"
            continue
        }
        $objName = Translate-ObjectName ($entry.Substring(0, $colonIdx).Trim())
        $spec = $entry.Substring($colonIdx + 1).Trim()
        $obj = New-RoleObject -name $objName

        $objType = $objName.Split(".")[0]
        if ($noRightsTypes -contains $objType) {
            Add-Err "${objName}: type '$objType' cannot carry rights in a role (see dsl-reference.md) - remove it from 'objects'"
            continue
        }

        foreach ($token in ($spec -split ",")) {
            $tk = $token.Trim()
            if (-not $tk) { continue }
            if ($tk.StartsWith("@")) {
                foreach ($r in (Resolve-Preset -objName $objName -presetName $tk.Substring(1).ToLower())) {
                    Set-Right -roleObj $obj -rightName $r -value $true
                }
            } else {
                Set-Right -roleObj $obj -rightName $tk -value $true
            }
        }
        if ($obj.Rights.Count -gt 0) { $roleObjects += $obj }
        elseif ($script:errors.Count -eq 0) { Add-Warn "${objName}: no rights resolved - object skipped" }
    } else {
        # Object form: { name, preset, rights, rls }
        if (-not $entry.name) {
            Add-Err "Object entry without 'name': $($entry | ConvertTo-Json -Compress -Depth 5)"
            continue
        }
        $objName = Translate-ObjectName ([string]$entry.name)
        $obj = New-RoleObject -name $objName

        $objType = $objName.Split(".")[0]
        if ($noRightsTypes -contains $objType) {
            Add-Err "${objName}: type '$objType' cannot carry rights in a role (see dsl-reference.md) - remove it from 'objects'"
            continue
        }

        if ($entry.PSObject.Properties["preset"] -and $entry.preset) {
            foreach ($r in (Resolve-Preset -objName $objName -presetName ([string]$entry.preset).TrimStart("@").ToLower())) {
                Set-Right -roleObj $obj -rightName $r -value $true
            }
        }
        if ($entry.PSObject.Properties["rights"] -and $entry.rights) {
            if ($entry.rights -is [System.Array]) {
                foreach ($r in $entry.rights) { Set-Right -roleObj $obj -rightName ([string]$r) -value $true }
            } else {
                foreach ($p in $entry.rights.PSObject.Properties) {
                    Set-Right -roleObj $obj -rightName $p.Name -value ([bool]$p.Value)
                }
            }
        }
        if ($entry.PSObject.Properties["rls"] -and $entry.rls) {
            foreach ($p in $entry.rls.PSObject.Properties) {
                $rName = Translate-Right $p.Name
                if (-not $obj.Rights.Contains($rName)) {
                    Set-Right -roleObj $obj -rightName $rName -value $true
                }
                $obj.Rights[$rName].rls = [string]$p.Value
            }
        }
        if ($obj.Rights.Count -gt 0) { $roleObjects += $obj }
        else { Add-Warn "${objName}: no rights resolved - object skipped" }
    }
}

$rlsTemplates = @()
if ($dsl.PSObject.Properties["templates"] -and $dsl.templates) {
    foreach ($tpl in @($dsl.templates)) {
        if (-not $tpl.name) { Add-Err "RLS template without 'name'"; continue }
        $cond = if ($tpl.PSObject.Properties["condition"]) { [string]$tpl.condition } else { "" }
        if (-not $cond) { Add-Warn "RLS template '$($tpl.name)': empty condition" }
        $rlsTemplates += [pscustomobject]@{ Name = [string]$tpl.name; Condition = $cond }
    }
}

if ($script:errors.Count -gt 0) {
    Write-Host "DSL errors ($($script:errors.Count)):" -ForegroundColor Red
    foreach ($e in $script:errors) { Write-Host "  ERR  $e" -ForegroundColor Red }
    foreach ($w in $script:warnings) { Write-Host "  WARN $w" -ForegroundColor Yellow }
    exit 1
}

# --- 4. Plan ---

$descriptorPath = Join-Path $RolesDir "$roleName.xml"
$extDir = Join-Path (Join-Path $RolesDir $roleName) "Ext"
$rightsPath = Join-Path $extDir "Rights.xml"

$existingUuid = $null
if (Test-Path $descriptorPath) {
    try {
        [xml]$existing = Get-Content -Path $descriptorPath -Encoding UTF8
        $roleNode = $existing.DocumentElement.SelectSingleNode("//*[local-name()='Role']")
        if ($roleNode) {
            $u = $roleNode.GetAttribute("uuid")
            if ($u) { $existingUuid = $u }
        }
    } catch {
        Add-Warn "Existing descriptor is not parseable, a new UUID will be generated: $($_.Exception.Message)"
    }
}

$totalRights = 0
$totalRls = 0
foreach ($o in $roleObjects) {
    $totalRights += $o.Rights.Count
    foreach ($k in $o.Rights.Keys) { if ($o.Rights[$k].rls) { $totalRls++ } }
}

$descriptorAction = if (Test-Path $descriptorPath) { "overwrite (UUID preserved)" } else { "create" }
$rightsAction = if (Test-Path $rightsPath) { "overwrite" } else { "create" }

Write-Host "Role:      $roleName ('$synonym')"
Write-Host "Objects:   $($roleObjects.Count) | Rights: $totalRights | RLS: $totalRls | Templates: $($rlsTemplates.Count)"
Write-Host "Descriptor: $descriptorPath [$descriptorAction]"
Write-Host "Rights:     $rightsPath [$rightsAction]"
foreach ($w in $script:warnings) { Write-Host "  WARN $w" -ForegroundColor Yellow }

if (-not $Apply) {
    Write-Host "DRY RUN: no files written." -ForegroundColor Yellow
    Write-Host "No changes made. Re-run with -Apply to generate the role files."
    exit 0
}

# --- 5. Generate XML (UTF-8 with BOM, indented) ---

$uuid = if ($existingUuid) { $existingUuid } else { [guid]::NewGuid().ToString() }

New-Item -ItemType Directory -Path $extDir -Force | Out-Null

$xmlSettings = New-Object System.Xml.XmlWriterSettings
$xmlSettings.Indent = $true
$xmlSettings.IndentChars = "    "
$xmlSettings.Encoding = New-Object System.Text.UTF8Encoding($true)

# 5a. Descriptor
$w = [System.Xml.XmlWriter]::Create($descriptorPath, $xmlSettings)
try {
    $mdNs = "http://v8.1c.ru/8.3/MDClasses"
    $v8Ns = "http://v8.1c.ru/8.1/data/core"
    $w.WriteStartDocument()
    $w.WriteStartElement("MetaDataObject", $mdNs)
    $w.WriteAttributeString("xmlns", "v8", $null, $v8Ns)
    $w.WriteAttributeString("xmlns", "xr", $null, "http://v8.1c.ru/8.3/xcf/readable")
    $w.WriteAttributeString("xmlns", "xs", $null, "http://www.w3.org/2001/XMLSchema")
    $w.WriteAttributeString("xmlns", "xsi", $null, "http://www.w3.org/2001/XMLSchema-instance")
    $w.WriteAttributeString("version", "2.17")
    $w.WriteStartElement("Role", $mdNs)
    $w.WriteAttributeString("uuid", $uuid)
    $w.WriteStartElement("Properties", $mdNs)
    $w.WriteElementString("Name", $mdNs, $roleName)
    $w.WriteStartElement("Synonym", $mdNs)
    $w.WriteStartElement("item", $v8Ns)
    $w.WriteElementString("lang", $v8Ns, "ru")
    $w.WriteElementString("content", $v8Ns, $synonym)
    $w.WriteEndElement() # item
    $w.WriteEndElement() # Synonym
    if ($comment) { $w.WriteElementString("Comment", $mdNs, $comment) }
    else { $w.WriteStartElement("Comment", $mdNs); $w.WriteEndElement() }
    $w.WriteEndElement() # Properties
    $w.WriteEndElement() # Role
    $w.WriteEndElement() # MetaDataObject
    $w.WriteEndDocument()
} finally {
    $w.Close()
}

# 5b. Rights.xml
$rightsNs = "http://v8.1c.ru/8.2/roles"
$w = [System.Xml.XmlWriter]::Create($rightsPath, $xmlSettings)
try {
    $w.WriteStartDocument()
    $w.WriteStartElement("Rights", $rightsNs)
    $w.WriteAttributeString("xmlns", "xs", $null, "http://www.w3.org/2001/XMLSchema")
    $w.WriteAttributeString("xmlns", "xsi", $null, "http://www.w3.org/2001/XMLSchema-instance")
    $w.WriteAttributeString("version", "2.17")
    $w.WriteElementString("setForNewObjects", $rightsNs, $flagSetForNewObjects.ToString().ToLower())
    $w.WriteElementString("setForAttributesByDefault", $rightsNs, $flagSetForAttributes.ToString().ToLower())
    $w.WriteElementString("independentRightsOfChildObjects", $rightsNs, $flagIndependentChild.ToString().ToLower())

    foreach ($o in $roleObjects) {
        $w.WriteStartElement("object", $rightsNs)
        $w.WriteElementString("name", $rightsNs, $o.Name)
        foreach ($rName in $o.Rights.Keys) {
            $r = $o.Rights[$rName]
            $w.WriteStartElement("right", $rightsNs)
            $w.WriteElementString("name", $rightsNs, $rName)
            $w.WriteElementString("value", $rightsNs, ([bool]$r.value).ToString().ToLower())
            if ($r.rls) {
                $w.WriteStartElement("restrictionByCondition", $rightsNs)
                $w.WriteElementString("condition", $rightsNs, [string]$r.rls)
                $w.WriteEndElement()
            }
            $w.WriteEndElement() # right
        }
        $w.WriteEndElement() # object
    }

    foreach ($tpl in $rlsTemplates) {
        $w.WriteStartElement("restrictionTemplate", $rightsNs)
        $w.WriteElementString("name", $rightsNs, $tpl.Name)
        $w.WriteElementString("condition", $rightsNs, $tpl.Condition)
        $w.WriteEndElement()
    }

    $w.WriteEndElement() # Rights
    $w.WriteEndDocument()
} finally {
    $w.Close()
}

# --- 6. Post-apply verification (script-contract: verify from re-read state) ---

$verifyOk = $true
foreach ($p in @($descriptorPath, $rightsPath)) {
    try {
        [xml](Get-Content -Path $p -Encoding UTF8) | Out-Null
        Write-Host "OK  written and re-parsed: $p" -ForegroundColor Green
    } catch {
        $verifyOk = $false
        Write-Host "ERR re-parse failed: $p - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Validate:  role-validate.ps1 -RightsPath `"$rightsPath`" -MetadataPath `"$descriptorPath`""
Write-Host "  2. Register the role in Configuration.xml <ChildObjects>: <Role>$roleName</Role> (if new)"

if (-not $verifyOk) { exit 1 }
exit 0
