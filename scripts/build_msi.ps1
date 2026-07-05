$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$DistApp = Join-Path $Root "dist\SciPlot"
$MsiRoot = Join-Path $Root "build\msi"
$Staging = Join-Path $MsiRoot "staging\SciPlot"
$WxsPath = Join-Path $MsiRoot "SciPlot.wxs"
$OutputPath = Join-Path $Root "dist\SciPlot-Windows-x64.msi"
$ProductVersion = "2.1.0"
$UpgradeCode = "AE751FD0-B9E6-410E-9F39-4A7BA2758F66"

if (-not (Test-Path (Join-Path $DistApp "SciPlot.exe"))) {
    throw "Missing packaged app. Run build_exe.ps1 before scripts\build_msi.ps1."
}

$resolvedRoot = [System.IO.Path]::GetFullPath($Root)
$resolvedMsiRoot = [System.IO.Path]::GetFullPath($MsiRoot)
if (-not $resolvedMsiRoot.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to prepare MSI outside the repository."
}

if (Test-Path $MsiRoot) {
    Remove-Item -LiteralPath $MsiRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $Staging | Out-Null
Copy-Item -Path (Join-Path $DistApp "*") -Destination $Staging -Recurse -Force
New-Item -ItemType File -Path (Join-Path $Staging "sciplot_installed.flag") -Force | Out-Null

function ConvertTo-WixLiteral([string]$value) {
    return [System.Security.SecurityElement]::Escape($value)
}

function New-WixId([string]$prefix, [string]$value) {
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($value.ToLowerInvariant())
    $hash = [System.BitConverter]::ToString($sha1.ComputeHash($bytes)).Replace("-", "")
    return "$prefix$($hash.Substring(0, 18))"
}

function Get-RelativePathCompat([string]$basePath, [string]$targetPath) {
    $baseFull = [System.IO.Path]::GetFullPath($basePath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
    $targetFull = [System.IO.Path]::GetFullPath($targetPath)
    $baseUri = New-Object System.Uri(($baseFull + [System.IO.Path]::DirectorySeparatorChar))
    $targetUri = New-Object System.Uri($targetFull)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($targetUri).ToString()).Replace("/", [System.IO.Path]::DirectorySeparatorChar)
}

$componentIds = New-Object System.Collections.Generic.List[string]
$directoryIds = @{}
$directoryIds[$Staging] = "INSTALLFOLDER"

function Write-WixDirectory([System.IO.DirectoryInfo]$directory, [int]$indent) {
    $pad = " " * $indent
    $lines = New-Object System.Collections.Generic.List[string]

    foreach ($file in Get-ChildItem -LiteralPath $directory.FullName -File | Sort-Object Name) {
        $relative = Get-RelativePathCompat $Staging $file.FullName
        $componentId = New-WixId "Cmp" $relative
        $fileId = New-WixId "Fil" $relative
        $componentIds.Add($componentId)
        $source = ConvertTo-WixLiteral $file.FullName
        $lines.Add("$pad  <Component Id=`"$componentId`" Guid=`"*`">")
        $lines.Add("$pad    <File Id=`"$fileId`" Source=`"$source`" KeyPath=`"yes`" />")
        $lines.Add("$pad  </Component>")
    }

    foreach ($child in Get-ChildItem -LiteralPath $directory.FullName -Directory | Sort-Object Name) {
        $relative = Get-RelativePathCompat $Staging $child.FullName
        $directoryId = New-WixId "Dir" $relative
        $name = ConvertTo-WixLiteral $child.Name
        $lines.Add("$pad  <Directory Id=`"$directoryId`" Name=`"$name`">")
        foreach ($childLine in Write-WixDirectory $child ($indent + 4)) {
            $lines.Add($childLine)
        }
        $lines.Add("$pad  </Directory>")
    }

    return $lines
}

$installFolderContent = Write-WixDirectory (Get-Item $Staging) 12
$componentRefs = New-Object System.Collections.Generic.List[string]
foreach ($componentId in $componentIds) {
    $componentRefs.Add("      <ComponentRef Id=`"$componentId`" />")
}
$componentRefs.Add("      <ComponentRef Id=`"StartMenuShortcut`" />")

$wxs = New-Object System.Collections.Generic.List[string]
$wxs.Add("<?xml version=`"1.0`" encoding=`"UTF-8`"?>")
$wxs.Add("<Wix xmlns=`"http://wixtoolset.org/schemas/v4/wxs`">")
$wxs.Add("  <Package Name=`"SciPlot`" Manufacturer=`"SciPlot`" Version=`"$ProductVersion`" UpgradeCode=`"{$UpgradeCode}`" Scope=`"perUser`">")
$wxs.Add("    <MajorUpgrade DowngradeErrorMessage=`"A newer version of SciPlot is already installed.`" />")
$wxs.Add("    <MediaTemplate EmbedCab=`"yes`" />")
$wxs.Add("    <StandardDirectory Id=`"LocalAppDataFolder`">")
$wxs.Add("      <Directory Id=`"ProgramsFolder`" Name=`"Programs`">")
$wxs.Add("        <Directory Id=`"INSTALLFOLDER`" Name=`"SciPlot`">")
foreach ($line in $installFolderContent) {
    $wxs.Add($line)
}
$wxs.Add("        </Directory>")
$wxs.Add("      </Directory>")
$wxs.Add("    </StandardDirectory>")
$wxs.Add("    <StandardDirectory Id=`"ProgramMenuFolder`">")
$wxs.Add("      <Directory Id=`"ApplicationProgramsFolder`" Name=`"SciPlot`">")
$wxs.Add("        <Component Id=`"StartMenuShortcut`" Guid=`"*`">")
$wxs.Add("          <Shortcut Id=`"ApplicationStartMenuShortcut`" Name=`"SciPlot`" Description=`"Create scientific plots`" Target=`"[INSTALLFOLDER]SciPlot.exe`" WorkingDirectory=`"INSTALLFOLDER`" />")
$wxs.Add("          <RemoveFolder Id=`"RemoveApplicationProgramsFolder`" On=`"uninstall`" />")
$wxs.Add("          <RegistryValue Root=`"HKCU`" Key=`"Software\SciPlot`" Name=`"installed`" Type=`"integer`" Value=`"1`" KeyPath=`"yes`" />")
$wxs.Add("        </Component>")
$wxs.Add("      </Directory>")
$wxs.Add("    </StandardDirectory>")
$wxs.Add("    <Feature Id=`"MainFeature`" Title=`"SciPlot`" Level=`"1`">")
foreach ($line in $componentRefs) {
    $wxs.Add($line)
}
$wxs.Add("    </Feature>")
$wxs.Add("  </Package>")
$wxs.Add("</Wix>")

New-Item -ItemType Directory -Path $MsiRoot -Force | Out-Null
$wxs | Set-Content -Path $WxsPath -Encoding UTF8

if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    $dotnetInfo = & dotnet --info 2>$null
    if ($LASTEXITCODE -ne 0 -or ($dotnetInfo -notmatch " .NET SDKs installed:" -and $dotnetInfo -notmatch "SDKs installed:")) {
        throw "WiX is not installed and no .NET SDK is available. Install the .NET SDK or build the MSI in GitHub Actions."
    }
    dotnet tool install --global wix
    $dotnetTools = Join-Path $env:USERPROFILE ".dotnet\tools"
    if ($env:PATH -notlike "*$dotnetTools*") {
        $env:PATH = "$dotnetTools;$env:PATH"
    }
}

wix build $WxsPath -o $OutputPath
Write-Host "MSI build complete:" -ForegroundColor Green
Write-Host $OutputPath
