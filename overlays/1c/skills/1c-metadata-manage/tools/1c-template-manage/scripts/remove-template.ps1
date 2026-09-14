<#
.SYNOPSIS
	Удаление макета из внешней обработки 1С (EPF)

.PARAMETER Apply
	Применить изменения. Без этого флага скрипт работает в режиме DryRun:
	показывает список удаляемых файлов и операций, и завершается без изменений.

.EXAMPLE
	.\remove-template.ps1 -ProcessorName "МояОбработка" -TemplateName "Макет"

.EXAMPLE
	.\remove-template.ps1 -ProcessorName "МояОбработка" -TemplateName "Макет" -Apply
#>
param(
	[Parameter(Mandatory)]
	[string]$ProcessorName,

	[Parameter(Mandatory)]
	[string]$TemplateName,

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
$templatesDir = Join-Path $processorDir "Templates"
$templateMetaPath = Join-Path $templatesDir "$TemplateName.xml"
$templateDir = Join-Path $templatesDir $TemplateName

if (-not (Test-Path $templateMetaPath)) {
	Write-Error "Метаданные макета не найдены: $templateMetaPath"
	exit 1
}

# --- DryRun gate (script-contract: mutations only under explicit -Apply) ---
if (-not $Apply) {
	Write-Host "DRY RUN: would remove template '$TemplateName':" -ForegroundColor Yellow
	if (Test-Path $templateDir) {
		Write-Host "  remove directory: $templateDir"
	}
	Write-Host "  remove file: $templateMetaPath"
	Write-Host "  unregister <Template>$TemplateName</Template> in $rootXmlPath"
	Write-Host "No changes made. Re-run with -Apply to remove the template."
	exit 0
}

# --- Удаление файлов ---

if (Test-Path $templateDir) {
	Remove-Item -Path $templateDir -Recurse -Force
	Write-Host "[OK] Удалён каталог: $templateDir"
}

Remove-Item -Path $templateMetaPath -Force
Write-Host "[OK] Удалён файл: $templateMetaPath"

# --- Модификация корневого XML ---

$rootXmlFull = Resolve-Path $rootXmlPath
$xmlDoc = New-Object System.Xml.XmlDocument
$xmlDoc.PreserveWhitespace = $true
$xmlDoc.Load($rootXmlFull.Path)

$nsMgr = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
$nsMgr.AddNamespace("md", "http://v8.1c.ru/8.3/MDClasses")

# Удалить <Template>TemplateName</Template> из ChildObjects
$templateNodes = $xmlDoc.SelectNodes("//md:ChildObjects/md:Template", $nsMgr)
foreach ($node in $templateNodes) {
	if ($node.InnerText -eq $TemplateName) {
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

Write-Host "[OK] Макет $TemplateName удалён из $rootXmlPath"
