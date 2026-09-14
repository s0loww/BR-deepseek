<#
.SYNOPSIS
	Удаление формы из внешней обработки 1С (EPF)

.PARAMETER Apply
	Применить изменения. Без этого флага скрипт работает в режиме DryRun:
	показывает список удаляемых файлов и операций, и завершается без изменений.

.EXAMPLE
	.\remove-form.ps1 -ProcessorName "МояОбработка" -FormName "Форма"

.EXAMPLE
	.\remove-form.ps1 -ProcessorName "МояОбработка" -FormName "Форма" -Apply
#>
param(
	[Parameter(Mandatory)]
	[string]$ProcessorName,

	[Parameter(Mandatory)]
	[string]$FormName,

	[string]$SrcDir = "src",

	[switch]$Apply
)

$ErrorActionPreference = "Stop"

# --- Проверки ---

$rootXmlPath = Join-Path $SrcDir "$ProcessorName.xml"
if (-not (Test-Path $rootXmlPath)) {
	Write-Error "Корневой файл обработки не найден: $rootXmlPath"
	exit 1
}

$processorDir = Join-Path $SrcDir $ProcessorName
$formsDir = Join-Path $processorDir "Forms"
$formMetaPath = Join-Path $formsDir "$FormName.xml"
$formDir = Join-Path $formsDir $FormName

if (-not (Test-Path $formMetaPath)) {
	Write-Error "Метаданные формы не найдены: $formMetaPath"
	exit 1
}

# --- DryRun gate (script-contract: mutations only under explicit -Apply) ---
if (-not $Apply) {
	Write-Host "DRY RUN: would remove form '$FormName':" -ForegroundColor Yellow
	if (Test-Path $formDir) {
		Write-Host "  remove directory: $formDir"
	}
	Write-Host "  remove file: $formMetaPath"
	Write-Host "  unregister <Form>$FormName</Form> in $rootXmlPath (DefaultForm cleared if it points to the form)"
	Write-Host "No changes made. Re-run with -Apply to remove the form."
	exit 0
}

# --- Удаление файлов ---

if (Test-Path $formDir) {
	Remove-Item -Path $formDir -Recurse -Force
	Write-Host "[OK] Удалён каталог: $formDir"
}

Remove-Item -Path $formMetaPath -Force
Write-Host "[OK] Удалён файл: $formMetaPath"

# --- Модификация корневого XML ---

$rootXmlFull = Resolve-Path $rootXmlPath
$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $true
$xmlDoc.Load($rootXmlFull.Path)

$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")

# Удалить <Form>FormName</Form> из ChildObjects
$formNodes = $xmlDoc.SelectNodes("//md:ChildObjects/md:Form", $nsMgr)
foreach ($node in $formNodes) {
	if ($node.InnerText -eq $FormName) {
		$parent = $node.ParentNode
		# Удалить предшествующий whitespace
		$prev = $node.PreviousSibling
		if ($prev -and $prev.NodeType -eq [System.Xml.XmlNodeType]::Whitespace) {
			$parent.RemoveChild($prev) | Out-Null
		}
		$parent.RemoveChild($node) | Out-Null
		break
	}
}

# Очистить DefaultForm если указывала на эту форму
$defaultForm = $xmlDoc.SelectSingleNode("//md:DefaultForm", $nsMgr)
if ($defaultForm -and $defaultForm.InnerText -match "Form\.$FormName$") {
	$defaultForm.InnerText = ""
}

# Сохранить с BOM
$encBom = New-Object System.Text.UTF8Encoding($true)
$settings = New-Object System.Xml.XmlWriterSettings
$settings.Encoding = $encBom
$settings.Indent = $false

$stream = New-Object System.IO.FileStream($rootXmlFull.Path, [System.IO.FileMode]::Create)
$writer = [System.Xml.XmlWriter]::Create($stream, $settings)
$xmlDoc.Save($writer)
$writer.Close()
$stream.Close()

Write-Host "[OK] Форма $FormName удалена из $rootXmlPath"
